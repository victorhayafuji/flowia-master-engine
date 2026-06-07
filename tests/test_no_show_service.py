from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from packages.models.enums import AppointmentStatus
from packages.scheduling.no_show_service import NoShowService


def _mock_response(data):
    class MockResponse:
        def __init__(self, payload):
            self.data = payload

    return MockResponse(data)


@pytest.fixture
def mock_no_show_db(mocker):
    mock_db = mocker.patch("packages.scheduling.no_show_service.db")
    mock_db.client = MagicMock()
    return mock_db


@pytest.fixture
def no_show_service():
    return NoShowService()


def test_detect_no_shows_marks_overdue(mock_no_show_db, no_show_service):
    past = datetime.now(timezone.utc) - timedelta(hours=3)
    mock_table = mock_no_show_db.client.table.return_value
    mock_select = mock_table.select.return_value
    mock_in = mock_select.in_.return_value
    mock_lt = mock_in.lt.return_value
    mock_lt.execute.return_value = _mock_response([
        {
            "id": "appt-1",
            "patient_id": "pat-1",
            "organization_id": "org-1",
            "scheduled_at": past.isoformat(),
            "duration_minutes": 30,
            "status": AppointmentStatus.CONFIRMED.value,
        }
    ])

    mock_update = mock_table.update.return_value
    mock_update.eq.return_value.execute.return_value = _mock_response([{"id": "appt-1"}])

    mock_patient_select = mock_table.select.return_value
    mock_patient_eq = mock_patient_select.eq.return_value
    mock_maybe = mock_patient_eq.maybe_single.return_value
    mock_maybe.execute.return_value = _mock_response({"no_show_count": 0})

    marked = no_show_service.detect_no_shows(now=datetime.now(timezone.utc))
    assert marked == 1
