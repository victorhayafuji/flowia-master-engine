import logging
from typing import Any

from packages.auth_core.database import db

logger = logging.getLogger(__name__)

DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000000"


def resolve_org_id_from_webhook_value(value: dict[str, Any]) -> str:
    """
    Resolves organization_id from WhatsApp webhook metadata.
    Matches phone_number_id against organizations.whatsapp_phone_id.
    """
    metadata = value.get("metadata") or {}
    phone_number_id = metadata.get("phone_number_id")

    if phone_number_id:
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
            logger.warning("No organization found for phone_number_id=%s", phone_number_id)
        except Exception as e:
            logger.error("Failed to resolve org by phone_number_id: %s", e)

    return _fallback_org_id()


def _fallback_org_id() -> str:
    try:
        res = db.client.table("organizations").select("id").limit(1).execute()
        if res.data:
            logger.warning("Using fallback org (first organization in DB)")
            return res.data[0]["id"]
    except Exception as e:
        logger.error("Failed to fetch fallback org: %s", e)
    return DEFAULT_ORG_ID
