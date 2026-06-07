from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from packages.auth_core.database import db
from packages.auth_core.dependencies import auth_required, validated_tenant_context

router = APIRouter(tags=["Salon Dashboard"])


@router.get("/dashboard/stats", dependencies=[Depends(auth_required)])
async def get_dashboard_stats(org_id: str = Depends(validated_tenant_context)):
    try:
        query_patients = db.client.table("patients").select("*", count="exact")
        if org_id and org_id != "ALL":
            query_patients = query_patients.eq("organization_id", org_id)
        res_patients = query_patients.limit(1).execute()

        tz = timezone(timedelta(hours=-3))
        now = datetime.now(tz)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_today = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        query_today = db.client.table("appointments").select("id", count="exact")
        if org_id and org_id != "ALL":
            query_today = query_today.eq("organization_id", org_id)
        query_today = query_today.gte("scheduled_at", today.isoformat())
        query_today = query_today.lte("scheduled_at", end_today.isoformat())
        res_today = query_today.execute()

        query_upcoming = db.client.table("appointments").select(
            "*, patient:patients(name), service:service_catalog(name)"
        )
        if org_id and org_id != "ALL":
            query_upcoming = query_upcoming.eq("organization_id", org_id)
        query_upcoming = (
            query_upcoming.gte("scheduled_at", now.isoformat()).order("scheduled_at").limit(5)
        )
        res_upcoming = query_upcoming.execute()

        return {
            "status": "success",
            "data": {
                "patients": res_patients.count or 0,
                "appointmentsToday": res_today.count or 0,
                "upcoming": res_upcoming.data,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
