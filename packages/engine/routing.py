"""Intent detection for salon agent triage."""
from __future__ import annotations

import re

from langchain_core.messages import BaseMessage

_SCHEDULING_KEYWORDS = (
    "agendar",
    "agendamento",
    "marcar",
    "marcação",
    "marcacao",
    "reservar",
    "reserva",
    "horário",
    "horario",
    "disponib",
    "tem vaga",
    "tem hor",
    "quero uma vaga",
)

_SUPPORT_KEYWORDS = (
    "cancelar",
    "cancelamento",
    "política",
    "politica",
    "atraso",
    "atrasar",
    "pagamento",
    "estacionamento",
    "alergia",
)

_MENU_SCHEDULING = frozenset({"1", "agendar", "marcar", "agendamento", "horario", "horário"})
_MENU_RECEPTIONIST = frozenset({"2", "duvida", "dúvida", "preco", "preço", "valor", "servico", "serviço"})
_MENU_SUPPORT = frozenset({"3", "politica", "política", "cancelar", "atraso", "pagamento"})

_WEEKDAY_HINTS = (
    "segunda",
    "terça",
    "terca",
    "quarta",
    "quinta",
    "sexta",
    "sábado",
    "sabado",
    "domingo",
    "amanhã",
    "amanha",
    "hoje",
)

_TEMPORAL_HINTS = (
    "semana que vem",
    "semana proxima",
    "semana próxima",
    "proxima semana",
    "próxima semana",
    "esse sabado",
    "esse sábado",
    "essa semana",
    "de tarde",
    "de manha",
    "de manhã",
)

_BOOKING_VISIT_HINTS = (
    "preciso ir",
    "quero ir",
    "da pra",
    "dá pra",
    "encaixar",
    "encaixa",
    "vir ai",
    "vir aí",
)

_EXECUTOR_AI_HINTS = (
    "qual horário",
    "qual horario",
    "horários disponíveis",
    "horarios disponiveis",
    "horario preferido",
    "qual horário você prefere",
    "qual horario voce prefere",
    "nome completo e telefone",
    "telefone com ddd",
    "para confirmar",
    "anotei",
    "qual desses horários",
    "qual desses horarios",
    "horário de brasília",
    "horario de brasilia",
)

_SERVICE_HINTS = (
    "color",
    "corte",
    "manicure",
    "pedicure",
    "escova",
    "hidrat",
    "progressiva",
    "barba",
    "sobrancelha",
    "depila",
    "mechas",
    "retoque",
)

_PHONE_PATTERN = re.compile(r"\d{10,13}")
_TIME_PATTERN = re.compile(r"\d{1,2}:\d{2}|(?:às|as)\s*\d{1,2}")


def _normalize(text: str) -> str:
    return text.lower().strip()


def message_text(message: BaseMessage) -> str:
    """Extract plain text from HumanMessage/AIMessage content (str or Gemini blocks)."""
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text", "")))
            else:
                parts.append(str(block))
        return " ".join(p for p in parts if p)
    return str(content or "")


def has_scheduling_intent(text: str) -> bool:
    t = _normalize(text)
    return any(keyword in t for keyword in _SCHEDULING_KEYWORDS)


def has_support_intent(text: str) -> bool:
    t = _normalize(text)
    return any(keyword in t for keyword in _SUPPORT_KEYWORDS)


def has_implicit_scheduling_intent(text: str) -> bool:
    """Service + date/day without explicit 'agendar' (e.g. 'coloração na sexta')."""
    t = _normalize(text)
    has_day = (
        any(day in t for day in _WEEKDAY_HINTS)
        or any(day in t for day in _TEMPORAL_HINTS)
        or bool(re.search(r"\d{1,2}/\d{1,2}", t))
        or bool(re.search(r"\d{4}-\d{2}-\d{2}", t))
    )
    has_service = any(hint in t for hint in _SERVICE_HINTS)
    return has_day and has_service


def has_temporal_scheduling_intent(text: str) -> bool:
    """Colloquial visit + time window without explicit 'agendar'."""
    t = _normalize(text)
    has_temporal = any(h in t for h in _TEMPORAL_HINTS) or any(d in t for d in _WEEKDAY_HINTS)
    has_service = any(h in t for h in _SERVICE_HINTS)
    has_visit = any(v in t for v in _BOOKING_VISIT_HINTS) or has_scheduling_intent(t)
    return has_temporal and (has_service or has_visit)


def has_price_and_scheduling_intent(text: str) -> bool:
    """Price question combined with date/time/service → scheduling, not receptionist."""
    t = _normalize(text)
    has_price = any(p in t for p in ("quanto", "preço", "preco", "valor"))
    has_schedule = (
        has_scheduling_intent(t)
        or has_implicit_scheduling_intent(t)
        or has_temporal_scheduling_intent(t)
        or has_time_or_slot_question(t)
        or any(d in t for d in _WEEKDAY_HINTS)
        or any(h in t for h in _TEMPORAL_HINTS)
    )
    return has_price and has_schedule


