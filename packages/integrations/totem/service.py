"""Totem (kiosk) attendance orchestration — a third channel over the existing engine.

Drives the outer self-service flow on a public tablet and delegates the heavy
lifting to code already shared with WhatsApp/chat:
  - booking + FAQ steps → ``packages.scheduling.guided_booking``
  - LGPD consent → ``packages.compliance.consent``
  - FAQ answers (LLM+RAG) → ``packages.engine.service.dispatch_chat_test`` (channel="totem")
  - check-in → ``SchedulingService.update_appointment_status`` (status ARRIVED)

Identity model mirrors WhatsApp: the booking/consent thread is ``{org_id}:{phone}``,
so a returning customer is recognized and never re-consented. The client-facing
handle is an opaque ``session_id`` (the phone never travels back to the device).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from packages.auth_core.conversation_thread import build_thread_id
from packages.auth_core.database import db
from packages.auth_core.tenant import set_tenant_context
from packages.compliance.consent import ConsentAction, evaluate_consent_gate, record_consent, record_decline
from packages.integrations.totem.session_store import (
    PHASE_BOOKING,
    PHASE_CONSENT,
    PHASE_DONE,
    PHASE_FAQ,
    PHASE_IDENTIFY,
    PHASE_MENU,
    TotemSession,
    clear_session,
    get_session,
    set_session,
)
from packages.models.enums import AppointmentStatus
from packages.scheduling import guided_booking as gb
from packages.scheduling.guided_session_store import STEP_POST
from packages.scheduling.guided_session_store import clear_session as clear_booking_session
from packages.scheduling.patient_booking import find_patient_by_phone, upsert_patient_by_phone

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "America/Sao_Paulo"

# Totem-only menu id (booking/FAQ ids are reused from guided_booking).
MENU_CHECKIN_ID = "menu_checkin"
# Post-action navigation (after a check-in result).
POST_MENU_ID = "post_menu"
POST_FINISH_ID = "post_finish"

# Check-in is offered for appointments not yet started.
_CHECKIN_ELIGIBLE = {AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED}


# --- Response shaping -------------------------------------------------------

def _payload(
    session_id: str, response: str, step: dict | None = None, *, done: bool = False
) -> dict[str, Any]:
    """Uniform turn result the kiosk PWA renders (text + optional StructuredStep)."""
    return {"session_id": session_id, "response": response, "step": step, "done": done}


def _identify_step() -> gb.StructuredStep:
    return gb.StructuredStep(
        PHASE_IDENTIFY,
        "Bem-vindo(a)! Para começar, digite seu nome e telefone (com DDD).",
        "input",
        [],
    )


def _menu_step() -> gb.StructuredStep:
    return gb.StructuredStep(
        PHASE_MENU,
        "Como posso te ajudar?",
        "buttons",
        [
            gb.StructuredOption(id=gb.MENU_BOOK_ID, title="Agendar serviço"),
            gb.StructuredOption(id=MENU_CHECKIN_ID, title="Fazer check-in"),
            gb.StructuredOption(id=gb.MENU_FAQ_ID, title="Tirar uma dúvida"),
        ],
    )


def _checkin_result_step(message: str) -> gb.StructuredStep:
    return gb.StructuredStep(
        "checkin_result",
        message,
        "buttons",
        [
            gb.StructuredOption(id=POST_MENU_ID, title="Voltar ao menu"),
            gb.StructuredOption(id=POST_FINISH_ID, title="Encerrar"),
        ],
    )


# --- Public API -------------------------------------------------------------

def start_totem_session(org_id: str) -> dict[str, Any]:
    """Begin a kiosk attendance and return the identification step."""
    session_id = uuid.uuid4().hex
    set_session(session_id, TotemSession(org_id=org_id, phase=PHASE_IDENTIFY))
    step = _identify_step()
    return _payload(session_id, step.text, step.to_dict())


async def advance_totem(session_id: str, selection: str) -> dict[str, Any]:
    """Apply one input/selection and return the next step or a terminal result."""
    session = get_session(session_id)
    if session is None:
        return _payload(session_id, "Sessão expirada. Toque para recomeçar.", None, done=True)

    raw = (selection or "").strip()
    phase = session.phase

    if phase == PHASE_IDENTIFY:
        return await _handle_identify(session_id, session, raw)
    if phase == PHASE_CONSENT:
        return _handle_consent(session_id, session, raw)
    if phase == PHASE_MENU:
        return await _handle_menu(session_id, session, raw)
    if phase == PHASE_BOOKING:
        return await _handle_booking(session_id, session, raw)
    if phase == PHASE_FAQ:
        return await _handle_faq(session_id, session, raw)

    # PHASE_DONE or unknown → restart cleanly.
    clear_session(session_id)
    return _payload(session_id, "Atendimento encerrado. Toque para recomeçar.", None, done=True)


# --- Phase handlers ---------------------------------------------------------

async def _handle_identify(session_id: str, session: TotemSession, raw: str) -> dict[str, Any]:
    name, phone = gb._parse_name_phone(raw)
    if not name or not phone:
        step = gb.StructuredStep(
            PHASE_IDENTIFY,
            "Não entendi. Digite seu nome e telefone com DDD (ex.: Maria 11999998888).",
            "input",
            [],
        )
        return _payload(session_id, step.text, step.to_dict())

    org_id = session.org_id
    with set_tenant_context(org_id):
        patient_id = upsert_patient_by_phone(org_id, name, phone)
        if not patient_id:
            step = gb.StructuredStep(
                PHASE_IDENTIFY,
                "Telefone inválido. Tente novamente com DDD (ex.: 11999998888).",
                "input",
                [],
            )
            return _payload(session_id, step.text, step.to_dict())

        session.name = name
        session.phone = phone
        session.patient_id = patient_id
        session.booking_thread_id = build_thread_id(org_id, phone)

        action, notice, _shown = evaluate_consent_gate(org_id, phone, "totem")

    if action == ConsentAction.SEND_NOTICE and notice:
        session.phase = PHASE_CONSENT
        set_session(session_id, session)
        step = gb.consent_step(notice)
        return _payload(session_id, step.text, step.to_dict())

    session.phase = PHASE_MENU
    set_session(session_id, session)
    step = _menu_step()
    return _payload(session_id, step.text, step.to_dict())


def _handle_consent(session_id: str, session: TotemSession, raw: str) -> dict[str, Any]:
    org_id = session.org_id
    if raw == gb.CONSENT_DECLINE_ID:
        with set_tenant_context(org_id):
            record_decline(org_id, session.phone or "", "totem")
        clear_session(session_id)
        return _payload(
            session_id,
            "Tudo bem! Encerrando por aqui. Quando quiser, é só chamar. 👋",
            None,
            done=True,
        )
    if raw == gb.CONSENT_ACCEPT_ID:
        with set_tenant_context(org_id):
            record_consent(org_id, session.phone or "", "totem")
        session.phase = PHASE_MENU
        set_session(session_id, session)
        step = _menu_step()
        return _payload(session_id, step.text, step.to_dict())

    # Anything else: re-ask explicitly (fail-closed — no implicit consent).
    step = gb.StructuredStep(
        "consent",
        "Para continuar, toque em uma das opções.",
        "buttons",
        [
            gb.StructuredOption(id=gb.CONSENT_ACCEPT_ID, title="Concordo, continuar"),
            gb.StructuredOption(id=gb.CONSENT_DECLINE_ID, title="Discordo, quero encerrar"),
        ],
    )
    return _payload(session_id, step.text, step.to_dict())


async def _handle_menu(session_id: str, session: TotemSession, raw: str) -> dict[str, Any]:
    org_id = session.org_id

    if raw == POST_FINISH_ID:
        clear_session(session_id)
        return _payload(
            session_id, "Atendimento encerrado. Até logo! 👋", None, done=True
        )
    # POST_MENU_ID and any unrecognized id fall through to re-showing the menu.

    if raw == gb.MENU_BOOK_ID:
        with set_tenant_context(org_id):
            step = await gb.start_session(
                session.booking_thread_id or session_id,
                org_id=org_id,
                patient_id=session.patient_id,
                channel="totem",
            )
        session.phase = PHASE_BOOKING
        set_session(session_id, session)
        return _booking_payload(session_id, session, step)

    if raw == MENU_CHECKIN_ID:
        message = await _do_checkin(session)
        step = _checkin_result_step(message)
        # Stay available: a check-in result offers menu/finish.
        set_session(session_id, session)
        return _payload(session_id, message, step.to_dict())

    if raw == gb.MENU_FAQ_ID:
        session.phase = PHASE_FAQ
        set_session(session_id, session)
        step = gb.faq_topics_step()
        return _payload(session_id, step.text, step.to_dict())

    # Unrecognized → re-show menu.
    step = _menu_step()
    return _payload(session_id, step.text, step.to_dict())


async def _handle_booking(session_id: str, session: TotemSession, raw: str) -> dict[str, Any]:
    with set_tenant_context(session.org_id):
        result = await gb.advance(session.booking_thread_id or session_id, raw)
    return _booking_payload(session_id, session, result)


async def _handle_faq(session_id: str, session: TotemSession, raw: str) -> dict[str, Any]:
    org_id = session.org_id

    # Back to the menu, or jump straight to booking from the FAQ follow-up.
    if raw == "menu":
        session.phase = PHASE_MENU
        set_session(session_id, session)
        step = _menu_step()
        return _payload(session_id, step.text, step.to_dict())
    if raw == gb.MENU_BOOK_ID:
        return await _handle_menu(session_id, session, gb.MENU_BOOK_ID)
    if raw == gb.MENU_FAQ_ID:
        step = gb.faq_topics_step()
        return _payload(session_id, step.text, step.to_dict())

    canonical = gb.FAQ_TOPIC_QUESTIONS.get(raw)
    if not canonical:
        step = gb.faq_topics_step()
        return _payload(session_id, step.text, step.to_dict())

    # Reuse the shared LLM+RAG engine with channel="totem" (single source of truth).
    from packages.engine.service import dispatch_chat_test

    with set_tenant_context(org_id):
        result = await dispatch_chat_test(
            canonical,
            thread_id=session.booking_thread_id,
            org_id=org_id,
            guided_enabled=False,
            channel="totem",
        )
    answer = result.get("response") or "Não encontrei essa informação."
    follow = gb.post_faq_step()
    return _payload(session_id, answer, follow.to_dict())


# --- Booking result shaping + metric ---------------------------------------

def _booking_payload(session_id: str, session: TotemSession, result: Any) -> dict[str, Any]:
    """Shape a guided StructuredStep/BookingOutcome and reset the totem on terminal."""
    if isinstance(result, gb.StructuredStep):
        # STEP_POST means an appointment was just created — record totem telemetry.
        if result.step == STEP_POST:
            _record_booking_metric(session)
        return _payload(session_id, result.text, result.to_dict())

    # BookingOutcome → terminal for this attendance.
    clear_booking_session(session.booking_thread_id or session_id)
    session.phase = PHASE_DONE
    set_session(session_id, session)
    message = getattr(result, "message", "Atendimento encerrado.")
    return _payload(session_id, message, None, done=True)


def _record_booking_metric(session: TotemSession) -> None:
    """Best-effort totem booking telemetry (deterministic path, no tokens)."""
    try:
        from packages.engine.metrics.service import save_conversation_metric

        thread = session.booking_thread_id or ""
        save_conversation_metric(
            thread_id=thread,
            sender_id=thread,
            agent_type="scheduling",
            messages_count=0,
            tokens_in=0,
            tokens_out=0,
            tokens_total=0,
            organization_id=session.org_id,
            scheduling_path="deterministic",
            triage_source="guided",
            channel="totem",
            tools_called=["book_time"],
        )
    except Exception as exc:
        logger.debug("Could not record totem booking metric: %s", type(exc).__name__)


# --- Check-in ---------------------------------------------------------------

def _org_timezone(org_id: str) -> str:
    try:
        row = (
            db.client.table("organizations")
            .select("timezone")
            .eq("id", org_id)
            .limit(1)
            .execute()
        )
        if row.data:
            return row.data[0].get("timezone") or DEFAULT_TIMEZONE
    except Exception:
        pass
    return DEFAULT_TIMEZONE


def _today_bounds_utc(tzname: str) -> tuple[str, str]:
    """[start, end] of the org's local day, expressed as UTC ISO for the query."""
    try:
        tz = ZoneInfo(tzname)
    except Exception:
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    now_local = datetime.now(tz)
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    return (
        start_local.astimezone(timezone.utc).isoformat(),
        end_local.astimezone(timezone.utc).isoformat(),
    )


