import asyncio
import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from langchain_core.messages import AIMessage, HumanMessage

from packages.auth_core.config import settings
from packages.auth_core.limiter import limiter
from packages.auth_core.tenant import set_tenant_context
from packages.engine.checkpointer import master_engine
from packages.engine.metrics.service import save_conversation_metric
from packages.engine.token_tracking import TurnTokenTracker, resolve_turn_tokens
from packages.integrations.webhook.dedup import try_claim_message
from packages.integrations.webhook.schemas import WebhookResponse, WhatsAppWebhookPayload
from packages.integrations.webhook.tenant_resolver import resolve_org_id_from_webhook_value
from packages.integrations.webhook.whatsapp import WhatsAppService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook")

FALLBACK_MESSAGE = (
    "Estamos com uma instabilidade temporária no nosso sistema. "
    "Um consultor entrará em contato em breve. Desculpe pelo inconveniente!"
)

@router.get("/whatsapp")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """
    Meta Webhook Verification Endpoint.
    Meta sends a GET request here to verify the webhook connection.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge)
    raise HTTPException(status_code=403, detail="Invalid verification token")


def validate_signature(payload: bytes, signature: str) -> bool:
    """Validates that the payload was sent by Meta using HMAC SHA256."""
    if not signature or not settings.WHATSAPP_APP_SECRET:
        return False

    expected_signature = hmac.new(
        settings.WHATSAPP_APP_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected_signature}", signature)

def process_message_in_background(payload: WhatsAppWebhookPayload):
    """Background task: deduplicates, invokes LangGraph engine, handles failures."""
    try:
        entries = payload.entry
        if not entries:
            return
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])
                for msg in messages:
                    if msg.get("type") != "text":
                        continue

                    # --- DEDUPLICATION CHECK ---
                    message_id = msg.get("id")
                    if message_id and not try_claim_message(message_id):
                        logger.info("🔁 DUPLICATE SKIPPED: message_id=%s", message_id)
                        continue

                    sender_id = msg.get("from", "unknown")
                    text_body = msg.get("text", {}).get("body", "")
                    if not text_body:
                        continue

                    # LGPD Compliance: Mask message content in logs
                    masked_body = (text_body[:15] + "...") if len(text_body) > 15 else text_body
                    logger.info(f"Processing message from {sender_id}: {masked_body}")

                    initial_state = {
                        "messages": [HumanMessage(content=text_body)],
                        "sender_id": sender_id,
                        "handoff_requested": False
                    }

                    org_id = resolve_org_id_from_webhook_value(value)

                    token_tracker = TurnTokenTracker()
                    config = {
                        "configurable": {"thread_id": sender_id, "org_id": org_id},
                        "callbacks": [token_tracker],
                    }

                    # --- HANDOFF & HUMAN MODE CHECK ---
                    try:
                        current_state_wrapper = master_engine.get_state(config)
                        if current_state_wrapper and hasattr(current_state_wrapper, "values"):
                            state_values = current_state_wrapper.values
                            if state_values.get("handoff_requested") is True:
                                if text_body.strip().lower() == "/resume":
                                    logger.info(f"🦸‍♂️ HUMAN MODE DISABLED for {sender_id}. Resuming AI control.")
                                    master_engine.update_state(config, {"handoff_requested": False})
                                    logger.info(f"AI Response to {sender_id}: Bot reassumiu o controle.")
                                    continue
                                else:
                                    logger.info(f"🤫 SILENT MODE: Human is talking to {sender_id}. Ignoring message.")
                                    continue
                    except Exception as e:
                        logger.warning(f"Failed to check graph state for handoff: {e}")

                    try:
                        with set_tenant_context(org_id):
                            final_state = asyncio.run(
                                master_engine.ainvoke(initial_state, config=config)
                            )

                        # Extract AI response object and text
                        messages = final_state.get("messages", [])
                        ai_msg_obj = messages[-1] if messages else None

                        if not isinstance(ai_msg_obj, AIMessage) and len(messages) > 1:
                            for m in reversed(messages):
                                if isinstance(m, AIMessage):
                                    ai_msg_obj = m
                                    break

                        if final_state.get("audit_flag") is False:
                            logger.warning(f"AUDIT BLOCKED response for {sender_id}. Fallback activated.")
                            final_ai_msg = "Sinto muito, ocorreu um erro técnico ao processar sua resposta. Como posso te ajudar de outra forma?"
                        else:
                            final_ai_msg = getattr(ai_msg_obj, "content", "") if ai_msg_obj else ""

                        # --- SAVE METRICS ---
                        if ai_msg_obj:
                            t_in, t_out, t_total = resolve_turn_tokens(messages, token_tracker)

                            save_conversation_metric(
                                thread_id=sender_id,
                                sender_id=sender_id,
                                agent_type=final_state.get("active_agent", "unknown"),
                                messages_count=len(messages),
                                tokens_in=t_in,
                                tokens_out=t_out,
                                tokens_total=t_total,
                                handoff_requested=final_state.get("handoff_requested", False),
                                qualified=final_state.get("qualified", False),
                                model_name=settings.MODEL_NAME
                            )

                        if final_ai_msg and final_ai_msg.strip():
                            wa_service = WhatsAppService()
                            sent = asyncio.run(
                                wa_service.send_text_message(sender_id, final_ai_msg)
                            )
                            if not sent:
                                logger.warning(
                                    "WhatsApp outbound failed for %s (check org credentials)",
                                    sender_id,
                                )
                    except Exception as llm_error:
                        logger.critical(f"🚨 ENGINE FAILURE for {sender_id}: {llm_error}", exc_info=True)
                        final_ai_msg = FALLBACK_MESSAGE

                    logger.info(f"AI Response to {sender_id}: {final_ai_msg}")

    except Exception as e:
        logger.error(f"Failed to process background message: {e}", exc_info=True)

@router.post("/whatsapp", response_model=WebhookResponse)
@limiter.limit("20/minute")
async def handle_whatsapp_message(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Receives incoming WhatsApp messages with HMAC signature verification.
    """
    content_length = request.headers.get("Content-Length")
    if content_length and int(content_length) > 1024 * 1024:
        logger.error("PAYLOAD_BOMB blocked: Request size too large.")
        raise HTTPException(status_code=413, detail="Payload too large")

    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if settings.WHATSAPP_APP_SECRET and not validate_signature(body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload_dict = json.loads(body)
        payload = WhatsAppWebhookPayload(**payload_dict)

        background_tasks.add_task(process_message_in_background, payload)
        return WebhookResponse(status="success", message="Webhook verified and queued")

    except json.JSONDecodeError:
        logger.error("Failed to decode JSON payload")
        return WebhookResponse(status="error", message="Invalid JSON")
    except Exception as e:
        logger.error(f"Unexpected error in webhook: {e}", exc_info=True)
        return WebhookResponse(status="error", message="Internal error")
