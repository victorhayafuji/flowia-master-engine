from fastapi import APIRouter, Depends, HTTPException

from apps.salon.domain.catalog.schemas import OrganizationBase, ProfessionalBase, ServiceCatalogBase
from packages.auth_core.config import settings
from packages.auth_core.database import SupabaseHandler
from packages.auth_core.dependencies import admin_required, auth_required, get_db, tenant_context
from packages.auth_core.tenant import set_tenant_context
from packages.models.enums import Vertical

MVP_ALLOWED_VERTICAL = Vertical.SALON

PRODUCT_LINE_VERTICALS: dict[str, list[str]] = {
    "salon": [Vertical.SALON.value],
    "clinic": [Vertical.DENTAL.value, Vertical.MEDICAL.value],
}


def _verticals_for_product_line(product_line: str) -> list[str]:
    return PRODUCT_LINE_VERTICALS.get(product_line, [product_line])


router = APIRouter(prefix="/organizations", tags=["Organizations"])

@router.post("/", dependencies=[Depends(admin_required)])
async def create_organization(
    org: OrganizationBase,
    db: SupabaseHandler = Depends(get_db)
):
    """Creates a new organization. Restricted to super_admin."""
    if org.vertical != MVP_ALLOWED_VERTICAL:
        raise HTTPException(
            status_code=400,
            detail="No MVP apenas organizações do tipo salão (vertical=salon) são permitidas.",
        )
    try:
        insert_data = org.model_dump(mode='json')
        result = db.client.table("organizations").insert(insert_data).execute()

        if not result.data:
            raise HTTPException(status_code=400, detail="Erro ao criar organização")

        return {"status": "success", "data": result.data[0]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

@router.get("/", dependencies=[Depends(admin_required)])
async def list_organizations(
    db: SupabaseHandler = Depends(get_db)
):
    """Lists organizations for the active product line. Restricted to super_admin."""
    try:
        allowed = _verticals_for_product_line(settings.PRODUCT_LINE)
        result = (
            db.client.table("organizations")
            .select("*")
            .in_("vertical", allowed)
            .execute()
        )
        return {"status": "success", "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

@router.post("/services", dependencies=[Depends(auth_required)])
async def create_service(
    service: ServiceCatalogBase,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db)
):
    with set_tenant_context(org_id):
        try:
            insert_data = service.model_dump(mode='json')
            if org_id and org_id != 'ALL':
                insert_data["organization_id"] = org_id

            result = db.client.table("service_catalog").insert(insert_data).execute()
            if not result.data:
                raise HTTPException(status_code=400, detail="Erro ao criar serviço")
            return {"status": "success", "data": result.data[0]}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

@router.get("/services", dependencies=[Depends(auth_required)])
async def list_services(
    include_inactive: bool = False,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db)
):
    with set_tenant_context(org_id):
        try:
            query = db.client.table("service_catalog").select("*")
            if org_id and org_id != 'ALL':
                query = query.eq("organization_id", org_id)
            if not include_inactive:
                query = query.eq("is_active", True)
            result = query.execute()
            return {"status": "success", "data": result.data}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/services/{service_id}", dependencies=[Depends(auth_required)])
async def deactivate_service(
    service_id: str,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db)
):
    """Soft delete: desativa o serviço, liberando o nome para reuso e preservando histórico."""
    with set_tenant_context(org_id):
        try:
            query = db.client.table("service_catalog").update({"is_active": False}).eq("id", service_id)
            if org_id and org_id != 'ALL':
                query = query.eq("organization_id", org_id)
            result = query.execute()
            if not result.data:
                raise HTTPException(status_code=404, detail="Serviço não encontrado")
            return {"status": "success", "data": result.data[0]}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

@router.post("/professionals", dependencies=[Depends(auth_required)])
async def create_professional(
    professional: ProfessionalBase,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db)
):
    with set_tenant_context(org_id):
        try:
            insert_data = professional.model_dump(mode='json')
            if org_id and org_id != 'ALL':
                insert_data["organization_id"] = org_id

            result = db.client.table("professionals").insert(insert_data).execute()
            if not result.data:
                raise HTTPException(status_code=400, detail="Erro ao criar profissional")
            return {"status": "success", "data": result.data[0]}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

@router.get("/professionals", dependencies=[Depends(auth_required)])
async def list_professionals(
    include_inactive: bool = False,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db)
):
    with set_tenant_context(org_id):
        try:
            query = db.client.table("professionals").select("*")
            if org_id and org_id != 'ALL':
                query = query.eq("organization_id", org_id)
            if not include_inactive:
                query = query.eq("is_active", True)
            result = query.execute()
            return {"status": "success", "data": result.data}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/professionals/{professional_id}", dependencies=[Depends(auth_required)])
async def deactivate_professional(
    professional_id: str,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db)
):
    """Soft delete: desativa o profissional, preservando histórico de agendamentos."""
    with set_tenant_context(org_id):
        try:
            query = db.client.table("professionals").update({"is_active": False}).eq("id", professional_id)
            if org_id and org_id != 'ALL':
                query = query.eq("organization_id", org_id)
            result = query.execute()
            if not result.data:
                raise HTTPException(status_code=404, detail="Profissional não encontrado")
            return {"status": "success", "data": result.data[0]}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