async def _do_checkin(session: TotemSession) -> str:
    """Mark the customer's open appointment for today as ARRIVED. Friendly, fail-soft."""
    org_id = session.org_id
    phone = session.phone or ""

    with set_tenant_context(org_id):
        patient = find_patient_by_phone(org_id, phone)
        if not patient:
            return "Não encontrei seu cadastro. Procure a recepção, por favor."

        tzname = _org_timezone(org_id)
        start_iso, end_iso = _today_bounds_utc(tzname)
        try:
            rows = (
                db.client.table("appointments")
                .select("id, scheduled_at, status, service:service_catalog(name)")
                .eq("organization_id", org_id)
                .eq("patient_id", patient["id"])
                .gte("scheduled_at", start_iso)
                .lt("scheduled_at", end_iso)
                .order("scheduled_at")
                .execute()
            ).data or []
        except Exception as exc:
            logger.warning("check-in query failed: %s", type(exc).__name__)
            return "Não consegui consultar sua agenda agora. Procure a recepção, por favor."

        if not rows:
            return "Não encontrei agendamento para hoje. Procure a recepção, por favor."

        # Already in service / done?
        if any(r.get("status") in (AppointmentStatus.ARRIVED.value, AppointmentStatus.IN_PROGRESS.value) for r in rows):
            return "Você já fez check-in. É só aguardar — já avisamos a recepção. 😊"

        target = next(
            (r for r in rows if AppointmentStatus(r["status"]) in _CHECKIN_ELIGIBLE), None
        )
        if not target:
            return "Seu atendimento de hoje não está disponível para check-in. Procure a recepção."

        from packages.scheduling.service import SchedulingService

        try:
            await SchedulingService().update_appointment_status(
                UUID(str(target["id"])),
                AppointmentStatus.ARRIVED,
                organization_id=org_id,
            )
        except Exception as exc:
            logger.warning("check-in status update failed: %s", type(exc).__name__)
            return "Não consegui concluir o check-in. Procure a recepção, por favor."

    name = (session.name or "").split(" ")[0] or "tudo certo"
    return f"Check-in confirmado, {name}! Já avisamos a recepção. Pode aguardar. ✅"
