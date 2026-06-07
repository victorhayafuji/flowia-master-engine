"""Tenant context helpers for chat agents."""
import logging

logger = logging.getLogger(__name__)

DEFAULT_SALON_NAME = "seu salão"


def get_salon_name(org_id: str | None) -> str:
    """Resolve organization display name for white-label prompts."""
    if not org_id or org_id == "ALL":
        return DEFAULT_SALON_NAME

    try:
        from packages.auth_core.database import db

        if not db.is_ready:
            return DEFAULT_SALON_NAME

        result = (
            db.client.table("organizations")
            .select("name")
            .eq("id", org_id)
            .maybe_single()
            .execute()
        )
        if result.data and result.data.get("name"):
            return str(result.data["name"]).strip()
    except Exception as e:
        logger.warning("get_salon_name fallback for org %s: %s", org_id, e)

    return DEFAULT_SALON_NAME
