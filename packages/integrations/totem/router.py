"""Kiosk (totem) API — a public self-service device, authenticated by device token.

Every endpoint resolves its organization from the ``x-device-token`` header via
``resolve_kiosk_tenant`` (fail-closed → 403). There is no person logged in.
"""
import logging

from fastapi import APIRouter, Depends, Request

from packages.auth_core.limiter import limiter
from packages.auth_core.tenant import set_tenant_context
from packages.integrations.totem.dependencies import resolve_kiosk_tenant
from packages.integrations.totem.schemas import TotemAdvanceRequest, TotemTurnResponse
from packages.integrations.totem.service import advance_totem, start_totem_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kiosk", tags=["Totem"])


@router.post("/session", response_model=TotemTurnResponse)
@limiter.limit("60/minute")
async def kiosk_start(
    request: Request,
    org_id: str = Depends(resolve_kiosk_tenant),
):
    """Begin a kiosk attendance; returns the identification step."""
    with set_tenant_context(org_id):
        return TotemTurnResponse(**start_totem_session(org_id))


@router.post("/advance", response_model=TotemTurnResponse)
@limiter.limit("120/minute")
async def kiosk_advance(
    request: Request,
    payload: TotemAdvanceRequest,
    org_id: str = Depends(resolve_kiosk_tenant),
):
    """Apply one selection/input and return the next step or a terminal result."""
    with set_tenant_context(org_id):
        result = await advance_totem(payload.session_id, payload.selection)
    return TotemTurnResponse(**result)
