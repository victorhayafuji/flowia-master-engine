"""Organization CRUD and WhatsApp credentials."""
from fastapi import APIRouter, Depends, HTTPException

from apps.salon.domain.catalog.helpers import (
    MVP_ALLOWED_VERTICAL,
    raise_on_whatsapp_phone_conflict,
    verticals_for_product_line,
)
from apps.salon.domain.catalog.schemas import OrganizationBase, OrganizationWhatsAppUpdate
from packages.auth_core.config import settings
from packages.auth_core.database import SupabaseHandler
from packages.auth_core.dependencies import admin_required, get_db
from packages.auth_core.exceptions import BusinessLogicError

router = APIRouter()


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
        raise HTTPException(status_code=400, detail=str(e)) from e


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
        raise HTTPException(status_code=400, detail=str(e)) from e


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
        raise HTTPException(status_code=400, detail=str(e)) from e
