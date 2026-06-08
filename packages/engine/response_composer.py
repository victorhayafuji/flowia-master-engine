"""Compose natural scheduling replies from factual executor output + optional polish."""
from __future__ import annotations

import logging
import re
from datetime import date

from langchain_google_genai import ChatGoogleGenerativeAI

from packages.auth_core.config import settings

logger = logging.getLogger(__name__)

_TIME_PATTERN = re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b")
_DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

_WEEKDAY_PT = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)


def format_date_label_pt(date_iso: str) -> str:
    parsed = date.fromisoformat(date_iso)
    weekday = _WEEKDAY_PT[parsed.weekday()]
    return f"{weekday}, {parsed.strftime('%d/%m')}"


def build_template_acknowledgment(
    *,
    salon_name: str,
    booking_service: str | None = None,
    booking_date: str | None = None,
    user_message: str = "",
) -> str | None:
    """Zero-token empathetic opener when the LLM extractor did not run."""
    msg = user_message.lower().strip()
    date_label = format_date_label_pt(booking_date) if booking_date else None

    if "mecha" in msg or "luzes" in msg or "balayage" in msg:
        when = f" na {date_label}" if date_label else ""
        return f"Claro! Vamos agendar suas mechas{when}."

    if booking_service and date_label:
        return f"Perfeito! Separei a agenda de {date_label} para você:"

    if booking_service:
        return f"Ótimo! Sobre {booking_service}, me conta para qual data você prefere?"

    if date_label:
        return f"Certo! Para {date_label}, qual serviço você gostaria de fazer?"

    if msg and any(w in msg for w in ("agendar", "marcar", "horário", "horario", "vaga")):
        name = salon_name or "salão"
        return f"Com prazer! Vou te ajudar a agendar no {name}."

    return None


_MAX_SLOTS_PER_ROW = 3

def _parse_professional_slot_line(line: str) -> tuple[str, list[str]] | None:
    """Parse 'Ana Costa: 13:00, 13:15, ...' into name + ordered unique times."""
    if ":" not in line:
        return None
    name, rest = line.split(":", 1)
    name = name.strip()
    times = _TIME_PATTERN.findall(rest)
    if not name or not times:
        return None
    seen: set[str] = set()
    ordered: list[str] = []
    for t in times:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return name, ordered


def format_time_grid(times: list[str], *, per_row: int = _MAX_SLOTS_PER_ROW) -> str:
    """Multi-line bullet grid — scannable on WhatsApp and Chat Test."""
    if not times:
        return ""
    rows: list[str] = []
    for i in range(0, len(times), per_row):
        chunk = times[i : i + per_row]
        rows.append("  • " + "   • ".join(chunk))
    return "\n".join(rows)


def format_availability_blocks(slot_lines: list[str]) -> str:
    """Turn tool output lines into a structured, human-readable availability block."""
    professionals: list[tuple[str, list[str]]] = []
    for line in slot_lines:
        parsed = _parse_professional_slot_line(line)
        if parsed:
            professionals.append(parsed)

    if not professionals:
        return ""

    if len(professionals) == 1:
        name, times = professionals[0]
        if len(times) == 1:
            body = f"Tenho {times[0]} com {name}."
        else:
            body = f"Com {name}, estes horários estão livres:\n{format_time_grid(times)}"
    else:
        chunks = []
        for name, times in professionals:
            chunks.append(f"Com {name}:\n{format_time_grid(times)}")
        body = "\n\n".join(chunks)

    return f"{body}\n\nQual horário funciona melhor para você?"


