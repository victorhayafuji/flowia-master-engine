"""Shared scheduling config and DB helpers."""
from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Any
from uuid import UUID

from packages.auth_core.database import db
from packages.auth_core.tenant import get_current_org_id

logger = logging.getLogger(__name__)

WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DEFAULT_SLOT_MINUTES = 15
DEFAULT_TIMEZONE = "America/Sao_Paulo"
DEFAULT_WORKING_HOURS = {
    "mon": {"start": "08:00", "end": "18:00"},
    "tue": {"start": "08:00", "end": "18:00"},
    "wed": {"start": "08:00", "end": "18:00"},
    "thu": {"start": "08:00", "end": "18:00"},
    "fri": {"start": "08:00", "end": "18:00"},
}


def parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")[:2]
    return time(int(hour), int(minute))


class SchedulingConfigMixin:
    db = db

    def _get_professional_schedule(self, professional_id: UUID) -> dict[str, Any]:
        res = (
            self.db.client.table("professionals")
            .select("working_hours, break_times, appointment_buffer_minutes")
            .eq("id", str(professional_id))
            .maybe_single()
            .execute()
        )
        row = (res.data if res else None) or {}
        buffer = row.get("appointment_buffer_minutes")
        return {
            "working_hours": row.get("working_hours") or DEFAULT_WORKING_HOURS,
            "break_times": row.get("break_times") or [],
            "buffer": int(buffer) if buffer is not None else 0,
        }

    def _get_org_config(self) -> dict[str, Any]:
        org_id = get_current_org_id()
        slot_step = DEFAULT_SLOT_MINUTES
        min_notice_hours = 0
        tzname = DEFAULT_TIMEZONE
        if org_id and org_id != "ALL":
            try:
                res = (
                    self.db.client.table("organizations")
                    .select("settings, timezone")
                    .eq("id", org_id)
                    .maybe_single()
                    .execute()
                )
                row = (res.data if res else None) or {}
                tzname = row.get("timezone") or DEFAULT_TIMEZONE
                scheduling = (row.get("settings") or {}).get("scheduling") or {}
                slot_step = int(scheduling.get("default_slot_minutes") or DEFAULT_SLOT_MINUTES)
                min_notice_hours = int(scheduling.get("min_notice_hours") or 0)
            except Exception as exc:
                logger.warning("Falling back to default scheduling config: %s", exc)
        return {"slot_step": slot_step, "min_notice_hours": min_notice_hours, "timezone": tzname}

    @staticmethod
    def _to_local_naive(raw: str, tzname: str) -> datetime:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt
        from packages.scheduling.timezone_utils import to_local_naive

        return to_local_naive(dt, tzname)
