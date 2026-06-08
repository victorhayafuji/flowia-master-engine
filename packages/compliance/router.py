"""LGPD compliance API — DSAR export/erase, privacy notice."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from packages.auth_core.database import db
from packages.auth_core.dependencies import auth_required, validated_tenant_context
from packages.auth_core.tenant import set_tenant_context
from packages.compliance import service as compliance_service
from packages.compliance.consent import PRIVACY_NOTICE_VERSION, build_privacy_notice

router = APIRouter(prefix="/compliance", tags=["Compliance"])


@router.get("/privacy-notice")
async def get_privacy_notice(org_id: str | None = None):
    org_name = "salão"
    if org_id and db.client:
        try:
            row = db.client.table("organizations").select("name").eq("id", org_id).limit(1).execute()
            if row.data:
                org_name = row.data[0].get("name") or org_name
        except Exception:
            pass
    return {
        "version": PRIVACY_NOTICE_VERSION,
        "text": build_privacy_notice(org_name),
    }


@router.get("/patients/{patient_id}/export", dependencies=[Depends(auth_required)])
async def export_patient(patient_id: str, org_id: str = Depends(validated_tenant_context)):
    with set_tenant_context(org_id):
        try:
            data = compliance_service.export_data(org_id, patient_id)
            return {"status": "success", "data": data}
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/patients/{patient_id}/erase", dependencies=[Depends(auth_required)])
async def erase_patient(patient_id: str, org_id: str = Depends(validated_tenant_context)):
    with set_tenant_context(org_id):
        try:
            result = compliance_service.erase_data(org_id, patient_id)
            return {"status": "success", "data": result}
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
