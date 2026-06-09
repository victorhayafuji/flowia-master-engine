"""Availability slot calculation."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import UUID

from packages.models.enums import AppointmentStatus
from packages.scheduling.services.config_helpers import (
    WEEKDAY_KEYS,
    SchedulingConfigMixin,
    parse_hhmm,
)
from packages.scheduling.timezone_utils import local_day_utc_bounds, now_local_naive


class SchedulingAvailabilityMixin(SchedulingConfigMixin):
    def _get_day_appointments(self, professional_id: UUID, target_date: date) -> list[dict]:
        tzname = self._get_org_config()["timezone"]
        start_of_day, end_of_day = local_day_utc_bounds(target_date, tzname)
        response = (
            self.db.client.table("appointments")
            .select("scheduled_at, duration_minutes, status")
            .eq("professional_id", str(professional_id))
            .gte("scheduled_at", start_of_day)
            .lte("scheduled_at", end_of_day)
            .neq("status", AppointmentStatus.CANCELLED.value)
            .neq("status", AppointmentStatus.NO_SHOW.value)
            .execute()
        )
        return response.data or []

    def _get_day_blocks(self, professional_id: UUID, target_date: date) -> list[dict]:
        import logging

        from packages.auth_core.tenant import get_current_org_id

        logger = logging.getLogger(__name__)
        start_of_day = datetime.combine(target_date, datetime.min.time()).isoformat()
        end_of_day = datetime.combine(target_date, datetime.max.time()).isoformat()
        org_id = get_current_org_id()
        try:
            query = (
                self.db.client.table("schedule_blocks")
                .select("professional_id, starts_at, ends_at")
                .lte("starts_at", end_of_day)
                .gte("ends_at", start_of_day)
            )
            if org_id and org_id != "ALL":
                query = query.eq("organization_id", org_id)
            response = query.execute()
        except Exception as exc:
            logger.debug("schedule_blocks lookup skipped: %s", exc)
            return []
        rows = response.data or []
        return [r for r in rows if r.get("professional_id") in (None, str(professional_id))]

    async def get_available_slots(
        self, professional_id: UUID, target_date: date, service_duration: int
    ) -> list[str]:
        schedule = self._get_professional_schedule(professional_id)
        org_config = self._get_org_config()

        weekday_key = WEEKDAY_KEYS[target_date.weekday()]
        day_hours = (schedule["working_hours"] or {}).get(weekday_key)
        if not day_hours:
            return []

        work_start = datetime.combine(target_date, parse_hhmm(day_hours["start"]))
        work_end = datetime.combine(target_date, parse_hhmm(day_hours["end"]))
        buffer = schedule["buffer"]
        slot_step = org_config["slot_step"]
        tzname = org_config["timezone"]

        blocked: list[tuple[datetime, datetime]] = []
        for pause in schedule["break_times"]:
            try:
                blocked.append(
                    (
                        datetime.combine(target_date, parse_hhmm(pause["start"])),
                        datetime.combine(target_date, parse_hhmm(pause["end"])),
                    )
                )
            except (KeyError, ValueError):
                continue

        for appt in self._get_day_appointments(professional_id, target_date):
            appt_start = self._to_local_naive(appt["scheduled_at"], tzname)
            appt_end = appt_start + timedelta(minutes=appt["duration_minutes"])
            blocked.append((appt_start - timedelta(minutes=buffer), appt_end + timedelta(minutes=buffer)))

        for block in self._get_day_blocks(professional_id, target_date):
            blocked.append(
                (
                    self._to_local_naive(block["starts_at"], tzname),
                    self._to_local_naive(block["ends_at"], tzname),
                )
            )

        earliest = now_local_naive(tzname) + timedelta(hours=org_config["min_notice_hours"])

        available_slots: list[str] = []
        current = work_start
        while current + timedelta(minutes=service_duration) <= work_end:
            slot_end = current + timedelta(minutes=service_duration)
            if current >= earliest and not any(
                current < b_end and slot_end > b_start for b_start, b_end in blocked
            ):
                available_slots.append(current.isoformat())
            current += timedelta(minutes=slot_step)

        return available_slots
