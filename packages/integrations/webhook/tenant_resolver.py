import logging
from typing import Any

from packages.auth_core.config import settings
from packages.auth_core.database import db

logger = logging.getLogger(__name__)

DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000000"


def resolve_org_id_from_webhook_value(value: dict[str, Any]) -> str | None:
    """
    Resolves organization_id from WhatsApp webhook metadata.
    Matches phone_number_id against organizations.whatsapp_phone_id.
    Returns None if unresolved (fail-closed — do not process message).
    """
    metadata = value.get("metadata") or {}
    phone_number_id = metadata.get("phone_number_id")

    if not phone_number_id:
        logger.error("Webhook missing phone_number_id — org unresolved")
        return None

    sim_org = (settings.SIM_WHATSAPP_ORG_ID or "").strip()
    sim_phone = (settings.SIM_WHATSAPP_PHONE_ID or "123456789").strip()
    if sim_org and str(phone_number_id) == sim_phone:
        logger.info("Webhook tenant resolved via SIM_WHATSAPP_ORG_ID (local simulation)")
        return sim_org

    try:
        res = (
            db.client.table("organizations")
            .select("id")
            .eq("whatsapp_phone_id", str(phone_number_id))
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]["id"]
        logger.error("No organization found for phone_number_id=%s", phone_number_id)
    except Exception as e:
        logger.error("Failed to resolve org by phone_number_id: %s", e)

    return None
