"""When deterministic scheduling should defer to the LLM (SCHEDULING_LLM_FALLBACK=smart)."""
from __future__ import annotations

from collections.abc import Sequence

from langchain_core.messages import BaseMessage

from packages.engine.routing import is_booking_conversation, message_text
from packages.scheduling.booking_executor import _guess_service_query, resolve_booking_context
from packages.scheduling.guardrails import extract_booking_date_from_text


def _human_texts(messages: Sequence[BaseMessage]) -> list[str]:
    return [message_text(m) for m in messages if getattr(m, "type", None) == "human"]


def needs_scheduling_llm_fallback(
    messages: Sequence[BaseMessage],
    org_id: str,
    *,
    booking_date: str | None = None,
    booking_service: str | None = None,
    booking_active: bool = False,
) -> bool:
    """True when colloquial/ambiguous input likely needs the scheduling LLM agent."""
    if not org_id:
        return False

    texts = _human_texts(messages)
    if not texts:
        return False

    if not (booking_active or is_booking_conversation(messages)):
        return False

    combined = " ".join(texts)
    last = texts[-1].lower().strip()

    ctx_date, ctx_service = resolve_booking_context(
        messages, org_id, booking_date=booking_date, booking_service=booking_service
    )
    date_iso = extract_booking_date_from_text(combined) or ctx_date
    service_query = _guess_service_query(combined, org_id) or ctx_service

    if date_iso and service_query:
        return False

    colloquial_service_markers = (
        "mecha",
        "luzes",
        "balayage",
        "retoque",
        "escova",
        "progressiva",
        "botox",
        "sombrancelha",
        "unha",
        "pedicure",
    )
    has_colloquial_service = any(m in last for m in colloquial_service_markers)

    if has_colloquial_service and not service_query:
        return True

    if date_iso and not service_query and len(last.split()) > 6:
        return True

    return False
