"""Channel-agnostic guided booking flow.

The agent drives a selection-based booking (resolve customer → service → professional
→ date → time → confirm) and emits *structured steps* (a prompt + options, or a free
text ``input`` step). Each channel renders them: the dev chat as inline buttons, WhatsApp
as interactive list/buttons. The flow logic and state live here once.

State is kept per ``thread_id`` in ``guided_session_store`` (in-memory).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date as date_cls
from datetime import datetime, timedelta
from uuid import UUID

from packages.auth_core.tenant import set_tenant_context
from packages.models.enums import AppointmentSource, AppointmentStatus
from packages.scheduling.eligibility import list_catalog_services, list_eligible_professionals
from packages.scheduling.guided_session_store import (
    STEP_CONFIRM,
    STEP_DATE,
    STEP_PATIENT_CAPTURE,
    STEP_POST,
    STEP_PROFESSIONAL,
    STEP_SERVICE,
    STEP_SLOT,
    GuidedSession,
    clear_session,
    get_session,
    set_session,
)
from packages.scheduling.patient_booking import find_patient_by_phone, upsert_patient_by_phone
from packages.scheduling.schemas import AppointmentBase
from packages.scheduling.service import SchedulingService
from packages.scheduling.timezone_utils import now_local_naive

DATE_WINDOW_DAYS = 5  # how many upcoming days to offer in the date step
_PT_WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

CONFIRM_ID = "confirm"
CANCEL_ID = "cancel"
BACK_ID = "back"
BOOK_AGAIN_ID = "book_again"
FINISH_ID = "finish"

# LGPD consent (explicit opt-in buttons; rendered by the channel layer).
CONSENT_ACCEPT_ID = "consent_accept"
CONSENT_DECLINE_ID = "consent_decline"

# Entry menu + FAQ (rendered by the channel layer; not part of the booking session).
MENU_BOOK_ID = "menu_book"
MENU_FAQ_ID = "menu_faq"
# Canonical questions sent to the LLM+RAG engine. Phrased to avoid the scheduling
# keywords (e.g. "horário") that would otherwise force the triage into booking.
FAQ_TOPIC_QUESTIONS: dict[str, str] = {
    "faq_precos": "Quais são os preços dos serviços?",
    "faq_horario": "Em quais dias e horas o salão funciona?",
    "faq_cancelamento": "Qual a política de cancelamento?",
    "faq_pagamento": "Quais as formas de pagamento aceitas?",
}

# Back navigation: each booking step → the step it returns to.
_PREV_STEP = {
    STEP_PROFESSIONAL: STEP_SERVICE,
    STEP_DATE: STEP_PROFESSIONAL,
    STEP_SLOT: STEP_DATE,
    STEP_CONFIRM: STEP_SLOT,
}


@dataclass
class StructuredOption:
    id: str
    title: str
    description: str | None = None


@dataclass
class StructuredStep:
    step: str
    text: str
    kind: str  # "list" | "buttons" | "input"
    options: list[StructuredOption] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "type": "step",
            "step": self.step,
            "text": self.text,
            "kind": self.kind,
            "options": [asdict(o) for o in self.options],
        }


@dataclass
class BookingOutcome:
    success: bool
    message: str
    appointment: dict | None = None

    def to_dict(self) -> dict:
        return {
            "type": "outcome",
            "success": self.success,
            "message": self.message,
            "appointment": self.appointment,
        }


def _format_price(price: float | None) -> str:
    if not price:
        return ""
    return f"R$ {float(price):.2f}".replace(".", ",")


def _slot_time(slot_iso: str) -> str:
    """HH:MM label from a full-ISO slot."""
    try:
        return datetime.fromisoformat(slot_iso).strftime("%H:%M")
    except (ValueError, TypeError):
        return slot_iso


def _parse_name_phone(text: str) -> tuple[str | None, str | None]:
    """Best-effort split of a free-text reply into (name, phone)."""
    digits = re.sub(r"\D", "", text or "")
    phone = digits if 10 <= len(digits) <= 13 else None
    # Drop the phone-like run from the name.
    name = re.sub(r"[\d][\d\s().\-+]{8,}\d", " ", text or "")
    name = name.strip(" ,.-\t\n")
    return (name or None), phone


def _nav_options(*, back: bool) -> list[StructuredOption]:
    """Trailing Voltar/Cancelar options appended to booking steps."""
    opts: list[StructuredOption] = []
    if back:
        opts.append(StructuredOption(id=BACK_ID, title="↩ Voltar"))
    opts.append(StructuredOption(id=CANCEL_ID, title="✕ Cancelar"))
    return opts


# --- Consent + entry menu + FAQ (channel layer routes these; no booking session) ---

def consent_step(notice_text: str) -> StructuredStep:
    """LGPD notice as an explicit opt-in: [Concordo, continuar] / [Discordo, quero encerrar]."""
    return StructuredStep(
        "consent",
        notice_text,
        "buttons",
        [
            StructuredOption(id=CONSENT_ACCEPT_ID, title="Concordo, continuar"),
            StructuredOption(id=CONSENT_DECLINE_ID, title="Discordo, quero encerrar"),
        ],
    )


def menu_step() -> StructuredStep:
    return StructuredStep(
        "menu",
        "Como posso te ajudar?",
        "buttons",
        [
            StructuredOption(id=MENU_BOOK_ID, title="Agendar serviço"),
            StructuredOption(id=MENU_FAQ_ID, title="Tirar uma dúvida"),
        ],
    )


def faq_topics_step() -> StructuredStep:
    return StructuredStep(
        "faq",
        "Sobre o que é sua dúvida?",
        "list",
        [
            StructuredOption(id="faq_precos", title="Preços"),
            StructuredOption(id="faq_horario", title="Horário de funcionamento"),
            StructuredOption(id="faq_cancelamento", title="Cancelamento"),
            StructuredOption(id="faq_pagamento", title="Formas de pagamento"),
            StructuredOption(id="menu", title="↩ Voltar ao menu"),
        ],
    )


def post_faq_step() -> StructuredStep:
    """Offered after a FAQ answer so the user returns to the deterministic flow."""
    return StructuredStep(
        "faq_followup",
        "Posso ajudar com mais alguma coisa?",
        "buttons",
        [
            StructuredOption(id=MENU_BOOK_ID, title="Agendar serviço"),
            StructuredOption(id=MENU_FAQ_ID, title="Tirar outra dúvida"),
        ],
    )


def _post_step(message: str) -> StructuredStep:
    return StructuredStep(
        STEP_POST,
        message,
        "buttons",
        [
            StructuredOption(id=BOOK_AGAIN_ID, title="Agendar outro"),
            StructuredOption(id=FINISH_ID, title="Encerrar"),
        ],
    )


# --- Step builders ---

def _patient_capture_step(needs_phone: bool) -> StructuredStep:
    text = (
        "Qual o nome e o telefone (com DDD) do cliente?"
        if needs_phone
        else "Qual o seu nome completo?"
    )
    return StructuredStep(STEP_PATIENT_CAPTURE, text, "input", [])


def _service_step(org_id: str) -> StructuredStep:
    services = list_catalog_services(org_id)
    options = [
        StructuredOption(
            id=str(s["id"]),
            title=s["name"],
            description=_format_price(s.get("price")) or None,
        )
        for s in services
    ]
    if not options:
        return StructuredStep(STEP_SERVICE, "Nenhum serviço cadastrado.", "list", [])
    options += _nav_options(back=False)  # service is the first booking step (no Voltar)
    return StructuredStep(STEP_SERVICE, "Qual serviço você deseja?", "list", options)


def _professional_step(org_id: str, service_id: str) -> StructuredStep:
    pros = list_eligible_professionals(org_id, service_id)
    options = [StructuredOption(id=str(p["id"]), title=p["name"]) for p in pros]
    options += _nav_options(back=True)
    return StructuredStep(STEP_PROFESSIONAL, "Com qual profissional?", "list", options)


def _org_timezone(org_id: str) -> str:
    """Org timezone (canonical reader) so 'Hoje/Amanhã' match the salon's wall clock,
    not the server's — matters on UTC hosts (Render)."""
    try:
        with set_tenant_context(org_id):
            return SchedulingService()._get_org_config()["timezone"]
    except Exception:
        return "America/Sao_Paulo"


