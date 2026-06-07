import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from packages.models.enums import ReminderType
from packages.scheduling.reminder_repository import ReminderRepository

logger = logging.getLogger(__name__)


class ReminderService:
    """Creates and processes appointment reminders. Delivery is stubbed until WhatsApp API is ready."""

    def __init__(self, repository: ReminderRepository | None = None):
        self.repository = repository or ReminderRepository()

    def create_appointment_reminders(self, appointment: dict[str, Any]) -> list[dict[str, Any]]:
        scheduled_at = _parse_datetime(appointment["scheduled_at"])
        organization_id = appointment["organization_id"]
        appointment_id = appointment["id"]
        patient_id = appointment["patient_id"]

        reminders: list[dict[str, Any]] = []
        specs = [
            (ReminderType.CONFIRMATION_24H, scheduled_at - timedelta(hours=24)),
            (ReminderType.REMINDER_2H, scheduled_at - timedelta(hours=2)),
        ]

        for reminder_type, when in specs:
            if when <= datetime.now(timezone.utc):
                continue
            row = self.repository.create_reminder(
                organization_id=organization_id,
                appointment_id=appointment_id,
                patient_id=patient_id,
                reminder_type=reminder_type,
                scheduled_for=when,
            )
            if row:
                reminders.append(row)

        logger.info(
            "Created %s reminders for appointment %s",
            len(reminders),
            appointment_id,
        )
        return reminders

    def cancel_reminders_for_appointment(self, appointment_id: str | UUID) -> int:
        count = self.repository.cancel_pending_for_appointment(str(appointment_id))
        logger.info("Cancelled %s pending reminders for appointment %s", count, appointment_id)
        return count

    def process_pending_reminders(self) -> int:
        """Stub delivery: mark due reminders as sent and log payload for future WhatsApp hook."""
        now = datetime.now(timezone.utc)
        pending = self.repository.list_pending_due(now)
        processed = 0

        for reminder in pending:
            try:
                logger.info(
                    "[reminder-stub] org=%s appt=%s type=%s patient=%s scheduled=%s",
                    reminder.get("organization_id"),
                    reminder.get("appointment_id"),
                    reminder.get("type"),
                    reminder.get("patient_id"),
                    reminder.get("scheduled_for"),
                )
                self.repository.mark_sent(reminder["id"])
                processed += 1
            except Exception as exc:
                logger.exception("Failed to process reminder %s", reminder.get("id"))
                self.repository.mark_failed(reminder["id"], str(exc))

        return processed


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
