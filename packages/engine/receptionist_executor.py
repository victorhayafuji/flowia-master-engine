"""Deterministic receptionist turns for price/service info (catalog + RAG via search_kb)."""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from langchain_core.messages import BaseMessage

from packages.auth_core.tenant import set_tenant_context
from packages.engine.routing import (
    has_scheduling_intent,
    is_booking_confirmed_in_thread,
    is_post_booking_closing,
    is_price_only_question,
    message_text,
    should_force_scheduling_route,
)
from packages.engine.tools import search_kb
from packages.scheduling.guardrails import _normalize_key

_SERVICE_INquiry_HINTS = (
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
    "fazem",
    "tem ",
    "oferecem",
    "servico",
    "serviço",
)

_PRICE_PATTERN = re.compile(r"R\$\s*[\d.,]+")


@dataclass
class ReceptionistTurnResult:
    message: str


def has_service_inquiry(text: str) -> bool:
    """Service/info question without explicit scheduling."""
    norm = _normalize_key(text)
    if is_price_only_question(text):
        return True
    if has_scheduling_intent(text):
        return False
    return any(hint in norm for hint in _SERVICE_INquiry_HINTS)


def should_run_deterministic_receptionist(
    messages: Sequence[BaseMessage],
    *,
    booking_active: bool = False,
) -> bool:
    if should_force_scheduling_route(list(messages), booking_active=booking_active):
        return False
    human = [m for m in messages if getattr(m, "type", None) == "human"]
    if not human:
        return False
    last = message_text(human[-1])
    if is_booking_confirmed_in_thread(list(messages)) and is_post_booking_closing(last):
        return True
    return has_service_inquiry(last)


def kb_has_official_data(kb_result: str) -> bool:
    if not kb_result or kb_result.startswith("Consulta inválida"):
        return False
    if kb_result.startswith("Erro interno"):
        return False
    if "Nenhuma informação foi encontrada" in kb_result:
        return False
    return (
        "[DADOS OFICIAIS DA BASE" in kb_result
        or "[DADOS OFICIAIS DO CATÁLOGO" in kb_result
        or "[DADOS OFICIAIS DO CATALOGO" in kb_result
        or bool(_PRICE_PATTERN.search(kb_result))
    )


def _extract_catalog_lines(kb_result: str) -> list[str]:
    lines: list[str] = []
    for line in kb_result.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            lines.append(stripped[2:])
    return lines


def compose_receptionist_reply(kb_result: str, user_message: str) -> str:
    """Turn search_kb output into a short WhatsApp-style answer."""
    lines = _extract_catalog_lines(kb_result)
    if not lines:
        return kb_result.strip()

    if len(lines) == 1:
        detail = lines[0]
        if is_price_only_question(user_message) or "?" in user_message:
            if "color" in _normalize_key(user_message):
                return f"Sim! Fazemos coloração. {detail} Quer agendar um horário?"
            return f"{detail} Quer agendar um horário?"
        return detail

    intro = "Estes são os serviços que encontrei no catálogo:"
    body = "\n".join(f"• {line}" for line in lines[:6])
    return f"{intro}\n{body}\n\nQual deles você gostaria de saber mais ou agendar?"


def run_receptionist_turn(
    messages: Sequence[BaseMessage],
    org_id: str,
) -> ReceptionistTurnResult | None:
    human = [m for m in messages if getattr(m, "type", None) == "human"]
    if not human:
        return None
    last = message_text(human[-1])

    if is_booking_confirmed_in_thread(list(messages)) and is_post_booking_closing(last):
        return ReceptionistTurnResult(
            message=(
                "Por nada! Ficamos felizes em ajudar. "
                "Se precisar de mais alguma coisa, é só chamar!"
            )
        )

    with set_tenant_context(org_id):
        kb_result = search_kb.invoke({"query": last})

    if not kb_has_official_data(kb_result):
        return None

    return ReceptionistTurnResult(message=compose_receptionist_reply(kb_result, last))
