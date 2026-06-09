"""Mid-flow booking memory — recover gracefully when the client digresses."""
from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from enum import Enum
from typing import TYPE_CHECKING

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig

from packages.engine.routing import message_text
from packages.scheduling.date_parsing import format_date_label_pt
from packages.scheduling.guardrails import extract_booking_date_from_text
from packages.scheduling.timezone_utils import extract_booking_time_from_text

if TYPE_CHECKING:
    from packages.scheduling.booking_executor import SchedulingTurnResult

_TIME_PATTERN = re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b")

_SLOTS_SHOWN_MARKERS = (
    "horários estão livres",
    "horarios estao livres",
    "qual horário funciona melhor",
    "qual horario funciona melhor",
    "horários para",
    "horarios para",
)

_PATIENT_DATA_MARKERS = (
    "nome completo",
    "whatsapp com ddd",
    "telefone com ddd",
    "me passa seu nome",
)

_RECOMMENDATION_HINTS = (
    "recomenda",
    "sugere",
    "indica",
    "melhor hor",
    "me ajuda a escolher",
    "nao sei",
    "não sei",
    "indecis",
    "qual voce prefere",
    "qual você prefere",
    "qual prefere",
)

_DATE_CHOICE_OPINION_HINTS = (
    "acha melhor",
    "acham melhor",
    "qual voce prefere",
    "qual você prefere",
    "qual prefere",
    "me recomenda",
    "me indica",
    "me sugere",
    "nao sei qual",
    "não sei qual",
    "voce escolhe",
    "você escolhe",
    "pode escolher",
    "decide voce",
    "decide você",
)

_DIGRESSION_GREETINGS = frozenset(
    {
        "oi",
        "ola",
        "olá",
        "bom dia",
        "boa tarde",
        "boa noite",
        "e ai",
        "e aí",
        "tudo bem",
    }
)


class BookingFlowStep(str, Enum):
    IDLE = "idle"
    NEED_DATE = "need_date"
    NEED_SERVICE = "need_service"
    AWAITING_TIME = "awaiting_time"
    AWAITING_PATIENT = "awaiting_patient"
    COMPLETE = "complete"


def infer_booking_flow_step(
    messages: Sequence[BaseMessage],
    *,
    booking_date: str | None,
    booking_service: str | None,
    booking_time: str | None = None,
    booking_patient_name: str | None = None,
    booking_patient_phone: str | None = None,
    booking_step: str | None = None,
) -> BookingFlowStep:
    if booking_step:
        try:
            return BookingFlowStep(booking_step)
        except ValueError:
            pass

    from packages.scheduling.booking_state_sync import derive_booking_step

    return derive_booking_step(
        messages,
        booking_date=booking_date,
        booking_service=booking_service,
        booking_time=booking_time,
        booking_patient_name=booking_patient_name,
        booking_patient_phone=booking_patient_phone,
    )


def _awaiting_patient_data(messages: Sequence[BaseMessage]) -> bool:
    for msg in reversed(messages):
        if getattr(msg, "type", None) != "ai":
            continue
        lower = message_text(msg).lower()
        if "anotei" in lower and any(marker in lower for marker in _PATIENT_DATA_MARKERS):
            return True
    return False


def extract_offered_slots_from_thread(
    messages: Sequence[BaseMessage],
) -> tuple[str | None, list[str]]:
    for msg in reversed(messages):
        if getattr(msg, "type", None) != "ai":
            continue
        text = message_text(msg)
        lower = text.lower()
        if not any(marker in lower for marker in _SLOTS_SHOWN_MARKERS):
            continue
        times = _ordered_unique_times(_TIME_PATTERN.findall(text))
        if not times:
            continue
        professional: str | None = None
        prof_match = re.search(r"Com\s+([^,\n]+),\s*estes hor", text, re.I)
        if prof_match:
            professional = prof_match.group(1).strip()
        return professional, times
    return None, []


