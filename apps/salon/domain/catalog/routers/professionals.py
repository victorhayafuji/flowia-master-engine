"""Professional CRUD."""
from fastapi import APIRouter, Depends, HTTPException

from apps.salon.domain.catalog.schemas import ProfessionalBase, ProfessionalUpdate
from packages.auth_core.database import SupabaseHandler
from packages.auth_core.dependencies import auth_required, get_db, tenant_context
from packages.auth_core.tenant import set_tenant_context

router = APIRouter()


@router.post("/professionals", dependencies=[Depends(auth_required)])
async def create_professional(
    professional: ProfessionalBase,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db),
):
    with set_tenant_context(org_id):
        try:
            insert_data = professional.model_dump(mode="json", exclude_none=True)
            if org_id and org_id != "ALL":
                insert_data["organization_id"] = org_id
            result = db.client.table("professionals").insert(insert_data).execute()
            if not result.data:
                raise HTTPException(status_code=400, detail="Erro ao criar profissional")
            return {"status": "success", "data": result.data[0]}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/professionals/{professional_id}", dependencies=[Depends(auth_required)])
async def update_professional(
    professional_id: str,
    payload: ProfessionalUpdate,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db),
):
    with set_tenant_context(org_id):
        try:
            data = payload.model_dump(mode="json", exclude_unset=True)
            if not data:
                raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")
            query = db.client.table("professionals").update(data).eq("id", professional_id)
            if org_id and org_id != "ALL":
                query = query.eq("organization_id", org_id)
            result = query.execute()
            if not result.data:
                raise HTTPException(status_code=404, detail="Profissional não encontrado")
            return {"status": "success", "data": result.data[0]}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/professionals", dependencies=[Depends(auth_required)])
async def list_professionals(
    include_inactive: bool = False,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db),
):
    with set_tenant_context(org_id):
        try:
            query = db.client.table("professionals").select("*")
            if org_id and org_id != "ALL":
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
    db: SupabaseHandler = Depends(get_db),
):
    with set_tenant_context(org_id):
        try:
            query = db.client.table("professionals").update({"is_active": False}).eq("id", professional_id)
            if org_id and org_id != "ALL":
                query = query.eq("organization_id", org_id)
            result = query.execute()
            if not result.data:
                raise HTTPException(status_code=404, detail="Profissional não encontrado")
            return {"status": "success", "data": result.data[0]}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
