"""Deterministic booking — bypasses LLM datetime formatting mistakes."""
from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import date
from uuid import UUID

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig

from packages.auth_core.tenant import set_tenant_context
from packages.engine.routing import (
    has_implicit_scheduling_intent,
    has_scheduling_intent,
    has_temporal_scheduling_intent,
    is_booking_confirmed_in_thread,
    is_post_booking_closing,
    message_text,
    wants_new_booking_after_confirm,
)
from packages.models.enums import AppointmentStatus
from packages.scheduling.booking.models import (
    _NAME_PATTERNS,
    BookingIntent,
    SchedulingTurnResult,
    is_availability_followup,
)
from packages.scheduling.booking.prompts import catalog_service_prompt
from packages.scheduling.booking_flow_memory import (
    build_date_confirmed_prompt,
    extract_offered_slots_from_thread,
    is_date_choice_opinion_question,
    is_date_confirmation_without_new_time,
    try_flow_recovery_turn,
)
from packages.scheduling.booking_state_sync import (
    BookingStateSnapshot,
    date_is_resolved,
    get_checkpoint_clarification_message,
    has_open_date_clarification,
)
from packages.scheduling.date_parsing import (
    DateParseMode,
    has_temporal_date_hint,
    resolve_date_detailed,
    resolve_date_from_text,
)
from packages.scheduling.eligibility import _SERVICE_SEARCH_SYNONYMS, list_catalog_services
from packages.scheduling.guardrails import (
    extract_booking_date_from_text,
    parse_booking_date,
    resolve_booking_phone,
    resolve_service_from_catalog,
    sanitize_text_field,
    validate_phone,
)
from packages.scheduling.patient_booking import upsert_patient_by_phone
from packages.scheduling.schemas import AppointmentBase
from packages.scheduling.service import SchedulingService
from packages.scheduling.timezone_utils import (
    build_local_datetime,
    extract_booking_time_from_text,
    format_local_datetime_label,
    parse_booking_datetime,
)

logger = logging.getLogger(__name__)


def _strip_agent_envelope(text: str) -> str:
    if "[MENSAGEM DO CLIENTE]" in text:
        start = text.find("[MENSAGEM DO CLIENTE]")
        end = text.find("[FIM]", start)
        if end != -1:
            return text[start + len("[MENSAGEM DO CLIENTE]") : end].strip()
    return text.strip()


def _human_texts(messages: Sequence[BaseMessage]) -> list[str]:
    return [
        _strip_agent_envelope(message_text(m))
        for m in messages
        if m.type == "human" and message_text(m).strip()
    ]


def _extract_service_from_thread(messages: Sequence[BaseMessage], org_id: str) -> str | None:
    catalog = list_catalog_services(org_id)
    if not catalog:
        return None
    for msg in reversed(messages):
        if getattr(msg, "type", None) not in {"human", "ai"}:
            continue
        text = message_text(msg).lower()
        for row in catalog:
            if row["name"].lower() in text:
                return row["name"]
        for synonym in _SERVICE_SEARCH_SYNONYMS:
            if synonym in text:
                service, err = resolve_service_from_catalog(org_id, synonym, catalog=catalog)
                if service and not err:
                    return service["name"]
    return None


def _coerce_booking_date(value: str | None, *, reference: date | None = None) -> str | None:
    if not value:
        return None
    ref = reference or date.today()
    parsed = extract_booking_date_from_text(value, reference=ref)
    if parsed:
        return parsed
    parsed_date, err = parse_booking_date(value, reference=ref)
    if parsed_date and not err:
        return parsed_date.isoformat()
    return None


_DATE_RESET_PHRASES = (
    "outro dia",
    "outra data",
    "mudar data",
    "trocar data",
    "mudar o dia",
    "outra dia",
)


def _wants_date_reset(text: str) -> bool:
    t = text.lower().strip()
    return any(phrase in t for phrase in _DATE_RESET_PHRASES)


