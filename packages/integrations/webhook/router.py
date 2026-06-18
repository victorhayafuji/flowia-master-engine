import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from packages.auth_core.config import settings
from packages.auth_core.limiter import limiter
from packages.integrations.webhook.processor import process_message_in_background
from packages.integrations.webhook.schemas import WebhookResponse, WhatsAppWebhookPayload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook")


@router.get("/whatsapp")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """Meta Webhook Verification Endpoint."""
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
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected_signature}", signature)


@router.post("/whatsapp", response_model=WebhookResponse)
@limiter.limit("20/minute")
async def handle_whatsapp_message(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Receives incoming WhatsApp messages with HMAC signature verification."""
    content_length = request.headers.get("Content-Length")
    if content_length and int(content_length) > 1024 * 1024:
        logger.error("PAYLOAD_BOMB blocked: Request size too large.")
        raise HTTPException(status_code=413, detail="Payload too large")

    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if settings.WHATSAPP_APP_SECRET:
        if not validate_signature(body, signature):
            raise HTTPException(status_code=403, detail="Invalid signature")
    elif not settings.WHATSAPP_ALLOW_UNSIGNED:
        # Fail-closed: sem APP_SECRET configurado, só aceitamos inbound não assinado
        # com opt-in explícito (modelo multi-app Meta — ver CLAUDE.md §20).
        logger.error(
            "Inbound webhook rejeitado: WHATSAPP_APP_SECRET ausente e WHATSAPP_ALLOW_UNSIGNED=false"
        )
        raise HTTPException(status_code=403, detail="Webhook signature required")

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