def _today_for(session: GuidedSession) -> date_cls:
    """Current calendar day in the org timezone (fallback DEFAULT_TIMEZONE)."""
    return now_local_naive(session.tzname).date()


def _date_step(today: date_cls, note: str | None = None) -> StructuredStep:
    options: list[StructuredOption] = []
    for offset in range(DATE_WINDOW_DAYS):
        d = today + timedelta(days=offset)
        label = "Hoje" if offset == 0 else "Amanhã" if offset == 1 else _PT_WEEKDAYS[d.weekday()]
        options.append(StructuredOption(id=d.isoformat(), title=f"{label} {d.strftime('%d/%m')}"))
    options += _nav_options(back=True)
    return StructuredStep(STEP_DATE, note or "Para qual dia?", "list", options)


async def _slot_step(org_id: str, session: GuidedSession) -> StructuredStep:
    service_obj = SchedulingService()
    with set_tenant_context(org_id):
        slots = await service_obj.get_available_slots(
            UUID(session.professional_id),
            date_cls.fromisoformat(session.date),
            session.service_duration or 30,
        )
    if not slots:
        return _date_step(_today_for(session), note="Sem horários nesse dia. Escolha outro:")
    options = [StructuredOption(id=s, title=_slot_time(s)) for s in slots]
    options += _nav_options(back=True)
    return StructuredStep(STEP_SLOT, "Qual horário?", "list", options)


