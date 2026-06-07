from typing import Any

from pydantic import BaseModel


class WhatsAppWebhookPayload(BaseModel):
    """
    Schema for validating incoming WhatsApp Webhook payloads.
    """
    object: str
    entry: list[dict[str, Any]]

class WebhookResponse(BaseModel):
    status: str
    message: str | None = None
