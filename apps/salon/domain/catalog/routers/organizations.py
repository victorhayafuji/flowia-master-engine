"""Organization CRUD and WhatsApp credentials."""
import logging

from fastapi import APIRouter, Depends, HTTPException

from apps.salon.domain.catalog.helpers import (
    MVP_ALLOWED_VERTICAL,
    mask_secret,
    raise_on_whatsapp_phone_conflict,
    verticals_for_product_line,
)
from apps.salon.domain.catalog.schemas import (
    KioskDeviceCreate,
    OrganizationBase,
    OrganizationWhatsAppUpdate,
    WhatsAppTestRequest,
)
from packages.auth_core.config import settings
from packages.auth_core.database import SupabaseHandler
from packages.auth_core.dependencies import admin_required, get_db, tenant_context
from packages.auth_core.exceptions import BusinessLogicError
from packages.integrations.totem.tokens import generate_device_token, hash_device_token
from packages.integrations.webhook.whatsapp import WhatsAppService

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_concrete_org(org_id: str) -> None:
    """WhatsApp config is per-org; reject the super_admin 'ALL' wildcard."""
    if org_id == "ALL":
        raise HTTPException(
            status_code=400,
            detail="Selecione uma organização específica para configurar o WhatsApp.",
        )


@router.post("/", dependencies=[Depends(admin_required)])
async def create_organization(org: OrganizationBase, db: SupabaseHandler = Depends(get_db)):
    if org.vertical != MVP_ALLOWED_VERTICAL:
        raise HTTPException(
            status_code=400,
            detail="No MVP apenas organizações do tipo salão (vertical=salon) são permitidas.",
        )
    try:
        insert_data = org.model_dump(mode="json")
        result = db.client.table("organizations").insert(insert_data).execute()
        if not result.data:
            raise HTTPException(status_code=400, detail="Erro ao criar organização")
        return {"status": "success", "data": result.data[0]}
    except BusinessLogicError:
        raise
    except Exception as e:
        raise_on_whatsapp_phone_conflict(e)
        logger.exception("Erro ao criar organização")
        raise HTTPException(status_code=400, detail="Erro ao criar organização.") from e