def _confirm_step(session: GuidedSession) -> StructuredStep:
    price = _format_price(session.service_price)
    time_label = _slot_time(session.slot or "")
    summary = (
        f"Confirmar agendamento?\n"
        f"• Serviço: {session.service_name}{f' ({price})' if price else ''}\n"
        f"• Profissional: {session.professional_name}\n"
        f"• Data: {session.date} às {time_label}"
    )
    return StructuredStep(
        STEP_CONFIRM,
        summary,
        "buttons",
        [
            StructuredOption(id=CONFIRM_ID, title="Confirmar"),
            StructuredOption(id=BACK_ID, title="↩ Voltar"),
            StructuredOption(id=CANCEL_ID, title="✕ Cancelar"),
        ],
    )


# --- Public API ---

async def start_session(
    thread_id: str,
    *,
    org_id: str,
    patient_id: str | None = None,
    patient_phone: str | None = None,
    channel: str = "chat_test",
) -> StructuredStep:
    """Begin a guided booking and return the first step.

    The client is resolved *before* the conversation — never asked in-chat:
    - ``patient_id`` (dev chat test-page selector): use it directly → shortened flow.
    - ``patient_phone`` (WhatsApp sender): resolve by phone; onboarding if not found.
    - neither (test "not registered"): onboarding asking name + phone.
    """
    session = GuidedSession(org_id=org_id, channel=channel)
    session.tzname = _org_timezone(org_id)

    if patient_id:
        session.patient_id = patient_id
        session.step = STEP_SERVICE
        set_session(thread_id, session)
        return _service_step(org_id)

    if patient_phone:
        session.patient_phone = patient_phone
        with set_tenant_context(org_id):
            existing = find_patient_by_phone(org_id, patient_phone)
        if existing:
            session.patient_id = existing["id"]
            session.step = STEP_SERVICE
            set_session(thread_id, session)
            return _service_step(org_id)
        session.step = STEP_PATIENT_CAPTURE
        session.needs_phone = False  # phone already known from the sender
        set_session(thread_id, session)
        return _patient_capture_step(needs_phone=False)

    session.step = STEP_PATIENT_CAPTURE
    session.needs_phone = True
    set_session(thread_id, session)
    return _patient_capture_step(needs_phone=True)


async def _render_step(session: GuidedSession) -> StructuredStep:
    """Re-render the step the session is currently on (used for back navigation)."""
    if session.step == STEP_SERVICE:
        return _service_step(session.org_id)
    if session.step == STEP_PROFESSIONAL:
        return _professional_step(session.org_id, session.service_id or "")
    if session.step == STEP_DATE:
        return _date_step(_today_for(session))
    if session.step == STEP_SLOT:
        return await _slot_step(session.org_id, session)
    return _confirm_step(session)


