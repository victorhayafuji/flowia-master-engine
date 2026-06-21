from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException

from packages.auth_core.database import db
from packages.auth_core.dependencies import auth_required, professional_scope, validated_tenant_context
from packages.models.enums import AppointmentStatus
from packages.scheduling import financial

router = APIRouter(tags=["Salon Dashboard"])

# Statuses that count as "still going to happen" for the operational board.
_OPEN_STATUSES = (
    AppointmentStatus.PENDING,
    AppointmentStatus.CONFIRMED,
    AppointmentStatus.ARRIVED,
    AppointmentStatus.IN_PROGRESS,
)
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


def _parse_aware(scheduled_at: str | None) -> datetime | None:
    """Parse a stored ``scheduled_at`` (UTC ISO, maybe ``Z``) into an aware datetime."""
    if not scheduled_at:
        return None
    try:
        dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=ZoneInfo("UTC"))


def _appt_day_in_tz(scheduled_at: str | None, tz: ZoneInfo) -> str | None:
    """Calendar day (YYYY-MM-DD) of an appointment in the org timezone.

    Uses the raw string only as a last-resort fallback — slicing the UTC string
    misclassifies appointments across the day boundary at night.
    """
    dt = _parse_aware(scheduled_at)
    if dt is None:
        return scheduled_at[:10] if scheduled_at else None
    return dt.astimezone(tz).date().isoformat()


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
            if status == AppointmentStatus.IN_PROGRESS:
                counts["in_progress"] += 1
            elif status == AppointmentStatus.COMPLETED:
                counts["completed"] += 1
            elif status == AppointmentStatus.NO_SHOW:
                counts["no_show"] += 1
            appt_dt = _parse_aware(appt.get("scheduled_at"))
            if status in _OPEN_STATUSES and appt_dt is not None and appt_dt >= now:
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


