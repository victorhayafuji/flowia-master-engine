from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from packages.models.enums import ReminderType
from packages.scheduling.reminder_repository import ReminderRepository
from packages.scheduling.reminder_service import ReminderService


def _mock_response(data):
    class MockResponse:
        def __init__(self, payload):
            self.data = payload

    return MockResponse(data)


@pytest.fixture
def mock_reminder_db(mocker):
    mock_db = mocker.patch("packages.scheduling.reminder_repository.db")
    mock_db.client = MagicMock()
    return mock_db


@pytest.fixture
def repository(mock_reminder_db):
    return ReminderRepository()


@pytest.fixture
def reminder_service(repository):
    return ReminderService(repository=repository)


def test_create_appointment_reminders(repository, mock_reminder_db, reminder_service):
    mock_table = mock_reminder_db.client.table.return_value
    mock_insert = mock_table.insert.return_value
    mock_insert.execute.side_effect = [
        _mock_response([{"id": "r1", "type": ReminderType.CONFIRMATION_24H.value}]),
        _mock_response([{"id": "r2", "type": ReminderType.REMINDER_2H.value}]),
    ]

    scheduled = datetime.now(timezone.utc) + timedelta(days=2)
    appointment = {
        "id": str(uuid4()),
        "organization_id": str(uuid4()),
        "patient_id": str(uuid4()),
        "scheduled_at": scheduled.isoformat(),
    }

    reminders = reminder_service.create_appointment_reminders(appointment)
    assert len(reminders) == 2
    assert mock_insert.execute.call_count == 2


def test_cancel_reminders_for_appointment(repository, mock_reminder_db, reminder_service):
    mock_table = mock_reminder_db.client.table.return_value
    mock_update = mock_table.update.return_value
    mock_eq1 = mock_update.eq.return_value
    mock_eq2 = mock_eq1.eq.return_value
    mock_eq2.execute.return_value = _mock_response([{"id": "r1"}, {"id": "r2"}])

    count = reminder_service.cancel_reminders_for_appointment("appt-1")
    assert count == 2


def test_process_pending_reminders_marks_sent(repository, mock_reminder_db, reminder_service, mocker):
    pending = [
        {
            "id": "r1",
            "organization_id": "org",
            "appointment_id": "appt",
            "patient_id": "pat",
            "type": "reminder_2h",
            "scheduled_for": datetime.now(timezone.utc).isoformat(),
        }
    ]
    mocker.patch.object(repository, "list_pending_due", return_value=pending)
    mark_sent = mocker.patch.object(repository, "mark_sent")

    processed = reminder_service.process_pending_reminders()
    assert processed == 1
    mark_sent.assert_called_once_with("r1")


def test_process_pending_reminders_skips_past_slots(repository, mock_reminder_db, reminder_service):
    appointment = {
        "id": str(uuid4()),
        "organization_id": str(uuid4()),
        "patient_id": str(uuid4()),
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }
    reminders = reminder_service.create_appointment_reminders(appointment)
    assert reminders == []
