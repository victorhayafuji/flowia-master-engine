"""Structured LLM extraction for ambiguous booking turns (bounded unpredictability)."""
from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from packages.auth_core.config import settings
from packages.engine.llm import get_chat_llm
from packages.engine.routing import is_booking_conversation, message_text
from packages.scheduling.booking_executor import _guess_service_query, resolve_booking_context
from packages.scheduling.guardrails import (
    extract_booking_date_from_text,
    parse_booking_date,
    resolve_service_from_catalog,
)

logger = logging.getLogger(__name__)


class BookingExtract(BaseModel):
    service_hint: str | None = None
    date_hint: str | None = None
    time_hint: str | None = None
    patient_name: str | None = None
    patient_phone: str | None = None
    user_acknowledgment: str | None = Field(
        default=None,
        description="Breve eco empático do pedido do cliente (1 frase, sem inventar dados).",
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    clarifying_question: str | None = None

    resolved_date: str | None = None
    resolved_service: str | None = None


def _human_texts(messages: Sequence[BaseMessage]) -> list[str]:
    return [message_text(m) for m in messages if getattr(m, "type", None) == "human"]


def should_run_intent_extractor(
    messages: Sequence[BaseMessage],
    org_id: str,
    *,
    booking_date: str | None = None,
    booking_service: str | None = None,
    booking_active: bool = False,
) -> bool:
    if not settings.INTENT_EXTRACTOR_ENABLED or not org_id:
        return False

    texts = _human_texts(messages)
    if not texts:
        return False

    if not (booking_active or is_booking_conversation(messages)):
        return False

    combined = " ".join(texts)
    ctx_date, ctx_service, _ = resolve_booking_context(
        messages, org_id, booking_date=booking_date, booking_service=booking_service
    )
    if ctx_date and ctx_service:
        return False

    if extract_booking_date_from_text(combined) and _guess_service_query(combined, org_id):
        return False

    return True


def _resolve_extracted_fields(raw: BookingExtract, org_id: str) -> BookingExtract:
    ref = date.today()
    resolved_date: str | None = None
    if raw.date_hint:
        parsed = extract_booking_date_from_text(raw.date_hint, reference=ref)
        if not parsed:
            parsed_date, err = parse_booking_date(raw.date_hint, reference=ref)
            if parsed_date and not err:
                parsed = parsed_date.isoformat()
        resolved_date = parsed

    resolved_service = None
    if raw.service_hint:
        service, err = resolve_service_from_catalog(org_id, raw.service_hint)
        if service and not err:
            resolved_service = service["name"]

    return raw.model_copy(
        update={"resolved_date": resolved_date, "resolved_service": resolved_service}
    )


async def extract_booking_intent(
    messages: Sequence[BaseMessage],
    org_id: str,
    *,
    salon_name: str = "salão",
) -> BookingExtract | None:
    """Extract structured booking hints from the latest user turn."""
    texts = _human_texts(messages)
    if not texts:
        return None

    recent = texts[-3:]
    conversation = "\n".join(f"Cliente: {t}" for t in recent)

    llm = get_chat_llm(temperature=0.0).with_structured_output(BookingExtract)

    prompt = (
        f"Você extrai dados de agendamento para o {salon_name}. "
        "Responda só com campos presentes ou inferíveis do texto — não invente horários livres. "
        "date_hint: data coloquial PT-BR (ex: amanhã, sexta, 12/06) ou ISO YYYY-MM-DD quando possível. "
        "time_hint em HH:MM 24h. "
        "user_acknowledgment: uma frase curta reconhecendo o pedido. "
        "Não repita datas ambíguas nem reformule a pergunta que o bot acabou de fazer. "
        "Em respostas curtas do cliente (ex: 'não sei', 'pode ser sexta'), omita user_acknowledgment.\n\n"
        f"{conversation}"
    )

    try:
        raw = await llm.ainvoke(prompt)
        if not isinstance(raw, BookingExtract):
            return None
        enriched = _resolve_extracted_fields(raw, org_id)
        if enriched.confidence < 0.35 and not enriched.resolved_service and not enriched.resolved_date:
            return None
        logger.info(
            "Intent extract | confidence=%.2f service=%s date=%s",
            enriched.confidence,
            enriched.resolved_service,
            enriched.resolved_date,
        )
        return enriched
    except Exception:
        logger.exception("extract_booking_intent failed")
        return None
