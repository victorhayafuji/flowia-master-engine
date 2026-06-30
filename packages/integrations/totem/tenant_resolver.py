"""Resolve a kiosk (totem) device token to its organization_id.

Mirror of ``packages/integrations/webhook/tenant_resolver.py``: a totem is not a
logged-in person (cookie JWT) nor a Meta sender (webhook signature) — it is a
provisioned device. The token (SHA-256 hashed) maps to one organization. Fail-closed:
an unknown/inactive token resolves to ``None`` and the request is rejected (403).
"""
from __future__ import annotations

import logging

from packages.auth_core.database import db
from packages.integrations.totem.tokens import hash_device_token

logger = logging.getLogger(__name__)


def resolve_org_id_from_device_token(token: str) -> str | None:
    """Return the organization_id for an active device token, or None if unresolved.

    Touches ``last_seen_at`` on a hit (best-effort; failure to update never blocks
    the request). Never logs the raw token.
    """
    token_hash = hash_device_token(token)
    if not token_hash:
        return None

    try:
        res = (
            db.client.table("kiosk_devices")
            .select("id, organization_id")
            .eq("token_hash", token_hash)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
    except Exception as e:
        logger.error("Failed to resolve org by device token: %s", type(e).__name__)
        return None

    if not res.data:
        logger.warning("Kiosk device token did not resolve to any active device")
        return None

    device = res.data[0]
    _touch_last_seen(device["id"])
    return device["organization_id"]


def _touch_last_seen(device_id: str) -> None:
    """Best-effort update of last_seen_at; swallow errors (telemetry, not critical)."""
    from datetime import datetime, timezone

    try:
        (
            db.client.table("kiosk_devices")
            .update({"last_seen_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", device_id)
            .execute()
        )
    except Exception as e:
        logger.debug("Could not update kiosk last_seen_at: %s", type(e).__name__)
