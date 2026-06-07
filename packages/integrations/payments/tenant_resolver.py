"""Resolves the per-organization payment configuration and provider.

Credentials are stored per tenant in organizations.settings.integrations.payments
(not in global .env), mirroring how WhatsApp credentials are per-org. Until a real
adapter exists, every org resolves to the NoOpPaymentProvider.
"""
import logging
from typing import Any

from packages.auth_core.database import db
from packages.integrations.payments.base import PaymentProvider
from packages.integrations.payments.stub import NoOpPaymentProvider

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: dict[str, Any] = {
    "provider": None,
    "enabled": False,
    "external_merchant_id": None,
}


def get_payments_config(org_id: str) -> dict[str, Any]:
    """Reads organizations.settings.integrations.payments, with safe defaults."""
    if not org_id or org_id == "ALL":
        return dict(DEFAULT_CONFIG)
    try:
        res = (
            db.client.table("organizations")
            .select("settings")
            .eq("id", org_id)
            .maybe_single()
            .execute()
        )
        settings_data = (res.data if res else None) or {}
        payments = ((settings_data.get("settings") or {}).get("integrations") or {}).get("payments")
        if isinstance(payments, dict):
            return {**DEFAULT_CONFIG, **payments}
    except Exception as exc:
        logger.warning("Failed to read payments config for org %s: %s", org_id, exc)
    return dict(DEFAULT_CONFIG)


def get_payment_provider(org_id: str) -> PaymentProvider:
    """Returns the provider for an org. Always NoOp until a real adapter is added."""
    config = get_payments_config(org_id)
    if not config.get("enabled"):
        return NoOpPaymentProvider()
    # Future: map config["provider"] -> concrete adapter. Stub keeps it disabled.
    logger.info("Payments marked enabled for org %s but no adapter is implemented yet.", org_id)
    return NoOpPaymentProvider()