def humanize_scheduling_factual(
    factual: str,
    *,
    booking_service: str | None = None,
    booking_date: str | None = None,
) -> str:
    """Soften executor/tool wording while preserving every slot time."""
    text = factual.strip()
    lower = text.lower()

    if (
        "qual horário você prefere" in lower
        or "qual horario voce prefere" in lower
        or "horários para" in lower
    ):
        slot_lines = [
            line.lstrip("- ").strip()
            for line in text.splitlines()
            if line.strip().startswith("-") and _TIME_PATTERN.search(line)
        ]
        formatted = format_availability_blocks(slot_lines)
        if formatted:
            return formatted

    if "anotei" in lower and _TIME_PATTERN.search(text):
        match = re.search(
            r"anotei\s+(.+?)\s+no dia\s+(\d{4}-\d{2}-\d{2})\s+[àa]s\s+(\d{1,2}:\d{2})",
            text,
            re.I,
        )
        if match:
            service = match.group(1).strip()
            time_hhmm = match.group(3)
            date_label = format_date_label_pt(match.group(2))
            return (
                f"Anotei {service} para {date_label} às {time_hhmm}.\n\n"
                "Para finalizar, me passa seu nome completo e WhatsApp com DDD, por favor?"
            )

    if "nome completo e telefone" in lower or "whatsapp com ddd" in lower:
        return re.sub(
            r"Para confirmar, me informe seu nome completo e telefone com DDD\.",
            "Para finalizar, me passa seu nome completo e WhatsApp com DDD, por favor?",
            text,
            flags=re.I,
        )

    if text.upper().startswith("SUCESSO"):
        human = text.replace("SUCESSO! ", "", 1)
        human = human.replace("Agendamento confirmado", "Seu horário está confirmado", 1)
        return f"Pronto! {human}".strip()

    if "não há horários livres" in lower or "nao ha horarios livres" in lower:
        when = format_date_label_pt(booking_date) if booking_date else "essa data"
        service = booking_service or "esse serviço"
        return (
            f"Poxa, não encontrei horários livres para {service} em {when}. "
            "Quer tentar outro dia?"
        )

    return text


def _extract_factual_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    tokens.update(_TIME_PATTERN.findall(text))
    tokens.update(_DATE_PATTERN.findall(text))
    return tokens


def factual_guard(polished: str, original_factual: str) -> bool:
    """All times/dates from factual block must appear in polished output."""
    required = _extract_factual_tokens(original_factual)
    if not required:
        return True
    return required.issubset(_extract_factual_tokens(polished))


def compose_scheduling_reply(
    factual: str,
    user_acknowledgment: str | None = None,
    *,
    salon_name: str = "",
    booking_service: str | None = None,
    booking_date: str | None = None,
    user_message: str = "",
) -> str:
    human_factual = humanize_scheduling_factual(
        factual,
        booking_service=booking_service,
        booking_date=booking_date,
    )
    ack = user_acknowledgment or build_template_acknowledgment(
        salon_name=salon_name,
        booking_service=booking_service,
        booking_date=booking_date,
        user_message=user_message,
    )
    if ack:
        ack = ack.strip()
        if ack and ack not in human_factual:
            return f"{ack}\n\n{human_factual.strip()}"
    return human_factual.strip()


async def polish_scheduling_reply(
    composed: str,
    *,
    factual_source: str,
    salon_name: str = "",
) -> str:
    """Optional LLM polish with fail-closed factual validation."""
    if not settings.RESPONSE_POLISH_ENABLED:
        return composed

    llm = ChatGoogleGenerativeAI(
        model=settings.MODEL_NAME,
        temperature=0.3,
        google_api_key=settings.GOOGLE_API_KEY,
    )
    prompt = (
        f"Reescreva a resposta do assistente do {salon_name or 'salão'} de forma natural e cordial. "
        "Mantenha TODOS os horários (HH:MM) e datas exatamente iguais. "
        "Não invente novos horários, preços ou políticas. "
        "Máximo 4 frases curtas.\n\n"
        f"Resposta:\n{composed}"
    )
    try:
        result = await llm.ainvoke(prompt)
        polished = getattr(result, "content", str(result)).strip()
        if polished and factual_guard(polished, factual_source):
            return polished
        logger.warning("Polish rejected — factual guard failed")
    except Exception:
        logger.exception("polish_scheduling_reply failed")
    return composed