def is_price_only_question(text: str) -> bool:
    """Pure price/info without scheduling signals."""
    t = _normalize(text)
    has_price = any(p in t for p in ("quanto", "preço", "preco", "valor", "custa"))
    if not has_price:
        return False
    return not (
        has_scheduling_intent(t)
        or has_implicit_scheduling_intent(t)
        or has_temporal_scheduling_intent(t)
        or has_time_or_slot_question(t)
    )


def has_time_or_slot_question(text: str) -> bool:
    t = _normalize(text)
    if _TIME_PATTERN.search(t):
        return True
    return any(
        phrase in t
        for phrase in (
            "tem hor",
            "tem vaga",
            "disponib",
            "pode ser",
            "esse hor",
            "prefiro",
        )
    )


def is_booking_data_reply(text: str) -> bool:
    """Name + phone reply mid booking flow."""
    t = _normalize(text)
    return bool(_PHONE_PATTERN.search(t))


def is_booking_conversation(messages: list[BaseMessage]) -> bool:
    """True when thread already discusses booking (e.g. receptionist mis-route)."""
    human_texts = [_normalize(message_text(m)) for m in messages if m.type == "human"]
    if not human_texts:
        return False

    combined = " ".join(human_texts)
    if has_scheduling_intent(combined) or has_implicit_scheduling_intent(combined):
        return True

    last = human_texts[-1]
    if is_booking_data_reply(last) or has_time_or_slot_question(last):
        return True

    booking_followups = ("quero fazer", "vou querer", "pode ser", "prefiro", "esse hor")
    if any(phrase in last for phrase in booking_followups):
        if any(
            word in combined
            for word in ("agendar", "marcar", "sexta", "sábado", "segunda", "horário", "horario", "color")
        ):
            return True

    for msg in reversed(messages[-8:]):
        if msg.type != "ai":
            continue
        ai = _normalize(message_text(msg))
        if any(phrase in ai for phrase in _EXECUTOR_AI_HINTS) or any(
            phrase in ai
            for phrase in (
                "agendar",
                "agendamento",
                "coloração",
                "coloracao",
                "horário",
                "horario",
                "telefone",
                "nome completo",
                "tipo de",
            )
        ):
            return True
    return False


def should_force_scheduling_route(
    messages: list[BaseMessage],
    *,
    booking_active: bool = False,
) -> bool:
    """True when thread must enter scheduling_node (skip receptionist LLM)."""
    if resolve_triage_agent(messages, None, booking_active=booking_active) == "scheduling":
        return True
    return is_booking_conversation(messages)


def triage_source_for(
    messages: list[BaseMessage],
    *,
    was_booking_active: bool = False,
) -> str:
    """How routing was decided: keyword, conversation, sticky, or llm."""
    if was_booking_active:
        human_msgs = [m for m in messages if m.type == "human"]
        if human_msgs and not is_price_only_question(message_text(human_msgs[-1])):
            return "sticky"
    if is_booking_conversation(messages):
        return "conversation"
    human_msgs = [m for m in messages if m.type == "human"]
    if human_msgs:
        last = message_text(human_msgs[-1])
        if (
            has_scheduling_intent(last)
            or has_implicit_scheduling_intent(last)
            or has_temporal_scheduling_intent(last)
            or has_price_and_scheduling_intent(last)
            or has_time_or_slot_question(last)
        ):
            return "keyword"
    return "llm"


def resolve_triage_agent(
    messages: list[BaseMessage],
    current_agent: str | None,
    *,
    booking_active: bool = False,
) -> str:
    """Returns target agent: scheduling, support, or receptionist."""
    human_msgs = [m for m in messages if m.type == "human"]
    if not human_msgs:
        return current_agent or "receptionist"

    last_human = _normalize(message_text(human_msgs[-1]))

    if last_human in _MENU_SCHEDULING:
        return "scheduling"
    if last_human in _MENU_SUPPORT:
        return "support"
    if last_human in _MENU_RECEPTIONIST:
        return "receptionist"

    if has_support_intent(last_human):
        return "support"

    if booking_active and not is_price_only_question(message_text(human_msgs[-1])):
        return "scheduling"

    if (
        has_scheduling_intent(last_human)
        or has_implicit_scheduling_intent(last_human)
        or has_temporal_scheduling_intent(last_human)
        or has_price_and_scheduling_intent(last_human)
        or has_time_or_slot_question(last_human)
        or is_booking_conversation(messages)
    ):
        return "scheduling"

    if current_agent == "scheduling":
        return "scheduling"

    if current_agent:
        return current_agent

    return "receptionist"