def _combined_date_clarification(
    combined: str,
    last: str,
    *,
    reference: date,
    checkpoint: BookingStateSnapshot | None = None,
) -> tuple[str | None, str | None]:
    """Re-apply ambiguous-date clarification from the full human thread."""
    if checkpoint and date_is_resolved(checkpoint):
        return None, None

    from packages.scheduling.booking_flow_memory import (
        build_date_choice_redirect_message,
        is_date_choice_opinion_question,
    )

    combined_detailed = resolve_date_detailed(combined, reference=reference, mode=DateParseMode.BOOKING)
    if not combined_detailed or not combined_detailed.needs_clarification:
        return None, None
    prompt = combined_detailed.clarification_prompt or "Qual dia você prefere?"
    if is_date_choice_opinion_question(last):
        prompt = build_date_choice_redirect_message(prompt)
    return None, prompt


def _resolve_explicit_date_from_thread(
    texts: list[str],
    *,
    reference: date,
) -> str | None:
    """Most recent unambiguous date pick in prior human turns (e.g. after a clarify)."""
    if len(texts) <= 1:
        return None
    for text in reversed(texts[:-1]):
        if _wants_date_reset(text):
            return None
        if is_date_choice_opinion_question(text):
            continue
        detailed = resolve_date_detailed(text, reference=reference, mode=DateParseMode.BOOKING)
        if detailed and detailed.needs_clarification:
            continue
        if detailed and detailed.iso:
            return detailed.iso
    return None


def _resolve_booking_date_turn(
    last: str,
    combined: str,
    *,
    reference: date,
    booking_date: str | None,
    human_texts: list[str] | None = None,
    checkpoint: BookingStateSnapshot | None = None,
) -> tuple[str | None, str | None]:
    """Returns (iso, clarification_message). Clarification blocks stale fallbacks."""
    texts = human_texts or ([last] if last else [])

    last_detailed = resolve_date_detailed(last, reference=reference, mode=DateParseMode.BOOKING)
    if last_detailed:
        if last_detailed.needs_clarification:
            return None, last_detailed.clarification_prompt
        if last_detailed.iso:
            return last_detailed.iso, None

    if _wants_date_reset(last):
        return None, "Sem problemas! Para qual data você quer agendar?"

    if has_temporal_date_hint(last) and not last_detailed:
        return None, "Qual dia você prefere? (ex: sexta, amanhã ou 12/06)"

    if booking_date and not _wants_date_reset(last):
        coerced = _coerce_booking_date(booking_date, reference=reference)
        if coerced:
            return coerced, None

    thread_date = _resolve_explicit_date_from_thread(texts, reference=reference)
    if thread_date:
        return thread_date, None

    pending = _combined_date_clarification(
        combined, last, reference=reference, checkpoint=checkpoint
    )
    if pending[1]:
        return pending

    if not _wants_date_reset(last):
        combined_iso = extract_booking_date_from_text(combined, reference=reference)
        if combined_iso:
            return combined_iso, None

    past_msg = _past_booking_date_message(last, reference=reference)
    if past_msg:
        return None, past_msg

    return None, None


def resolve_booking_context(
    messages: Sequence[BaseMessage],
    org_id: str,
    *,
    booking_date: str | None = None,
    booking_service: str | None = None,
    checkpoint: BookingStateSnapshot | None = None,
) -> tuple[str | None, str | None, str | None]:
    texts = _human_texts(messages)
    combined = " ".join(texts)
    last = texts[-1] if texts else ""
    ref = date.today()

    date_iso, clarification = _resolve_booking_date_turn(
        last,
        combined,
        reference=ref,
        booking_date=booking_date,
        human_texts=texts,
        checkpoint=checkpoint,
    )
    service_query = (
        _guess_service_query(last, org_id, prefer_exact=True)
        or _guess_service_query(combined, org_id)
        or _extract_service_from_thread(messages, org_id)
        or booking_service
    )
    return date_iso, service_query, clarification


def _past_booking_date_message(text: str, *, reference: date | None = None) -> str | None:
    ref = reference or date.today()
    reference_res = resolve_date_from_text(text, reference=ref, mode=DateParseMode.REFERENCE)
    booking_res = resolve_date_from_text(text, reference=ref, mode=DateParseMode.BOOKING)
    if reference_res and not booking_res:
        return (
            "Para agendar, preciso de uma data a partir de hoje. "
            "Qual dia você prefere?"
        )
    return None