def _ordered_unique_times(times: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for slot in times:
        if slot not in seen:
            seen.add(slot)
            ordered.append(slot)
    return ordered


def _parse_tool_slot_line(line: str) -> tuple[str, list[str]] | None:
    stripped = line.lstrip("- ").strip()
    if ":" not in stripped or not _TIME_PATTERN.search(stripped):
        return None
    name, rest = stripped.split(":", 1)
    name = name.strip()
    times = _ordered_unique_times(_TIME_PATTERN.findall(rest))
    if not name or not times:
        return None
    return name, times


def is_date_choice_opinion_question(text: str) -> bool:
    """True when the client asks the bot to pick between day options (not time slots)."""
    lower = text.lower().strip()
    if not lower:
        return False
    if "horario" in lower or "horário" in lower or "hora " in lower:
        return False
    if extract_booking_time_from_text(text):
        return False
    if any(hint in lower for hint in _DATE_CHOICE_OPINION_HINTS):
        return True
    if "?" in text and len(lower.split()) <= 8:
        if any(token in lower for token in ("melhor", "recomenda", "sugere", "indica")):
            return True
    return False


def build_date_choice_redirect_message(clarification_prompt: str) -> str:
    """Politely redirect day indecision back to the client without picking a date."""
    prompt = clarification_prompt.strip()
    if ":" in prompt:
        options = prompt.split(":", 1)[1].strip().rstrip("?")
        if options:
            return (
                f"Os dois dias funcionam por aqui! "
                f"Me diz qual prefere: {options}?"
            )
    return (
        "Os dois dias funcionam por aqui! "
        "Me diz qual prefere — "
        f"{prompt.rstrip('?')}?"
    )


def pick_recommended_time(times: list[str]) -> str:
    if not times:
        return ""
    scored: list[tuple[int, str]] = []
    for slot in times:
        hour, minute = slot.split(":")
        mins = int(hour) * 60 + int(minute)
        scored.append((mins, slot))
    sweet_spot = [slot for mins, slot in scored if 10 * 60 <= mins <= 12 * 60]
    if sweet_spot:
        return sweet_spot[0]
    preferred = [slot for mins, slot in scored if 9 * 60 <= mins <= 14 * 60]
    if preferred:
        return preferred[0]
    return times[0]


_DATE_CONFIRM_HINTS = (
    "podemos marcar",
    "pode ser",
    "pode marcar",
    "vamos marcar",
    "combinado",
    "fechado",
    "certo",
    "ok entao",
    "ok então",
    "ta bom",
    "tá bom",
)


def is_date_confirmation_without_new_time(text: str, date_iso: str | None) -> bool:
    """True when the client confirms the day without picking a new time slot."""
    if not date_iso:
        return False
    if extract_booking_time_from_text(text):
        return False

    from packages.scheduling.booking_executor import is_date_reaffirmation

    if is_date_reaffirmation(text, date_iso):
        return True

    lower = text.lower().strip()
    if not any(hint in lower for hint in _DATE_CONFIRM_HINTS):
        return False
    extracted = extract_booking_date_from_text(text, reference=date.today())
    return extracted == date_iso


def build_date_confirmed_prompt(date_iso: str, service: str | None = None) -> str:
    when = format_date_label_pt(date_iso)
    if service:
        return f"Perfeito! {service} na {when}. Qual horário funciona melhor para você?"
    return f"Perfeito! Na {when}, qual horário funciona melhor para você?"


def is_flow_digression(text: str, step: BookingFlowStep) -> bool:
    if step in {BookingFlowStep.IDLE, BookingFlowStep.COMPLETE}:
        return False

    cleaned = text.strip()
    if not cleaned:
        return False

    lower = cleaned.lower()

    if step == BookingFlowStep.AWAITING_TIME:
        if extract_booking_time_from_text(cleaned):
            return False
        if any(hint in lower for hint in _RECOMMENDATION_HINTS):
            return True
        if "?" in cleaned and any(
            token in lower for token in ("qual", "quanto", "como", "onde", "preco", "preço")
        ):
            return True
        if lower in _DIGRESSION_GREETINGS:
            return True
        if len(lower.split()) <= 4 and not any(char.isdigit() for char in lower):
            return True
        return False

    if step == BookingFlowStep.AWAITING_PATIENT:
        if "?" in cleaned or lower in _DIGRESSION_GREETINGS:
            return True
        return False

    if step in {BookingFlowStep.NEED_DATE, BookingFlowStep.NEED_SERVICE}:
        if lower in _DIGRESSION_GREETINGS or ("?" in cleaned and len(lower.split()) <= 8):
            return True

    return False


def _recommendation_intro(
    *,
    service: str,
    date_label: str,
    recommended: str,
    professional: str | None,
) -> str:
    pro_hint = f" com {professional}" if professional else ""
    return (
        f"Sem problemas! Para {service} em {date_label}, "
        f"sugiro {recommended}{pro_hint} — costuma ser um horário mais tranquilo."
    )


def _generic_recovery_intro(*, service: str, date_label: str) -> str:
    return (
        f"Claro! Vamos continuar seu agendamento de {service} para {date_label}."
    )


async def try_flow_recovery_turn(
    messages: Sequence[BaseMessage],
    config: RunnableConfig,
    *,
    booking_date: str | None,
    booking_service: str | None,
    booking_time: str | None = None,
    booking_patient_name: str | None = None,
    booking_patient_phone: str | None = None,
    booking_step: str | None = None,
    pending_clarification: str | None = None,
) -> SchedulingTurnResult | None:
    from packages.scheduling.booking_executor import SchedulingTurnResult as _SchedulingTurnResult

    if pending_clarification == "date":
        return None

    if not booking_date or not booking_service:
        return None

    texts = [
        message_text(m)
        for m in messages
        if getattr(m, "type", None) == "human" and message_text(m).strip()
    ]
    if not texts:
        return None

    last = texts[-1]
    step = infer_booking_flow_step(
        messages,
        booking_date=booking_date,
        booking_service=booking_service,
        booking_time=booking_time,
        booking_patient_name=booking_patient_name,
        booking_patient_phone=booking_patient_phone,
        booking_step=booking_step,
    )
    if not is_flow_digression(last, step):
        return None

    message = await build_flow_recovery_message(
        messages,
        config,
        booking_date=booking_date,
        booking_service=booking_service,
        user_text=last,
        step=step,
    )
    if not message:
        return None

    return _SchedulingTurnResult(
        message=message,
        booking_date=booking_date,
        booking_service=booking_service,
        booking_time=booking_time,
        booking_patient_name=booking_patient_name,
        booking_patient_phone=booking_patient_phone,
    )


async def build_flow_recovery_message(
    messages: Sequence[BaseMessage],
    config: RunnableConfig,
    *,
    booking_date: str,
    booking_service: str,
    user_text: str,
    step: BookingFlowStep,
) -> str | None:
    date_label = format_date_label_pt(booking_date)

    if step == BookingFlowStep.AWAITING_TIME:
        from packages.engine.response_composer import humanize_scheduling_factual
        from packages.scheduling.booking_executor import fetch_availability_summary

        professional, offered_times = extract_offered_slots_from_thread(messages)
        summary = await fetch_availability_summary(booking_service, booking_date, config)
        if summary.startswith("Não há horários"):
            return (
                f"Poxa, não encontrei horários livres para {booking_service} em {date_label}. "
                "Quer tentar outro dia?"
            )

        lower = user_text.lower()
        wants_recommendation = any(hint in lower for hint in _RECOMMENDATION_HINTS)
        if not offered_times:
            for line in summary.splitlines():
                parsed = _parse_tool_slot_line(line)
                if parsed:
                    professional = professional or parsed[0]
                    offered_times = parsed[1]
                    break

        recommended = pick_recommended_time(offered_times)
        if wants_recommendation and recommended:
            intro = _recommendation_intro(
                service=booking_service,
                date_label=date_label,
                recommended=recommended,
                professional=professional,
            )
        else:
            intro = _generic_recovery_intro(service=booking_service, date_label=date_label)

        factual = f"{summary}\n\nQual horário você prefere? (horário de Brasília)"
        slots = humanize_scheduling_factual(
            factual,
            booking_service=booking_service,
            booking_date=booking_date,
        )
        return f"{intro}\n\n{slots}"

    if step == BookingFlowStep.AWAITING_PATIENT:
        return (
            f"Sem problemas! Para confirmar {booking_service} em {date_label}, "
            "me passa seu nome completo e WhatsApp com DDD, por favor?"
        )

    if step == BookingFlowStep.NEED_DATE:
        if is_date_choice_opinion_question(user_text):
            from packages.scheduling.date_parsing import DateParseMode, resolve_date_detailed

            texts = [
                message_text(m)
                for m in messages
                if getattr(m, "type", None) == "human" and message_text(m).strip()
            ]
            combined = " ".join(texts)
            detailed = resolve_date_detailed(combined, mode=DateParseMode.BOOKING)
            if detailed and detailed.needs_clarification and detailed.clarification_prompt:
                return build_date_choice_redirect_message(detailed.clarification_prompt)
        return (
            f"Tudo bem! Para qual data você quer agendar {booking_service}?"
        )

    if step == BookingFlowStep.NEED_SERVICE:
        return (
            f"Claro! Para {date_label}, qual serviço você gostaria de fazer?"
        )

    return None
