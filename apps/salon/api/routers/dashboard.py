from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException

from packages.auth_core.database import db
from packages.auth_core.dependencies import auth_required, professional_scope, validated_tenant_context

router = APIRouter(tags=["Salon Dashboard"])

# Statuses that count as "still going to happen" for the operational board.
_OPEN_STATUSES = ("pending", "confirmed", "arrived", "in_progress")
_DEFAULT_TZ = "America/Sao_Paulo"


def _get_org_timezone(org_id: str | None) -> str:
    if not org_id or org_id == "ALL":
        return _DEFAULT_TZ
    try:
        res = (
            db.client.table("organizations")
            .select("timezone")
            .eq("id", org_id)
            .maybe_single()
            .execute()
        )
        row = (res.data if res else None) or {}
        return row.get("timezone") or _DEFAULT_TZ
    except Exception:
        return _DEFAULT_TZ


def _day_bounds(org_id: str | None = None):
    tzname = _get_org_timezone(org_id)
    try:
        tz = ZoneInfo(tzname)
    except Exception:
        tz = ZoneInfo(_DEFAULT_TZ)
    now = datetime.now(tz)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_today = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    return now, today, end_today


@router.get("/dashboard/stats", dependencies=[Depends(auth_required)])
async def get_dashboard_stats(
    org_id: str = Depends(validated_tenant_context),
    prof_scope: str | None = Depends(professional_scope),
):
    try:
        patients_count = 0
        total_no_shows = 0
        if not prof_scope:
            query_patients = db.client.table("patients").select("no_show_count")
            if org_id and org_id != "ALL":
                query_patients = query_patients.eq("organization_id", org_id)
            patient_rows = query_patients.eq("is_active", True).execute().data or []
            patients_count = len(patient_rows)
            total_no_shows = sum(row.get("no_show_count") or 0 for row in patient_rows)

        now, today, end_today = _day_bounds(org_id)

        query_today = db.client.table("appointments").select("id", count="exact")
        if org_id and org_id != "ALL":
            query_today = query_today.eq("organization_id", org_id)
        if prof_scope:
            query_today = query_today.eq("professional_id", prof_scope)
        query_today = query_today.gte("scheduled_at", today.isoformat())
        query_today = query_today.lte("scheduled_at", end_today.isoformat())
        res_today = query_today.execute()

        query_upcoming = db.client.table("appointments").select(
            "*, patient:patients(name), professional:professionals(name), service:service_catalog(name)"
        )
        if org_id and org_id != "ALL":
            query_upcoming = query_upcoming.eq("organization_id", org_id)
        if prof_scope:
            query_upcoming = query_upcoming.eq("professional_id", prof_scope)
        query_upcoming = (
            query_upcoming.gte("scheduled_at", now.isoformat()).order("scheduled_at").limit(5)
        )
        res_upcoming = query_upcoming.execute()

        return {
            "status": "success",
            "data": {
                "patients": patients_count,
                "totalNoShows": total_no_shows,
                "appointmentsToday": res_today.count or 0,
                "upcoming": res_upcoming.data,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/dashboard/today-board", dependencies=[Depends(auth_required)])
async def get_today_board(
    org_id: str = Depends(validated_tenant_context),
    prof_scope: str | None = Depends(professional_scope),
):
    """Operational board for today: who attends, what, when, and current status."""
    try:
        now, today, end_today = _day_bounds(org_id)

        prof_query = db.client.table("professionals").select("id, name").eq("is_active", True)
        if org_id and org_id != "ALL":
            prof_query = prof_query.eq("organization_id", org_id)
        if prof_scope:
            prof_query = prof_query.eq("id", prof_scope)
        professionals = prof_query.execute().data or []

        appt_query = db.client.table("appointments").select(
            "id, scheduled_at, duration_minutes, status, professional_id, "
            "patient:patients(name), service:service_catalog(name)"
        )
        if org_id and org_id != "ALL":
            appt_query = appt_query.eq("organization_id", org_id)
        if prof_scope:
            appt_query = appt_query.eq("professional_id", prof_scope)
        appt_query = (
            appt_query.gte("scheduled_at", today.isoformat())
            .lte("scheduled_at", end_today.isoformat())
            .order("scheduled_at")
        )
        appointments = appt_query.execute().data or []

        counts = {"total": len(appointments), "in_progress": 0, "completed": 0, "no_show": 0, "upcoming": 0}
        by_professional: dict[str, list] = {}
        for appt in appointments:
            status = appt.get("status")
            if status == "in_progress":
                counts["in_progress"] += 1
            elif status == "completed":
                counts["completed"] += 1
            elif status == "no_show":
                counts["no_show"] += 1
            if status in _OPEN_STATUSES and appt.get("scheduled_at", "") >= now.isoformat():
                counts["upcoming"] += 1

            ends_at = None
            try:
                start = datetime.fromisoformat(appt["scheduled_at"].replace("Z", "+00:00"))
                ends_at = (start + timedelta(minutes=appt.get("duration_minutes") or 0)).isoformat()
            except (KeyError, ValueError):
                pass
            appt["ends_at"] = ends_at
            by_professional.setdefault(appt.get("professional_id"), []).append(appt)

        board = [
            {"professional": prof, "appointments": by_professional.get(prof["id"], [])}
            for prof in professionals
        ]
        # Appointments whose professional is inactive/missing still show under "Sem profissional".
        orphan = [a for a in appointments if a.get("professional_id") not in {p["id"] for p in professionals}]
        if orphan:
            board.append({"professional": {"id": None, "name": "Sem profissional"}, "appointments": orphan})

        return {
            "status": "success",
            "data": {"date": today.date().isoformat(), "counts": counts, "board": board},
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