async def format_availability_reply(service_query: str, date_iso: str, config: RunnableConfig) -> str:
    from packages.engine.response_composer import format_date_label_pt

    coerced = _coerce_booking_date(date_iso)
    if not coerced:
        return (
            "Data inválida para agendamento. "
            "Informe o dia claramente (ex: sexta-feira, 10 de junho ou 2026-06-10)."
        )
    summary = await fetch_availability_summary(service_query, coerced, config)
    if summary.startswith("Não há horários"):
        when = format_date_label_pt(coerced)
        return (
            f"Para '{service_query}' em {when} não há horários livres. "
            "Quer tentar outra data?"
        )
    return f"{summary}\n\nQual horário você prefere? (horário de Brasília)"


def extract_patient_name(text: str) -> str | None:
    for pattern in _NAME_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        name, err = sanitize_text_field(match.group(1).strip(), 80)
        if name and not err:
            return name
    return None


def is_date_reaffirmation(text: str, date_iso: str | None) -> bool:
    if not date_iso:
        return False
    extracted = extract_booking_date_from_text(text, reference=date.today())
    return extracted == date_iso and len(text.strip()) < 48


def extract_patient_phone(text: str) -> str | None:
    digits = re.findall(r"\d{10,13}", text)
    for raw in reversed(digits):
        phone, err = validate_phone(raw)
        if phone and not err:
            return phone
    return None


def _guess_service_query(combined: str, org_id: str, *, prefer_exact: bool = False) -> str | None:
    catalog = list_catalog_services(org_id)
    if not catalog:
        return None
    cleaned = combined.strip()
    if prefer_exact or len(cleaned) <= 48:
        service, err = resolve_service_from_catalog(org_id, cleaned, catalog=catalog)
        if service and not err:
            return service["name"]
    combined_norm = combined.lower()
    for row in catalog:
        if row["name"].lower() in combined_norm:
            return row["name"]
    for synonym in _SERVICE_SEARCH_SYNONYMS:
        if synonym in combined_norm:
            service, err = resolve_service_from_catalog(org_id, synonym, catalog=catalog)
            if service and not err:
                return service["name"]
    for hint in ("corte masculino", "corte feminino", "coloracao", "coloração", "manicure", "barba", "hidrat"):
        if hint in combined_norm:
            service, err = resolve_service_from_catalog(org_id, hint, catalog=catalog)
            if service and not err:
                return service["name"]
    return None


_DATE_CLARIFY_HINTS = (
    "qual dia",
    "que dia",
    "para qual dia",
    "mas para qual",
    "foi para qual",
    "eh para qual",
    "é para qual",
)


def _is_date_clarification_question(text: str) -> bool:
    t = text.lower().strip()
    if len(t) > 72:
        return False
    return any(hint in t for hint in _DATE_CLARIFY_HINTS)


def _is_catalog_service_reply(text: str, org_id: str) -> bool:
    """True when the message is a direct pick from the service catalog (e.g. 'Corte masculino')."""
    return _guess_service_query(text, org_id, prefer_exact=True) is not None


def _booking_slots_locked(
    *,
    booking_date: str | None,
    booking_service: str | None,
    booking_time: str | None,
) -> bool:
    return bool(booking_date and booking_service and booking_time)


def _resolve_intent_date(
    *,
    last: str,
    combined: str,
    reference: date,
    booking_date: str | None,
    ctx_date: str | None,
) -> str | None:
    if booking_date:
        return _coerce_booking_date(booking_date, reference=reference) or booking_date
    if ctx_date:
        return ctx_date
    last_iso = extract_booking_date_from_text(last, reference=reference)
    if last_iso:
        return last_iso
    return extract_booking_date_from_text(combined, reference=reference)


