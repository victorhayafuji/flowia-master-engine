"""Deterministic support turns for policies with reference dates (absence, cancel)."""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from langchain_core.messages import BaseMessage

from packages.auth_core.tenant import set_tenant_context
from packages.engine.routing import has_support_intent, message_text
from packages.engine.tools import search_kb
from packages.scheduling.date_parsing import DateParseMode, format_date_label_pt, resolve_date_detailed
from packages.scheduling.guardrails import extract_reference_date_from_text
from packages.scheduling.timezone_utils import org_today

_ABSENCE_HINTS = (
    "faltei",
    "nao fui",
    "não fui",
    "me atrasei",
    "atrasei",
    "atraso",
    "atrasar",
    "nao compareci",
    "não compareci",
    "faltou",
)

_CANCEL_WITH_DATE = re.compile(
    r"cancel",
    re.I,
)

_RESCHEDULE_HINTS = ("remarc", "reagend", "marcar de novo", "outro horario", "outro horário")


@dataclass
class SupportTurnResult:
    message: str
    reference_date: str | None = None


def has_absence_intent(text: str) -> bool:
    t = text.lower()
    return any(hint in t for hint in _ABSENCE_HINTS)


def has_cancel_and_reschedule_intent(text: str) -> bool:
    t = text.lower()
    if not _CANCEL_WITH_DATE.search(t):
        return False
    return any(hint in t for hint in _RESCHEDULE_HINTS)


def should_run_deterministic_support(
    messages: Sequence[BaseMessage], *, reference: date | None = None
) -> bool:
    human = [m for m in messages if getattr(m, "type", None) == "human"]
    if not human:
        return False
    last = message_text(human[-1])
    if not has_support_intent(last) and not has_absence_intent(last):
        return False
    if has_cancel_and_reschedule_intent(last):
        return True
    ref = reference or date.today()
    detailed = resolve_date_detailed(last, reference=ref, mode=DateParseMode.REFERENCE)
    if detailed and (detailed.iso or detailed.needs_clarification):
        return True
    return extract_reference_date_from_text(last, reference=ref) is not None


def _compose_support_reply(kb_result: str, *, date_iso: str, user_message: str) -> str:
    label = format_date_label_pt(date_iso)
    kb_text = kb_result.strip()
    if kb_text.startswith("Consulta inválida") or kb_text.startswith("Erro interno"):
        return (
            f"Entendi que você se refere a {label}. "
            "Não consegui consultar a política agora — vou pedir para a equipe te ajudar."
        )
    if "Nenhuma informação foi encontrada" in kb_text:
        return (
            f"Entendi que você se refere a {label}. "
            "Não encontrei a política específica na base — posso transferir para a equipe?"
        )

    summary = kb_text.split("\n\n")[0][:400]
    if has_absence_intent(user_message):
        opener = f"Sobre sua ausência em {label}: "
    elif _CANCEL_WITH_DATE.search(user_message):
        opener = f"Sobre o cancelamento referente a {label}: "
    else:
        opener = f"Referente a {label}: "
    return f"{opener}{summary}"


def _compose_ambiguous_support_reply(
    kb_result: str,
    *,
    clarification_prompt: str,
    user_message: str,
) -> str:
    kb_text = kb_result.strip()
    if kb_text.startswith("Consulta inválida") or kb_text.startswith("Erro interno"):
        policy = "Não consegui consultar a política agora."
    elif "Nenhuma informação foi encontrada" in kb_text:
        policy = "Consultei nossa base de políticas do salão."
    else:
        policy = kb_text.split("\n\n")[0][:280]

    if has_absence_intent(user_message):
        topic = "Sobre ausência/atraso"
    elif _CANCEL_WITH_DATE.search(user_message):
        topic = "Sobre cancelamento"
    else:
        topic = "Sobre sua dúvida"

    return f"{topic}: {policy}\n\n{clarification_prompt}"


def _multi_date_handoff_message() -> str:
    return (
        "Para cancelar um horário e remarcar em outro dia, preciso que a equipe "
        "confirme os dois passos com você. Posso pedir para alguém te atender?"
    )


def run_support_turn(
    messages: Sequence[BaseMessage],
    org_id: str,
) -> SupportTurnResult | None:
    human = [m for m in messages if getattr(m, "type", None) == "human"]
    if not human:
        return None
    last = message_text(human[-1])

    if has_cancel_and_reschedule_intent(last):
        return SupportTurnResult(message=_multi_date_handoff_message())

    ref = org_today(org_id)
    detailed = resolve_date_detailed(last, reference=ref, mode=DateParseMode.REFERENCE)
    date_iso = extract_reference_date_from_text(last, reference=ref)

    if detailed and detailed.needs_clarification:
        query_parts = ["política cancelamento atraso"]
        if has_absence_intent(last):
            query_parts.insert(0, "ausência falta comparecimento")
        if _CANCEL_WITH_DATE.search(last):
            query_parts.insert(0, "cancelamento")
        with set_tenant_context(org_id):
            kb_result = search_kb.invoke({"query": " ".join(query_parts)})
        message = _compose_ambiguous_support_reply(
            kb_result,
            clarification_prompt=detailed.clarification_prompt or "Qual data exatamente?",
            user_message=last,
        )
        return SupportTurnResult(message=message, reference_date=date_iso)

    if not date_iso:
        return None

    label = format_date_label_pt(date_iso)
    query_parts = ["política cancelamento atraso", date_iso, label]
    if has_absence_intent(last):
        query_parts.insert(0, "ausência falta comparecimento")
    if _CANCEL_WITH_DATE.search(last):
        query_parts.insert(0, "cancelamento")

    with set_tenant_context(org_id):
        kb_result = search_kb.invoke({"query": " ".join(query_parts)})

    message = _compose_support_reply(kb_result, date_iso=date_iso, user_message=last)
    return SupportTurnResult(message=message, reference_date=date_iso)
