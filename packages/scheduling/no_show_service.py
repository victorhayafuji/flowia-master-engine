import logging
from datetime import datetime, timedelta, timezone

from packages.auth_core.database import db
from packages.models.enums import AppointmentStatus

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = {
    AppointmentStatus.PENDING.value,
    AppointmentStatus.CONFIRMED.value,
}


class NoShowService:
    """Marks overdue appointments as no_show and increments patient no_show_count."""

    def detect_no_shows(self, now: datetime | None = None) -> int:
        if not db.client:
            return 0

        reference = now or datetime.now(timezone.utc)
        response = (
            db.client.table("appointments")
            .select("id, patient_id, organization_id, scheduled_at, duration_minutes, status")
            .in_("status", list(_ACTIVE_STATUSES))
            .lt("scheduled_at", reference.isoformat())
            .execute()
        )

        marked = 0
        for row in response.data or []:
            end_time = _appointment_end(row)
            if end_time > reference:
                continue

            # tenant-scope-exempt: platform-wide cron scans every org on purpose;
            # the status flip is keyed by the appointment's own PK from that scan.
            db.client.table("appointments").update(
                {"status": AppointmentStatus.NO_SHOW.value}
            ).eq("id", row["id"]).execute()

            patient_id = row.get("patient_id")
            if patient_id:
                # Scope the patients write by the org of the appointment being
                # processed. The cron scans every org on purpose (platform-wide),
                # but each individual write stays org-scoped (defense-in-depth).
                self._increment_no_show_count(patient_id, row.get("organization_id"))

            marked += 1
            logger.info("Marked appointment %s as no_show", row["id"])

        return marked

    def _increment_no_show_count(
        self, patient_id: str, organization_id: str | None = None
    ) -> None:
        if not db.client:
            return
        select_query = (
            db.client.table("patients")
            .select("no_show_count")
            .eq("id", patient_id)
        )
        if organization_id and organization_id != "ALL":
            select_query = select_query.eq("organization_id", organization_id)
        current = select_query.maybe_single().execute()
        count = (current.data or {}).get("no_show_count") or 0
        update_query = (
            db.client.table("patients")
            .update({"no_show_count": count + 1})
            .eq("id", patient_id)
        )
        if organization_id and organization_id != "ALL":
            update_query = update_query.eq("organization_id", organization_id)
        update_query.execute()


def _appointment_end(row: dict) -> datetime:
    start = datetime.fromisoformat(row["scheduled_at"].replace("Z", "+00:00"))
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    duration = row.get("duration_minutes") or 30
    return start + timedelta(minutes=duration)