def collect_booking_intent(
    messages: Sequence[BaseMessage],
    org_id: str,
    *,
    booking_date: str | None = None,
    booking_service: str | None = None,
    booking_time: str | None = None,
    booking_patient_name: str | None = None,
    booking_patient_phone: str | None = None,
) -> BookingIntent | None:
    texts = _human_texts(messages)
    if not texts:
        return None

    combined = " ".join(texts)
    last = texts[-1]
    ref = date.today()

    ctx_date, ctx_service, _clarification = resolve_booking_context(
        messages, org_id, booking_date=booking_date, booking_service=booking_service
    )

    locked = _booking_slots_locked(
        booking_date=booking_date,
        booking_service=booking_service,
        booking_time=booking_time,
    )

    if locked:
        date_iso = _coerce_booking_date(booking_date, reference=ref) or booking_date
        service_query = booking_service
        time_hhmm = booking_time
        patient_phone = extract_patient_phone(last) or booking_patient_phone
        patient_name = extract_patient_name(last) or booking_patient_name
    else:
        date_iso = _resolve_intent_date(
            last=last,
            combined=combined,
            reference=ref,
            booking_date=booking_date,
            ctx_date=ctx_date,
        )
        service_query = (
            _guess_service_query(last, org_id, prefer_exact=True)
            or _guess_service_query(combined, org_id)
            or ctx_service
            or booking_service
        )
        time_hhmm = (
            extract_booking_time_from_text(last)
            or booking_time
            or extract_booking_time_from_text(combined)
        )
        patient_phone = (
            extract_patient_phone(last)
            or extract_patient_phone(combined)
            or booking_patient_phone
        )
        patient_name = (
            extract_patient_name(last)
            or booking_patient_name
            or extract_patient_name(combined)
        )

    if not all([date_iso, time_hhmm, patient_phone, patient_name, service_query]):
        return None

    return BookingIntent(
        service_query=service_query,
        date_iso=date_iso,
        time_hhmm=time_hhmm,
        patient_name=patient_name,
        patient_phone=patient_phone,
    )


_catalog_service_prompt = catalog_service_prompt


async def _execute_booking_safe(intent: BookingIntent, config: RunnableConfig) -> SchedulingTurnResult:
    try:
        msg = await execute_booking(intent, config)
        return SchedulingTurnResult(
            message=msg,
            booking_date=intent.date_iso,
            booking_service=intent.service_query,
            booking_time=intent.time_hhmm,
            booking_patient_name=intent.patient_name,
            booking_patient_phone=intent.patient_phone,
        )
    except Exception as exc:
        from packages.auth_core.exceptions import BusinessLogicError, DoubleBookingError

        if isinstance(exc, DoubleBookingError):
            summary = await fetch_availability_summary(intent.service_query, intent.date_iso, config)
            msg = (
                "Esse horário acabou de ser ocupado.\n\n"
                f"{summary}\n\nQual outro horário prefere?"
            )
        elif isinstance(exc, BusinessLogicError):
            msg = str(exc)
        else:
            logger.exception("execute_booking failed")
            msg = "Não consegui concluir o agendamento agora. Tente novamente em instantes."
        return SchedulingTurnResult(
            message=msg,
            booking_date=intent.date_iso,
            booking_service=intent.service_query,
            booking_time=intent.time_hhmm,
            booking_patient_name=intent.patient_name,
            booking_patient_phone=intent.patient_phone,
        )


async def _handle_time_selection(
    messages: Sequence[BaseMessage],
    org_id: str,
    config: RunnableConfig,
    date_iso: str,
    service_query: str,
    time_hhmm: str,
) -> SchedulingTurnResult:
    texts = _human_texts(messages)
    last = texts[-1] if texts else ""
    combined = " ".join(texts)
    patient_name = extract_patient_name(last) or extract_patient_name(combined)
    patient_phone = extract_patient_phone(last) or extract_patient_phone(combined)

    if patient_name and patient_phone:
        intent = BookingIntent(
            service_query=service_query,
            date_iso=date_iso,
            time_hhmm=time_hhmm,
            patient_name=patient_name,
            patient_phone=patient_phone,
        )
        return await _execute_booking_safe(intent, config)

    return SchedulingTurnResult(
        message=(
            f"Anotei {service_query} no dia {date_iso} às {time_hhmm}. "
            "Para confirmar, me informe seu nome completo e telefone com DDD."
        ),
        booking_date=date_iso,
        booking_service=service_query,
        booking_time=time_hhmm,
        booking_patient_name=patient_name,
        booking_patient_phone=patient_phone,
    )


