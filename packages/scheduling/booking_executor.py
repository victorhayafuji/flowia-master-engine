"""Deterministic booking — bypasses LLM datetime formatting mistakes."""
from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig

from packages.auth_core.tenant import set_tenant_context
from packages.engine.routing import message_text
from packages.models.enums import AppointmentStatus
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

_NAME_PATTERNS = (
    re.compile(
        r"(?:meu nome(?:\s+e|\s+é)|me chamo|sou(?:\s+o|\s+a)?)\s+"
        r"([A-Za-zÀ-ú'\s]{2,60}?)(?:,|\s+telefone|\s+tel|\s+phone|\d{10,}|$)",
        re.I,
    ),
    re.compile(
        r"(?:,\s*|\s+)([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)?)\s*,\s*(?:telefone\s+)?(\d{10,13})\b",
        re.I,
    ),
)


@dataclass
class BookingIntent:
    service_query: str
    date_iso: str
    time_hhmm: str
    patient_name: str
    patient_phone: str
    professional_name: str | None = None


@dataclass
class SchedulingTurnResult:
    message: str
    booking_date: str | None = None
    booking_service: str | None = None


_AVAILABILITY_FOLLOWUP_PHRASES = (
    "outro hor",
    "outra hor",
    "tem hor",
    "tem vaga",
    "algum hor",
    "disponib",
    "horarios",
    "horários",
    "qual hor",
    "pode ser",
    "prefiro",
)


def is_availability_followup(text: str, *, has_time_in_message: bool = False) -> bool:
    t = text.lower().strip()
    if has_time_in_message:
        return any(phrase in t for phrase in _AVAILABILITY_FOLLOWUP_PHRASES)
    if t in {"sim", "s", "ok", "pode", "claro", "quero"}:
        return True
    return any(phrase in t for phrase in _AVAILABILITY_FOLLOWUP_PHRASES)


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
        text = message_text(msg).lower()
        for row in catalog:
            if row["name"].lower() in text:
                return row["name"]
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


def resolve_booking_context(
    messages: Sequence[BaseMessage],
    org_id: str,
    *,
    booking_date: str | None = None,
    booking_service: str | None = None,
) -> tuple[str | None, str | None]:
    texts = _human_texts(messages)
    combined = " ".join(texts)
    last = texts[-1] if texts else ""
    ref = date.today()

    date_iso = (
        extract_booking_date_from_text(last, reference=ref)
        or extract_booking_date_from_text(combined, reference=ref)
        or _coerce_booking_date(booking_date, reference=ref)
    )
    service_query = (
        _guess_service_query(combined, org_id)
        or _guess_service_query(last, org_id)
        or _extract_service_from_thread(messages, org_id)
        or booking_service
    )
    return date_iso, service_query


