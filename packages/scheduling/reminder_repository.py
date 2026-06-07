import logging
from datetime import datetime
from typing import Any

from packages.auth_core.database import db
from packages.models.enums import ReminderStatus, ReminderType

logger = logging.getLogger(__name__)


class ReminderRepository:
    def __init__(self):
        self.db = db

    def create_reminder(
        self,
        *,
        organization_id: str,
        appointment_id: str,
        patient_id: str,
        reminder_type: ReminderType,
        scheduled_for: datetime,
        channel: str = "whatsapp",
    ) -> dict[str, Any] | None:
        if not self.db.client:
            return None

        payload = {
            "organization_id": organization_id,
            "appointment_id": appointment_id,
            "patient_id": patient_id,
            "type": reminder_type.value,
            "channel": channel,
            "scheduled_for": scheduled_for.isoformat(),
            "status": ReminderStatus.PENDING.value,
        }
        result = self.db.client.table("reminders").insert(payload).execute()
        return result.data[0] if result.data else None

    def list_pending_due(self, before: datetime, limit: int = 50) -> list[dict[str, Any]]:
        if not self.db.client:
            return []

        response = (
            self.db.client.table("reminders")
            .select("*")
            .eq("status", ReminderStatus.PENDING.value)
            .lte("scheduled_for", before.isoformat())
            .order("scheduled_for")
            .limit(limit)
            .execute()
        )
        return response.data or []

    def mark_sent(self, reminder_id: str) -> None:
        if not self.db.client:
            return
        now = datetime.utcnow().isoformat()
        self.db.client.table("reminders").update(
            {"status": ReminderStatus.SENT.value, "sent_at": now}
        ).eq("id", reminder_id).execute()

    def mark_failed(self, reminder_id: str, error_message: str) -> None:
        if not self.db.client:
            return
        self.db.client.table("reminders").update(
            {"status": ReminderStatus.FAILED.value, "error_message": error_message}
        ).eq("id", reminder_id).execute()

    def cancel_pending_for_appointment(self, appointment_id: str) -> int:
        if not self.db.client:
            return 0

        response = (
            self.db.client.table("reminders")
            .update({"status": ReminderStatus.CANCELLED.value})
            .eq("appointment_id", appointment_id)
            .eq("status", ReminderStatus.PENDING.value)
            .execute()
        )
        return len(response.data or [])
