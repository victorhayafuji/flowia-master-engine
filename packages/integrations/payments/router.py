"""Payments stub router. Status reflects the per-org flag; webhook is not implemented."""
import logging

from fastapi import APIRouter, Depends, HTTPException

from packages.auth_core.dependencies import auth_required, tenant_context
from packages.auth_core.tenant import set_tenant_context
from packages.integrations.payments.tenant_resolver import get_payments_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/payments", tags=["Payments (stub)"])


@router.get("/status", dependencies=[Depends(auth_required)])
async def payments_status(org_id: str = Depends(tenant_context)):
    """Returns whether payments are enabled for the active organization."""
    with set_tenant_context(org_id):
        config = get_payments_config(org_id)
    return {
        "status": "success",
        "data": {
            "enabled": bool(config.get("enabled")),
            "provider": config.get("provider"),
        },
    }


@router.post("/webhook")
async def payments_webhook():
    """Placeholder for a future provider webhook. Intentionally not implemented."""
    raise HTTPException(
        status_code=501,
        detail="Integração de pagamentos não implementada (stub).",
    )