@router.get("/dashboard/agent-summary", dependencies=[Depends(auth_required)])
async def get_agent_summary(
    org_id: str = Depends(validated_tenant_context),
    prof_scope: str | None = Depends(professional_scope),
):
    """Lite agent observability for salon owners — counts only, no PII or token data."""
    if prof_scope:
        return {
            "status": "success",
            "data": {
                "handoffsPending": 0,
                "appointmentsWhatsappToday": 0,
                "conversationsThisWeek": 0,
            },
        }

    try:
        _, today, end_today = _day_bounds(org_id)
        since_week = (datetime.utcnow() - timedelta(days=7)).isoformat()

        handoffs_pending = 0
        if org_id and org_id != "ALL":
            handoff_query = (
                db.client.table("patients")
                .select("id", count="exact")
                .eq("organization_id", org_id)
                .eq("is_active", True)
                .not_.is_("handoff_requested_at", "null")
            )
            handoffs_pending = handoff_query.execute().count or 0

        appt_query = (
            db.client.table("appointments")
            .select("id", count="exact")
            .eq("source", "whatsapp")
            .gte("scheduled_at", today.isoformat())
            .lte("scheduled_at", end_today.isoformat())
        )
        if org_id and org_id != "ALL":
            appt_query = appt_query.eq("organization_id", org_id)
        appointments_whatsapp_today = appt_query.execute().count or 0

        metrics_query = (
            db.client.table("conversation_metrics")
            .select("thread_id")
            .gte("created_at", since_week)
            .limit(5000)
        )
        if org_id and org_id != "ALL":
            metrics_query = metrics_query.eq("organization_id", org_id)
        metric_rows = metrics_query.execute().data or []
        conversations_this_week = len(
            {row["thread_id"] for row in metric_rows if row.get("thread_id")}
        )

        return {
            "status": "success",
            "data": {
                "handoffsPending": handoffs_pending,
                "appointmentsWhatsappToday": appointments_whatsapp_today,
                "conversationsThisWeek": conversations_this_week,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _financial_period_bounds(org_id: str | None):
    """Day / month / year [start, end] windows in the org timezone."""
    tzname = _get_org_timezone(org_id)
    try:
        tz = ZoneInfo(tzname)
    except Exception:
        tz = ZoneInfo(_DEFAULT_TZ)
    now = datetime.now(tz)

    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    month_start = day_start.replace(day=1)
    if now.month == 12:
        next_month = month_start.replace(year=now.year + 1, month=1)
    else:
        next_month = month_start.replace(month=now.month + 1)
    month_end = next_month - timedelta(microseconds=1)
    year_start = day_start.replace(month=1, day=1)
    year_end = day_start.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)

    return {
        "day": (day_start, day_end),
        "month": (month_start, month_end),
        "year": (year_start, year_end),
    }


@router.get("/dashboard/financial", dependencies=[Depends(auth_required)])
async def get_dashboard_financial(
    org_id: str = Depends(validated_tenant_context),
    prof_scope: str | None = Depends(professional_scope),
):
    """Faturado / A Faturar / Perda by Day / Month / Year (org timezone).

    Amounts come from the joined ``service_catalog.price``; the status→category
    rule lives in ``packages.scheduling.financial`` (single source of truth).
    """
    try:
        bounds = _financial_period_bounds(org_id)

        def summary_for(start: datetime, end: datetime):
            query = db.client.table("appointments").select(
                "status, service:service_catalog(price)"
            )
            if org_id and org_id != "ALL":
                query = query.eq("organization_id", org_id)
            if prof_scope:
                query = query.eq("professional_id", prof_scope)
            query = query.gte("scheduled_at", start.isoformat()).lte("scheduled_at", end.isoformat())
            return financial.summarize(query.execute().data or [])

        data = {period: summary_for(start, end) for period, (start, end) in bounds.items()}
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/dashboard/professional-kpi", dependencies=[Depends(auth_required)])
async def get_professional_kpi(
    date: str | None = None,
    org_id: str = Depends(validated_tenant_context),
    prof_scope: str | None = Depends(professional_scope),
):
    """Per-professional appointments + unique clients for the selected day vs prev vs next.

    ``date`` is YYYY-MM-DD in the org timezone (default: today). ``appointments`` is
    the throughput metric; ``clients`` counts distinct ``patient_id`` (proxy for
    unique customers — see limitations).
    """
    try:
        tzname = _get_org_timezone(org_id)
        try:
            tz = ZoneInfo(tzname)
        except Exception:
            tz = ZoneInfo(_DEFAULT_TZ)

        if date:
            try:
                selected = datetime.fromisoformat(date).replace(tzinfo=tz)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="date deve ser YYYY-MM-DD") from exc
        else:
            selected = datetime.now(tz)
        selected = selected.replace(hour=0, minute=0, second=0, microsecond=0)

        prev_day = selected - timedelta(days=1)
        next_day = selected + timedelta(days=1)
        # Query the whole [prev, next] window once, then bucket in Python.
        window_start = prev_day
        window_end = next_day.replace(hour=23, minute=59, second=59, microsecond=999999)

        prof_query = db.client.table("professionals").select("id, name").eq("is_active", True)
        if org_id and org_id != "ALL":
            prof_query = prof_query.eq("organization_id", org_id)
        if prof_scope:
            prof_query = prof_query.eq("id", prof_scope)
        professionals = prof_query.execute().data or []

        appt_query = db.client.table("appointments").select(
            "professional_id, patient_id, scheduled_at, status"
        )
        if org_id and org_id != "ALL":
            appt_query = appt_query.eq("organization_id", org_id)
        if prof_scope:
            appt_query = appt_query.eq("professional_id", prof_scope)
        appt_query = (
            appt_query.gte("scheduled_at", window_start.isoformat())
            .lte("scheduled_at", window_end.isoformat())
            .neq("status", AppointmentStatus.CANCELLED.value)
        )
        appointments = appt_query.execute().data or []

        day_keys = {
            "prev": prev_day.date().isoformat(),
            "current": selected.date().isoformat(),
            "next": next_day.date().isoformat(),
        }

        def empty_bucket():
            return {"appointments": 0, "clients": set()}

        per_prof: dict[str, dict[str, dict]] = {
            p["id"]: {k: empty_bucket() for k in day_keys} for p in professionals
        }

        for appt in appointments:
            pid = appt.get("professional_id")
            if pid not in per_prof:
                continue
            appt_day = _appt_day_in_tz(appt.get("scheduled_at"), tz)
            slot = next((k for k, v in day_keys.items() if v == appt_day), None)
            if slot is None:
                continue
            bucket = per_prof[pid][slot]
            bucket["appointments"] += 1
            if appt.get("patient_id"):
                bucket["clients"].add(appt["patient_id"])

        def serialize(bucket):
            return {"appointments": bucket["appointments"], "clients": len(bucket["clients"])}

        rows = [
            {
                "professional": prof,
                "prev": serialize(per_prof[prof["id"]]["prev"]),
                "current": serialize(per_prof[prof["id"]]["current"]),
                "next": serialize(per_prof[prof["id"]]["next"]),
            }
            for prof in professionals
        ]

        return {
            "status": "success",
            "data": {
                "dates": day_keys,
                "professionals": rows,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