async def advance(thread_id: str, selection_id: str) -> StructuredStep | BookingOutcome:
    """Apply a selection/typed input and return the next step or a terminal outcome."""
    session = get_session(thread_id)
    if session is None:
        return BookingOutcome(False, "Sessão expirada. Comece o agendamento novamente.")

    raw = selection_id or ""
    selection = raw.strip()

    # Voltar / Cancelar work on any selection step (not on the free-text input step).
    if session.step not in (STEP_PATIENT_CAPTURE, STEP_POST):
        if selection == CANCEL_ID:
            clear_session(thread_id)
            return BookingOutcome(False, "Agendamento cancelado.")
        if selection == BACK_ID:
            prev = _PREV_STEP.get(session.step)
            if not prev:
                clear_session(thread_id)
                return BookingOutcome(False, "Agendamento cancelado.")
            session.step = prev
            set_session(thread_id, session)
            return await _render_step(session)

    if session.step == STEP_PATIENT_CAPTURE:
        name, phone = _parse_name_phone(raw)
        phone = phone or session.patient_phone
        if not name or not phone:
            return _patient_capture_step(needs_phone=session.needs_phone)
        with set_tenant_context(session.org_id):
            patient_id = upsert_patient_by_phone(session.org_id, name, phone)
        if not patient_id:
            return _patient_capture_step(needs_phone=session.needs_phone)
        session.patient_id = patient_id
        session.patient_phone = phone
        session.step = STEP_SERVICE
        set_session(thread_id, session)
        return _service_step(session.org_id)

    if session.step == STEP_POST:
        if selection == BOOK_AGAIN_ID:
            fresh = GuidedSession(org_id=session.org_id, channel=session.channel)
            fresh.patient_id = session.patient_id
            fresh.patient_phone = session.patient_phone
            fresh.step = STEP_SERVICE
            set_session(thread_id, fresh)
            return _service_step(fresh.org_id)
        clear_session(thread_id)
        return BookingOutcome(True, "Tudo certo! Quando precisar, é só chamar. 👋")

    if session.step == STEP_SERVICE:
        service = _find_service(session.org_id, selection)
        if not service:
            return _service_step(session.org_id)
        session.service_id = str(service["id"])
        session.service_name = service["name"]
        session.service_duration = int(service.get("duration_minutes") or 30)
        session.service_price = service.get("price")
        session.step = STEP_PROFESSIONAL
        set_session(thread_id, session)
        step = _professional_step(session.org_id, session.service_id)
        if not step.options:
            clear_session(thread_id)
            return BookingOutcome(False, "Nenhum profissional disponível para esse serviço.")
        return step

    if session.step == STEP_PROFESSIONAL:
        pros = list_eligible_professionals(session.org_id, session.service_id or "")
        match = next((p for p in pros if str(p["id"]) == selection), None)
        if not match:
            return _professional_step(session.org_id, session.service_id or "")
        session.professional_id = str(match["id"])
        session.professional_name = match["name"]
        session.step = STEP_DATE
        set_session(thread_id, session)
        return _date_step(_today_for(session))

    if session.step == STEP_DATE:
        if not _valid_date(selection):
            return _date_step(_today_for(session))
        session.date = selection
        set_session(thread_id, session)
        step = await _slot_step(session.org_id, session)
        if step.step == STEP_SLOT:
            session.step = STEP_SLOT
            set_session(thread_id, session)
        return step

    if session.step == STEP_SLOT:
        if not _valid_slot(selection):
            return await _slot_step(session.org_id, session)
        session.slot = selection
        session.step = STEP_CONFIRM
        set_session(thread_id, session)
        return _confirm_step(session)

    if session.step == STEP_CONFIRM:
        if selection == CONFIRM_ID:
            outcome = await _create_appointment(session)
            if outcome.success:
                session.step = STEP_POST
                set_session(thread_id, session)
                return _post_step(outcome.message)
            clear_session(thread_id)
            return outcome
        return _confirm_step(session)

    clear_session(thread_id)
    return BookingOutcome(False, "Fluxo inválido. Comece novamente.")


def _find_service(org_id: str, service_id: str) -> dict | None:
    return next(
        (s for s in list_catalog_services(org_id) if str(s["id"]) == service_id),
        None,
    )


def _valid_date(value: str) -> bool:
    try:
        date_cls.fromisoformat(value)
        return True
    except (ValueError, TypeError):
        return False


def _valid_slot(value: str) -> bool:
    """A slot selection must be a full ISO datetime (as offered by get_available_slots)."""
    try:
        datetime.fromisoformat(value)
        return True
    except (ValueError, TypeError):
        return False


async def _create_appointment(session: GuidedSession) -> BookingOutcome:
    if not (session.patient_id and session.service_id and session.professional_id and session.slot):
        return BookingOutcome(False, "Faltam dados para confirmar o agendamento.")

    with set_tenant_context(session.org_id):
        try:
            scheduled_at = datetime.fromisoformat(session.slot)
            appointment = AppointmentBase(
                patient_id=UUID(str(session.patient_id)),
                professional_id=UUID(session.professional_id),
                service_id=UUID(session.service_id),
                scheduled_at=scheduled_at,
                duration_minutes=session.service_duration or 30,
                status=AppointmentStatus.CONFIRMED,
                source=AppointmentSource.WHATSAPP if session.channel == "whatsapp" else AppointmentSource.DASHBOARD,
            )
            result = await SchedulingService().create_appointment(appointment)
        except Exception as exc:  # noqa: BLE001 — friendly message, detail logged upstream
            return BookingOutcome(False, _friendly_error(exc))

    return BookingOutcome(
        True,
        f"Agendamento confirmado para {session.date} às {_slot_time(session.slot)} "
        f"({session.service_name} com {session.professional_name}).",
        appointment=result if isinstance(result, dict) else None,
    )


def _friendly_error(exc: Exception) -> str:
    name = type(exc).__name__
    if name == "DoubleBookingError":
        return "Esse horário acabou de ser ocupado. Escolha outro horário."
    return "Não foi possível concluir o agendamento. Tente novamente."
