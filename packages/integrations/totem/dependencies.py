"""FastAPI dependency that authenticates a kiosk (totem) device.

Lives in the totem package (not auth_core) to respect the dependency graph:
auth_core may only depend on models, while integrations may depend on auth_core.
This is the device-level analogue of ``validated_tenant_context`` — it trusts a
provisioned device token instead of a person's JWT cookie.
"""
from __future__ import annotations

from fastapi import Header, HTTPException

from packages.integrations.totem.tenant_resolver import resolve_org_id_from_device_token


async def resolve_kiosk_tenant(
    x_device_token: str | None = Header(None, alias="x-device-token"),
) -> str:
    """Resolve the org for the calling totem, or 403 (fail-closed).

    A missing or unknown token is treated as unauthorized — never 422 — so an
    unpaired/revoked device gets a consistent security response.
    """
    org_id = resolve_org_id_from_device_token(x_device_token or "")
    if not org_id:
        raise HTTPException(status_code=403, detail="Dispositivo não autorizado.")
    return org_id
