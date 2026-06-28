"""Service catalog and service-professional M:N."""
import logging

from fastapi import APIRouter, Depends, HTTPException

from apps.salon.domain.catalog.helpers import sync_service_professionals
from apps.salon.domain.catalog.schemas import (
    ServiceCatalogBase,
    ServiceCatalogUpdate,
    ServiceProfessionalsUpdate,
)
from packages.auth_core.database import SupabaseHandler
from packages.auth_core.dependencies import auth_required, get_db, tenant_context
from packages.auth_core.tenant import set_tenant_context

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/services", dependencies=[Depends(auth_required)])
async def create_service(
    service: ServiceCatalogBase,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db),
):
    with set_tenant_context(org_id):
        try:
            insert_data = service.model_dump(mode="json")
            professional_ids = insert_data.pop("professional_ids", None)
            if org_id and org_id != "ALL":
                insert_data["organization_id"] = org_id
            result = db.client.table("service_catalog").insert(insert_data).execute()
            if not result.data:
                raise HTTPException(status_code=400, detail="Erro ao criar serviço")
            created = result.data[0]
            if professional_ids is not None:
                sync_service_professionals(db, org_id, created["id"], professional_ids)
            return {"status": "success", "data": created}
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Erro ao criar serviço (org=%s)", org_id)
            raise HTTPException(status_code=400, detail="Erro ao criar serviço.") from e


@router.put("/services/{service_id}", dependencies=[Depends(auth_required)])
async def update_service(
    service_id: str,
    payload: ServiceCatalogUpdate,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db),
):
    with set_tenant_context(org_id):
        try:
            data = payload.model_dump(mode="json", exclude_unset=True)
            professional_ids = data.pop("professional_ids", None)
            updated = None
            if data:
                query = db.client.table("service_catalog").update(data).eq("id", service_id)
                if org_id and org_id != "ALL":
                    query = query.eq("organization_id", org_id)
                result = query.execute()
                if not result.data:
                    raise HTTPException(status_code=404, detail="Serviço não encontrado")
                updated = result.data[0]
            if professional_ids is not None:
                sync_service_professionals(db, org_id, service_id, professional_ids)
            if updated is None:
                query = db.client.table("service_catalog").select("*").eq("id", service_id)
                if org_id and org_id != "ALL":
                    query = query.eq("organization_id", org_id)
                fetched = query.maybe_single().execute()
                updated = fetched.data if fetched else None
                if updated is None:
                    raise HTTPException(status_code=404, detail="Serviço não encontrado")
            return {"status": "success", "data": updated}
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Erro ao atualizar serviço %s (org=%s)", service_id, org_id)
            raise HTTPException(status_code=400, detail="Erro ao atualizar serviço.") from e


@router.get("/services/{service_id}/professionals", dependencies=[Depends(auth_required)])
async def list_service_professionals(
    service_id: str,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db),
):
    with set_tenant_context(org_id):
        try:
            query = db.client.table("service_professionals").select(
                "professional_id, professional:professionals(id, name, specialty, is_active)"
            ).eq("service_id", service_id)
            if org_id and org_id != "ALL":
                query = query.eq("organization_id", org_id)
            result = query.execute()
            return {"status": "success", "data": result.data}
        except Exception as e:
            logger.exception(
                "Erro ao listar profissionais do serviço %s (org=%s)", service_id, org_id
            )
            raise HTTPException(
                status_code=400, detail="Erro ao listar profissionais do serviço."
            ) from e


@router.put("/services/{service_id}/professionals", dependencies=[Depends(auth_required)])
async def set_service_professionals(
    service_id: str,
    payload: ServiceProfessionalsUpdate,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db),
):
    with set_tenant_context(org_id):
        try:
            sync_service_professionals(db, org_id, service_id, payload.professional_ids)
            return {
                "status": "success",
                "data": {
                    "service_id": service_id,
                    "professional_ids": [str(p) for p in payload.professional_ids],
                },
            }
        except Exception as e:
            logger.exception(
                "Erro ao definir elegibilidade do serviço %s (org=%s)", service_id, org_id
            )
            raise HTTPException(
                status_code=400, detail="Erro ao definir profissionais do serviço."
            ) from e


@router.get("/services", dependencies=[Depends(auth_required)])
async def list_services(
    include_inactive: bool = False,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db),
):
    with set_tenant_context(org_id):
        try:
            query = db.client.table("service_catalog").select("*")
            if org_id and org_id != "ALL":
                query = query.eq("organization_id", org_id)
            if not include_inactive:
                query = query.eq("is_active", True)
            result = query.execute()
            services = result.data or []

            # Attach M:N eligibility so the UI can filter services by professional.
            # Empty list = no specific eligibility → all active professionals (fallback).
            sp_query = db.client.table("service_professionals").select("service_id, professional_id")
            if org_id and org_id != "ALL":
                sp_query = sp_query.eq("organization_id", org_id)
            eligibility: dict[str, list[str]] = {}
            for row in sp_query.execute().data or []:
                sid, pid = row.get("service_id"), row.get("professional_id")
                if sid and pid:
                    eligibility.setdefault(sid, []).append(pid)
            # Mirror list_eligible_professionals priority: M:N → legacy FK → empty (all).
            for svc in services:
                mn = eligibility.get(svc["id"], [])
                if not mn and svc.get("professional_id"):
                    mn = [svc["professional_id"]]
                svc["professional_ids"] = mn

            return {"status": "success", "data": services}
        except Exception as e:
            logger.exception("Erro ao listar serviços (org=%s)", org_id)
            raise HTTPException(status_code=400, detail="Erro ao listar serviços.") from e


@router.delete("/services/{service_id}", dependencies=[Depends(auth_required)])
async def deactivate_service(
    service_id: str,
    org_id: str = Depends(tenant_context),
    db: SupabaseHandler = Depends(get_db),
):
    with set_tenant_context(org_id):
        try:
            query = db.client.table("service_catalog").update({"is_active": False}).eq("id", service_id)
            if org_id and org_id != "ALL":
                query = query.eq("organization_id", org_id)
            result = query.execute()
            if not result.data:
                raise HTTPException(status_code=404, detail="Serviço não encontrado")
            return {"status": "success", "data": result.data[0]}
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Erro ao desativar serviço %s (org=%s)", service_id, org_id)
            raise HTTPException(status_code=400, detail="Erro ao desativar serviço.") from e