async def format_availability_reply(service_query: str, date_iso: str, config: RunnableConfig) -> str:
    coerced = _coerce_booking_date(date_iso)
    if not coerced:
        return (
            "Data inválida para agendamento. "
            "Informe o dia claramente (ex: sexta-feira, 10 de junho ou 2026-06-10)."
        )
    summary = await fetch_availability_summary(service_query, coerced, config)
    if summary.startswith("Não há horários"):
        return (
            f"Para '{service_query}' em {coerced} não há horários livres. "
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
    extracted = extract_booking_date_from_text(text)
    return extracted == date_iso and len(text.strip()) < 48


def extract_patient_phone(text: str) -> str | None:
    digits = re.findall(r"\d{10,13}", text)
    for raw in reversed(digits):
        phone, err = validate_phone(raw)
        if phone and not err:
            return phone
    return None


def _guess_service_query(combined: str, org_id: str) -> str | None:
    catalog = list_catalog_services(org_id)
    if not catalog:
        return None
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


def collect_booking_intent(
    messages: Sequence[BaseMessage],
    org_id: str,
    *,
    booking_date: str | None = None,
    booking_service: str | None = None,
) -> BookingIntent | None:
    texts = _human_texts(messages)
    if not texts:
        return None

    combined = " ".join(texts)
    last = texts[-1]

    ctx_date, ctx_service = resolve_booking_context(
        messages, org_id, booking_date=booking_date, booking_service=booking_service
    )
    date_iso = extract_booking_date_from_text(combined) or ctx_date
    service_query = _guess_service_query(combined, org_id) or ctx_service
    time_hhmm = extract_booking_time_from_text(last) or extract_booking_time_from_text(combined)
    patient_phone = extract_patient_phone(combined)
    patient_name = extract_patient_name(combined)

    if not all([date_iso, time_hhmm, patient_phone, patient_name, service_query]):
        return None

    return BookingIntent(
        service_query=service_query,
        date_iso=date_iso,
        time_hhmm=time_hhmm,
        patient_name=patient_name,
        patient_phone=patient_phone,
    )


def _catalog_service_prompt(org_id: str) -> str:
    catalog = list_catalog_services(org_id)
    if not catalog:
        return "Qual serviço você gostaria de agendar?"
    names = ", ".join(row["name"] for row in catalog[:6])
    return f"Qual serviço deseja agendar? Temos: {names}."


async def _execute_booking_safe(intent: BookingIntent, config: RunnableConfig) -> SchedulingTurnResult:
    try:
        msg = await execute_booking(intent, config)
        return SchedulingTurnResult(
            message=msg,
            booking_date=intent.date_iso,
            booking_service=intent.service_query,
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
        )


async def _handle_time_selection(
    messages: Sequence[BaseMessage],
    org_id: str,
    config: RunnableConfig,
    date_iso: str,
    service_query: str,
    time_hhmm: str,
) -> SchedulingTurnResult:
    combined = " ".join(_human_texts(messages))
    patient_name = extract_patient_name(combined)
    patient_phone = extract_patient_phone(combined)

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

    label = format_local_datetime_label(local_naive, tzname)
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
) -> SchedulingTurnResult | None:
    """Handle booking turns in code — LLM only when data is incomplete."""
    org_id = (config.get("configurable") or {}).get("org_id")
    if not org_id:
        return None

    with set_tenant_context(org_id):
        date_iso, service_query = resolve_booking_context(
            messages, org_id, booking_date=booking_date, booking_service=booking_service
        )

        texts = _human_texts(messages)
        last = texts[-1] if texts else ""

        if not texts:
            return None
        time_hhmm = extract_booking_time_from_text(last)
        time_in_last = bool(time_hhmm)

        intent = collect_booking_intent(
            messages,
            org_id,
            booking_date=booking_date,
            booking_service=booking_service,
        )
        if intent:
            return await _execute_booking_safe(intent, config)

        if date_iso and service_query and time_hhmm:
            return await _handle_time_selection(
                messages, org_id, config, date_iso, service_query, time_hhmm
            )

        if date_iso and service_query and (
            is_availability_followup(last, has_time_in_message=time_in_last)
            or is_date_reaffirmation(last, date_iso)
        ):
            msg = await format_availability_reply(service_query, date_iso, config)
            return SchedulingTurnResult(
                message=msg,
                booking_date=date_iso,
                booking_service=service_query,
            )

        if date_iso and service_query and (
            not time_hhmm
            or is_availability_followup(last, has_time_in_message=time_in_last)
            or is_date_reaffirmation(last, date_iso)
        ):
            msg = await format_availability_reply(service_query, date_iso, config)
            return SchedulingTurnResult(
                message=msg,
                booking_date=date_iso,
                booking_service=service_query,
            )

        if date_iso and not service_query:
            return SchedulingTurnResult(
                message=_catalog_service_prompt(org_id),
                booking_date=date_iso,
            )

        if service_query and not date_iso:
            return SchedulingTurnResult(
                message=f"Para qual data você quer agendar {service_query}?",
                booking_service=service_query,
            )

        if not date_iso and not service_query and len(texts) >= 1:
            return SchedulingTurnResult(message=_catalog_service_prompt(org_id))

    return None


async def try_deterministic_booking(messages: Sequence[BaseMessage], config: RunnableConfig) -> str | None:
    result = await run_scheduling_turn(messages, config)
    return result.message if result else None
