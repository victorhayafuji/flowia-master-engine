"""Process inbound WhatsApp text messages through LangGraph."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from packages.auth_core.config import settings
from packages.auth_core.conversation_thread import get_state_with_legacy_fallback
from packages.auth_core.tenant import set_tenant_context
from packages.compliance.consent import ConsentAction, evaluate_consent_gate
from packages.compliance.logging_utils import mask_sender_id
from packages.engine.checkpointer import master_engine
from packages.engine.input_guard import (
    BLOCKED_USER_RESPONSE,
    MessageVerdict,
    assess_user_message,
    format_user_message_for_agent,
)
from packages.engine.metrics.service import save_conversation_metric
from packages.engine.metrics.telemetry import extract_turn_tools_called
from packages.engine.token_tracking import TurnTokenTracker, resolve_turn_tokens
from packages.integrations.webhook.dedup import try_claim_message
from packages.integrations.webhook.schemas import WhatsAppWebhookPayload
from packages.integrations.webhook.session_store import can_resume_ai, clear_handoff_session
from packages.integrations.webhook.whatsapp import WhatsAppService

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = (
    "Estamos com uma instabilidade temporária no nosso sistema. "
    "Um consultor entrará em contato em breve. Desculpe pelo inconveniente!"
)

MAX_JOB_ATTEMPTS = 3


def process_inbound_text_message(
    *,
    org_id: str,
    sender_id: str,
    text_body: str,
    message_id: str | None = None,
    skip_dedup: bool = False,
) -> None:
    """Run input guard, consent, engine invoke and outbound for one WhatsApp text message."""
    if message_id and not skip_dedup and not try_claim_message(message_id):
        logger.info("Duplicate webhook message_id=%s — skipping", message_id)
        return

    if not text_body:
        return

    verdict = assess_user_message(text_body)
    if verdict == MessageVerdict.BLOCKED:
        logger.warning("Blocked message from %s (input guard)", mask_sender_id(sender_id))
        wa_service = WhatsAppService()
        asyncio.run(wa_service.send_text_message(sender_id, BLOCKED_USER_RESPONSE))
        return

    formatted_body = format_user_message_for_agent(text_body)
    masked_body = (text_body[:15] + "...") if len(text_body) > 15 else text_body
    logger.info("Processing message from %s: %s", mask_sender_id(sender_id), masked_body)

    with set_tenant_context(org_id):
        consent_action, notice_msg, lgpd_shown = evaluate_consent_gate(org_id, sender_id, "whatsapp")

    if consent_action == ConsentAction.SEND_NOTICE and notice_msg:
        try:
            wa_service = WhatsAppService()
            asyncio.run(wa_service.send_text_message(sender_id, notice_msg))
        except ValueError as wa_err:
            logger.warning("LGPD notice skipped for %s: %s", mask_sender_id(sender_id), wa_err)
        return

    initial_state: dict[str, Any] = {
        "messages": [HumanMessage(content=formatted_body)],
        "sender_id": sender_id,
        "handoff_requested": False,
        "lgpd_shown": lgpd_shown,
    }
    if verdict == MessageVerdict.SUSPICIOUS:
        initial_state["audit_flag"] = "suspicious"

    token_tracker = TurnTokenTracker()
    base_configurable = {
        "org_id": org_id,
        "channel": "whatsapp",
        "sender_phone": sender_id,
    }
    _, config = get_state_with_legacy_fallback(
        master_engine,
        org_id,
        sender_id,
        base_configurable,
        callbacks=[token_tracker],
    )
    thread_id = config["configurable"]["thread_id"]
    final_ai_msg = ""

    try:
        current_state_wrapper, _ = get_state_with_legacy_fallback(
            master_engine,
            org_id,
            sender_id,
            base_configurable,
        )
        if current_state_wrapper and hasattr(current_state_wrapper, "values"):
            state_values = current_state_wrapper.values
            if state_values.get("handoff_requested") is True:
                if text_body.strip().lower() == "/resume":
                    can_resume, resume_err = can_resume_ai(sender_id, org_id=org_id)
                    if not can_resume:
                        logger.info(
                            "Resume rejected for %s: %s",
                            mask_sender_id(sender_id),
                            resume_err,
                        )
                        return
                    logger.info(
                        "HUMAN MODE DISABLED for %s. Resuming AI control.",
                        mask_sender_id(sender_id),
                    )
                    master_engine.update_state(config, {"handoff_requested": False})
                    clear_handoff_session(sender_id, org_id=org_id)
                    return
                logger.info(
                    "SILENT MODE: Human is talking to %s. Ignoring message.",
                    mask_sender_id(sender_id),
                )
                return
    except Exception as exc:
        logger.warning("Failed to check graph state for handoff: %s", exc)

    try:
        with set_tenant_context(org_id):
            final_state = asyncio.run(master_engine.ainvoke(initial_state, config=config))

        messages = final_state.get("messages", [])
        ai_msg_obj = messages[-1] if messages else None

        if not isinstance(ai_msg_obj, AIMessage) and len(messages) > 1:
            for m in reversed(messages):
                if isinstance(m, AIMessage):
                    ai_msg_obj = m
                    break

        if final_state.get("audit_flag") == "blocked":
            logger.warning(
                "AUDIT BLOCKED response for %s. Fallback activated.",
                mask_sender_id(sender_id),
            )
            final_ai_msg = BLOCKED_USER_RESPONSE
        elif final_state.get("audit_flag") is False:
            logger.warning(
                "AUDIT BLOCKED response for %s. Fallback activated.",
                mask_sender_id(sender_id),
            )
            final_ai_msg = (
                "Sinto muito, ocorreu um erro técnico ao processar sua resposta. "
                "Como posso te ajudar de outra forma?"
            )
        else:
            final_ai_msg = getattr(ai_msg_obj, "content", "") if ai_msg_obj else ""

        if ai_msg_obj:
            t_in, t_out, t_total = resolve_turn_tokens(messages, token_tracker)
            save_conversation_metric(
                thread_id=thread_id,
                sender_id=sender_id,
                agent_type=final_state.get("active_agent", "unknown"),
                messages_count=len(messages),
                tokens_in=t_in,
                tokens_out=t_out,
                tokens_total=t_total,
                handoff_requested=final_state.get("handoff_requested", False),
                qualified=final_state.get("qualified", False),
                model_name=settings.MODEL_NAME,
                organization_id=org_id,
                scheduling_path=final_state.get("scheduling_path"),
                triage_source=final_state.get("triage_source"),
                channel="whatsapp",
                tools_called=extract_turn_tools_called(messages),
            )

        if final_ai_msg and final_ai_msg.strip():
            try:
                wa_service = WhatsAppService()
                sent = asyncio.run(wa_service.send_text_message(sender_id, final_ai_msg))
                if not sent:
                    logger.warning(
                        "WhatsApp outbound failed for %s (check org credentials)",
                        mask_sender_id(sender_id),
                    )
            except ValueError as wa_err:
                logger.warning(
                    "WhatsApp outbound skipped for %s: %s",
                    mask_sender_id(sender_id),
                    wa_err,
                )
    except Exception as llm_error:
        logger.critical(
            "ENGINE FAILURE for %s: %s",
            mask_sender_id(sender_id),
            llm_error,
            exc_info=True,
        )
        final_ai_msg = FALLBACK_MESSAGE

    masked_response = (final_ai_msg[:15] + "...") if len(final_ai_msg) > 15 else final_ai_msg
    logger.info("AI Response to %s: %s", mask_sender_id(sender_id), masked_response)


def iter_text_messages(payload: WhatsAppWebhookPayload):
    """Yield (value, msg) for each inbound text message in a webhook payload."""
    for entry in payload.entry or []:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                if msg.get("type") == "text":
                    yield value, msg


def process_message_in_background(payload: WhatsAppWebhookPayload) -> None:
    """Background entry: enqueue jobs and optionally process inline."""
    from packages.integrations.webhook.job_queue import dispatch_whatsapp_payload

    try:
        dispatch_whatsapp_payload(payload)
    except Exception as exc:
        logger.error("Failed to process background message: %s", exc, exc_info=True)


def process_job_record(job: dict[str, Any]) -> None:
    """Process one persisted queue job."""
    payload = job.get("payload") or {}
    org_id = str(job.get("organization_id") or payload.get("org_id") or "")
    sender_id = str(payload.get("sender_id") or job.get("sender_id") or "")
    text_body = str(payload.get("text_body") or "")
    message_id = payload.get("message_id") or job.get("message_id")

    if not org_id or not sender_id:
        raise ValueError("Job missing organization_id or sender_id")

    process_inbound_text_message(
        org_id=org_id,
        sender_id=sender_id,
        text_body=text_body,
        message_id=str(message_id) if message_id else None,
        skip_dedup=True,
    )
