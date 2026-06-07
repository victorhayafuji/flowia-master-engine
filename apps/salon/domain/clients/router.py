from fastapi import APIRouter, Depends, HTTPException

from apps.salon.domain.clients.schemas import PatientBase
from packages.auth_core.database import SupabaseHandler
from packages.auth_core.dependencies import auth_required, get_db, tenant_context
from packages.auth_core.tenant import set_tenant_context

router = APIRouter(prefix="/patients", tags=["Patients"])

@router.post("/", dependencies=[Depends(auth_required)])
async def create_patient(
    patient: PatientBase,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db)
):
    with set_tenant_context(org_id):
        try:
            insert_data = patient.model_dump(mode='json')
            if org_id and org_id != 'ALL':
                insert_data["organization_id"] = org_id
            result = db.client.table("patients").insert(insert_data).execute()
            if not result.data:
                raise HTTPException(status_code=400, detail="Erro ao criar paciente")
            return {"status": "success", "data": result.data[0]}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

@router.get("/", dependencies=[Depends(auth_required)])
async def list_patients(
    include_inactive: bool = False,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db)
):
    with set_tenant_context(org_id):
        try:
            query = db.client.table("patients").select("*")
            if org_id and org_id != 'ALL':
                query = query.eq("organization_id", org_id)
            if not include_inactive:
                query = query.eq("is_active", True)
            result = query.execute()
            return {"status": "success", "data": result.data}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{patient_id}", dependencies=[Depends(auth_required)])
async def deactivate_patient(
    patient_id: str,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db)
):
    """Soft delete: marca o cliente como inativo, preservando histórico de agendamentos."""
    with set_tenant_context(org_id):
        try:
            query = db.client.table("patients").update({"is_active": False}).eq("id", patient_id)
            if org_id and org_id != 'ALL':
                query = query.eq("organization_id", org_id)
            result = query.execute()
            if not result.data:
                raise HTTPException(status_code=404, detail="Cliente não encontrado")
            return {"status": "success", "data": result.data[0]}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