async def fetch_availability_summary(
    service_query: str,
    date_iso: str,
    config: RunnableConfig,
) -> str:
    from packages.scheduling.tools import check_availability

    return await check_availability.ainvoke(
        {"service_name": service_query, "target_date": date_iso},
        config=config,
    )


async def execute_booking(intent: BookingIntent, config: RunnableConfig) -> str:
    from packages.scheduling.tools import _get_configurable, _resolve_professional_for_datetime

    cfg = _get_configurable(config)
    org_id = cfg.get("org_id")
    if not org_id:
        return "Erro interno de tenant."

    phone_resolved, _ = resolve_booking_phone(intent.patient_phone, cfg)
    if not phone_resolved:
        return "Telefone inválido para agendamento."

    sched_service = SchedulingService()
    tzname = sched_service._get_org_config()["timezone"]
    local_dt_str = build_local_datetime(intent.date_iso, intent.time_hhmm)
    local_naive, _, dt_err = parse_booking_datetime(local_dt_str, tzname, assume_local_wall_clock=True)
    if dt_err or not local_naive:
        return "Horário inválido para agendamento."

    service_data, svc_err = resolve_service_from_catalog(org_id, intent.service_query)
    if svc_err or not service_data:
        return f"Serviço '{intent.service_query}' não encontrado."

    from packages.scheduling.eligibility import list_eligible_professionals

    eligible = list_eligible_professionals(
        org_id,
        service_data["id"],
        service_data.get("professional_id"),
    )
    professional_id = await _resolve_professional_for_datetime(
        org_id,
        service_data,
        local_dt_str,
        intent.professional_name,
        sched_service,
        tzname=tzname,
    )
    if not professional_id:
        summary = await fetch_availability_summary(intent.service_query, intent.date_iso, config)
        return (
            f"O horário {intent.time_hhmm} (Brasília) não está livre para '{service_data['name']}' "
            f"em {intent.date_iso}.\n\n{summary}\n\nQual horário você prefere?"
        )

    patient_id = upsert_patient_by_phone(org_id, intent.patient_name, phone_resolved)
    if not patient_id:
        return "Erro ao cadastrar o cliente."

    appointment = AppointmentBase(
        patient_id=UUID(patient_id),
        professional_id=UUID(professional_id),
        service_id=UUID(service_data["id"]),
        scheduled_at=local_naive,
        duration_minutes=service_data["duration_minutes"],
        status=AppointmentStatus.CONFIRMED,
    )
    await sched_service.create_appointment(appointment)

    pro_name = next(
        (pro["name"] for pro in eligible if pro["id"] == str(professional_id)),
        None,
    )
    label = format_local_datetime_label(local_naive, tzname)
    if pro_name:
        return (
            f"SUCESSO! Agendamento confirmado para {intent.patient_name}: "
            f"'{service_data['name']}' com {pro_name} em {label}."
        )
    return (
        f"SUCESSO! Agendamento confirmado para {intent.patient_name}: "
        f"'{service_data['name']}' em {label}."
    )