@router.patch("/{organization_id}/whatsapp", dependencies=[Depends(admin_required)])
async def update_organization_whatsapp(
    organization_id: str,
    payload: OrganizationWhatsAppUpdate,
    db: SupabaseHandler = Depends(get_db),
):
    data = payload.model_dump(mode="json", exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")
    try:
        result = (
            db.client.table("organizations")
            .update(data)
            .eq("id", organization_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Organização não encontrada")
        return {"status": "success", "data": result.data[0]}
    except BusinessLogicError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise_on_whatsapp_phone_conflict(e)
        logger.exception("Erro ao atualizar WhatsApp da organização %s", organization_id)
        raise HTTPException(
            status_code=400, detail="Erro ao atualizar credenciais WhatsApp."
        ) from e


# --- Self-service WhatsApp config (org_admin configura a própria organização) ---
# Escopadas ao tenant do chamador via tenant_context (header x-organization-id == JWT org_id).


@router.get("/whatsapp")
async def get_my_whatsapp(
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db),
):
    """Returns the caller org's WhatsApp config with the token masked (never raw)."""
    _require_concrete_org(org_id)
    res = (
        db.client.table("organizations")
        .select("whatsapp_phone_id, whatsapp_access_token, whatsapp_business_id")
        .eq("id", org_id)
        .limit(1)
        .execute()
    )
    row = res.data[0] if res.data else {}
    token = (row.get("whatsapp_access_token") or "").strip()
    return {
        "status": "success",
        "data": {
            "whatsapp_phone_id": row.get("whatsapp_phone_id"),
            "whatsapp_business_id": row.get("whatsapp_business_id"),
            "token_configured": bool(token),
            "token_preview": mask_secret(token),
            "verify_token": settings.WHATSAPP_VERIFY_TOKEN,
            "webhook_url": settings.PUBLIC_API_URL.rstrip("/") + "/webhook/whatsapp",
        },
    }


@router.patch("/whatsapp")
async def update_my_whatsapp(
    payload: OrganizationWhatsAppUpdate,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db),
):
    """Updates the caller org's WhatsApp credentials. Blank token = keep current."""
    _require_concrete_org(org_id)
    data = payload.model_dump(mode="json", exclude_unset=True)
    # Empty token means "don't change it" — never overwrite a saved token with blank.
    if "whatsapp_access_token" in data and not (data["whatsapp_access_token"] or "").strip():
        data.pop("whatsapp_access_token")
    if not data:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")
    try:
        result = (
            db.client.table("organizations").update(data).eq("id", org_id).execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Organização não encontrada")
        # Never echo the token back to the client.
        return {"status": "success", "data": {"updated": True}}
    except BusinessLogicError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        raise_on_whatsapp_phone_conflict(e)
        logger.exception("Erro ao atualizar WhatsApp da própria org (org=%s)", org_id)
        raise HTTPException(
            status_code=400, detail="Erro ao atualizar credenciais WhatsApp."
        ) from e


@router.post("/whatsapp/test")
async def test_my_whatsapp(
    payload: WhatsAppTestRequest,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db),
):
    """Validates WhatsApp credentials against the Meta Graph API (read-only)."""
    _require_concrete_org(org_id)
    phone_id = (payload.whatsapp_phone_id or "").strip()
    token = (payload.whatsapp_access_token or "").strip()
    # Blank fields fall back to the stored credentials (test without retyping the token).
    if not phone_id or not token:
        res = (
            db.client.table("organizations")
            .select("whatsapp_phone_id, whatsapp_access_token")
            .eq("id", org_id)
            .limit(1)
            .execute()
        )
        row = res.data[0] if res.data else {}
        phone_id = phone_id or (row.get("whatsapp_phone_id") or "").strip()
        token = token or (row.get("whatsapp_access_token") or "").strip()
    result = await WhatsAppService().verify_credentials(phone_id, token)
    return {"status": "success", "data": result}


# --- Self-service Totem (kiosk) device provisioning (org_admin manages own org) ---
# Scoped to the caller's tenant via tenant_context. The device token is the kiosk's
# credential: shown once on creation, stored only as a SHA-256 hash, revocable.


@router.get("/kiosk-devices")
async def list_kiosk_devices(
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db),
):
    """List the caller org's kiosk devices (never the token — only metadata)."""
    _require_concrete_org(org_id)
    res = (
        db.client.table("kiosk_devices")
        .select("id, label, is_active, created_at, last_seen_at")
        .eq("organization_id", org_id)
        .order("created_at")
        .execute()
    )
    return {"status": "success", "data": res.data or []}


@router.post("/kiosk-devices")
async def create_kiosk_device(
    payload: KioskDeviceCreate,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db),
):
    """Provision a new kiosk device. Returns the token ONCE — it cannot be retrieved again."""
    _require_concrete_org(org_id)
    label = (payload.label or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="Informe um nome para o dispositivo.")

    token = generate_device_token()
    try:
        res = (
            db.client.table("kiosk_devices")
            .insert(
                {
                    "organization_id": org_id,
                    "label": label[:80],
                    "token_hash": hash_device_token(token),
                    "is_active": True,
                }
            )
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=400, detail="Erro ao criar dispositivo.")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Erro ao criar dispositivo de totem (org=%s)", org_id)
        raise HTTPException(status_code=400, detail="Erro ao criar dispositivo.") from e

    device = res.data[0]
    # The raw token is returned exactly once; only its hash is persisted.
    return {
        "status": "success",
        "data": {"id": device["id"], "label": device["label"], "token": token},
    }


@router.delete("/kiosk-devices/{device_id}")
async def revoke_kiosk_device(
    device_id: str,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db),
):
    """Revoke (deactivate) a kiosk device. The token stops resolving immediately."""
    _require_concrete_org(org_id)
    res = (
        db.client.table("kiosk_devices")
        .update({"is_active": False})
        .eq("id", device_id)
        .eq("organization_id", org_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado.")
    return {"status": "success", "data": {"revoked": True}}


@router.get("/", dependencies=[Depends(admin_required)])
async def list_organizations(db: SupabaseHandler = Depends(get_db)):
    try:
        allowed = verticals_for_product_line(settings.PRODUCT_LINE)
        result = (
            db.client.table("organizations")
            .select("*")
            .in_("vertical", allowed)
            .execute()
        )
        return {"status": "success", "data": result.data}
    except Exception as e:
        logger.exception("Erro ao listar organizações")
        raise HTTPException(status_code=400, detail="Erro ao listar organizações.") from e
