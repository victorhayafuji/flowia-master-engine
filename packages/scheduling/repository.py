from datetime import date
from typing import Any

from packages.auth_core.database import db
from packages.scheduling.timezone_utils import DEFAULT_TIMEZONE, local_date_range_utc_bounds


class SchedulingRepository:
    def _org_timezone(self, org_id: str) -> str:
        if not org_id or org_id == "ALL":
            return DEFAULT_TIMEZONE
        try:
            res = (
                db.client.table("organizations")
                .select("timezone")
                .eq("id", org_id)
                .maybe_single()
                .execute()
            )
            row = (res.data if res else None) or {}
            return row.get("timezone") or DEFAULT_TIMEZONE
        except Exception:
            return DEFAULT_TIMEZONE

    def get_appointments_by_date_range(
        self,
        start_date: str,
        end_date: str,
        org_id: str,
        professional_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query = db.client.table("appointments").select(
            "*, patient:patients(name, phone), professional:professionals(name), service:service_catalog(name, price)"
        )

        if org_id and org_id != 'ALL':
            query = query.eq("organization_id", org_id)

        if professional_id:
            query = query.eq("professional_id", professional_id)

        tzname = self._org_timezone(org_id)
        start_iso, end_iso = local_date_range_utc_bounds(
            date.fromisoformat(start_date),
            date.fromisoformat(end_date),
            tzname,
        )
        query = query.gte("scheduled_at", start_iso)
        query = query.lte("scheduled_at", end_iso)

        result = query.execute()
        return result.data

    def update_appointment_date(self, appointment_id: str, new_date: str, org_id: str) -> list[dict[str, Any]]:
        query = db.client.table("appointments").update({"scheduled_at": new_date})
        if org_id and org_id != 'ALL':
            query = query.eq("organization_id", org_id)
        query = query.eq("id", appointment_id)

        result = query.execute()
        return result.data