async def run_scheduling_turn(
    messages: Sequence[BaseMessage],
    config: RunnableConfig,
    *,
    booking_date: str | None = None,
    booking_service: str | None = None,
    booking_time: str | None = None,
    booking_patient_name: str | None = None,
    booking_patient_phone: str | None = None,
    booking_step: str | None = None,
    checkpoint: BookingStateSnapshot | None = None,
) -> SchedulingTurnResult | None:
    """Handle booking turns in code — LLM only when data is incomplete."""
    org_id = (config.get("configurable") or {}).get("org_id")
    if not org_id:
        return None

    with set_tenant_context(org_id):
        if checkpoint:
            date_iso = checkpoint.booking_date
            service_query = checkpoint.booking_service
            clarification = (
                checkpoint.clarification if has_open_date_clarification(checkpoint) else None
            )
            booking_time = checkpoint.booking_time or booking_time
            booking_date = checkpoint.booking_date or booking_date
            booking_service = checkpoint.booking_service or booking_service
        else:
            date_iso, service_query, clarification = resolve_booking_context(
                messages,
                org_id,
                booking_date=booking_date,
                booking_service=booking_service,
            )

        texts = _human_texts(messages)
        last = texts[-1] if texts else ""
        ref = date.today()

        if not texts:
            return None

        checkpoint_prompt = (
            get_checkpoint_clarification_message(checkpoint, last)
            if checkpoint
            else None
        )
        if checkpoint_prompt and service_query and not date_iso:
            return SchedulingTurnResult(
                message=checkpoint_prompt,
                booking_service=service_query,
            )

        if clarification and service_query and not date_iso:
            return SchedulingTurnResult(
                message=clarification,
                booking_service=service_query,
            )
        if clarification and not service_query and not date_iso:
            return SchedulingTurnResult(message=clarification)

        if (
            clarification
            and date_iso
            and service_query
            and is_date_choice_opinion_question(last)
        ):
            return SchedulingTurnResult(
                message=clarification,
                booking_service=service_query,
            )

        if is_booking_confirmed_in_thread(messages):
            if is_post_booking_closing(last):
                return SchedulingTurnResult(
                    message=(
                        "Por nada! Ficamos felizes em ajudar. "
                        "Se precisar de mais alguma coisa, é só chamar!"
                    ),
                )
            if not wants_new_booking_after_confirm(last):
                return None

        time_hhmm = extract_booking_time_from_text(last) or booking_time
        time_in_last = bool(extract_booking_time_from_text(last))

        intent = collect_booking_intent(
            messages,
            org_id,
            booking_date=booking_date,
            booking_service=booking_service,
            booking_time=booking_time,
            booking_patient_name=booking_patient_name,
            booking_patient_phone=booking_patient_phone,
        )
        if intent:
            return await _execute_booking_safe(intent, config)

        if date_iso and service_query and time_hhmm:
            return await _handle_time_selection(
                messages, org_id, config, date_iso, service_query, time_hhmm
            )

        _, offered_times = extract_offered_slots_from_thread(messages)
        if (
            date_iso
            and service_query
            and not time_hhmm
            and offered_times
            and is_date_confirmation_without_new_time(last, date_iso)
        ):
            return SchedulingTurnResult(
                message=build_date_confirmed_prompt(date_iso, service_query),
                booking_date=date_iso,
                booking_service=service_query,
            )

        if date_iso and service_query and (
            _is_catalog_service_reply(last, org_id)
            or _is_date_clarification_question(last)
            or is_availability_followup(last, has_time_in_message=time_in_last)
            or is_date_reaffirmation(last, date_iso)
            or (
                not time_hhmm
                and (
                    has_scheduling_intent(last)
                    or has_implicit_scheduling_intent(last)
                    or has_temporal_scheduling_intent(last)
                )
            )
        ):
            msg = await format_availability_reply(service_query, date_iso, config)
            return SchedulingTurnResult(
                message=msg,
                booking_date=date_iso,
                booking_service=service_query,
            )

        if date_iso and not service_query:
            return SchedulingTurnResult(
                message=_catalog_service_prompt(org_id, date_iso=date_iso),
                booking_date=date_iso,
            )

        if service_query and not date_iso:
            past_msg = _past_booking_date_message(last, reference=ref)
            if past_msg:
                return SchedulingTurnResult(message=past_msg, booking_service=service_query)
            return SchedulingTurnResult(
                message=f"Para qual data você quer agendar {service_query}?",
                booking_service=service_query,
            )

        if not date_iso and not service_query and len(texts) >= 1:
            return SchedulingTurnResult(message=_catalog_service_prompt(org_id))

        if checkpoint and has_open_date_clarification(checkpoint):
            return None

        recovery = await try_flow_recovery_turn(
            messages,
            config,
            booking_date=date_iso or booking_date,
            booking_service=service_query or booking_service,
            booking_time=booking_time,
            booking_patient_name=booking_patient_name,
            booking_patient_phone=booking_patient_phone,
            booking_step=booking_step,
            pending_clarification=checkpoint.pending_clarification if checkpoint else None,
        )
        if recovery:
            return recovery

    return None


async def try_deterministic_booking(messages: Sequence[BaseMessage], config: RunnableConfig) -> str | None:
    result = await run_scheduling_turn(messages, config)
    return result.message if result else None
