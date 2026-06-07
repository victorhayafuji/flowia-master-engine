from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from packages.auth_core.exceptions import BusinessLogicError, DoubleBookingError
from packages.models.enums import AppointmentStatus
from packages.scheduling.schemas import AppointmentBase
from packages.scheduling.service import SchedulingService


@pytest.fixture
def mock_scheduling_db(mocker):
    mock_handler = mocker.patch("packages.scheduling.service.db")
    return mock_handler


@pytest.fixture
def scheduling_service(mock_scheduling_db):
    return SchedulingService()


def _mock_response(data):
    class MockResponse:
        def __init__(self, payload):
            self.data = payload

    return MockResponse(data)


@pytest.mark.asyncio
async def test_create_appointment_success(scheduling_service, mock_scheduling_db, mocker):
    mocker.patch(
        "packages.scheduling.reminder_service.ReminderService.create_appointment_reminders",
        return_value=[],
    )
    mock_table = mock_scheduling_db.client.table.return_value
    mock_select = mock_table.select.return_value
    mock_eq = mock_select.eq.return_value
    mock_gte = mock_eq.gte.return_value
    mock_lte = mock_gte.lte.return_value
    mock_neq = mock_lte.neq.return_value

    empty = _mock_response([])
    mock_neq.execute.return_value = empty
    mock_lte.execute.return_value = empty

    mock_insert = mock_table.insert.return_value
    mock_insert.execute.return_value = _mock_response([{"id": "123"}])

    appointment = AppointmentBase(
        patient_id=uuid4(),
        professional_id=uuid4(),
        service_id=uuid4(),
        scheduled_at=datetime.now() + timedelta(days=1),
        duration_minutes=30,
    )

    result = await scheduling_service.create_appointment(appointment)
    assert result["id"] == "123"


@pytest.mark.asyncio
async def test_create_appointment_double_booking(scheduling_service, mock_scheduling_db):
    scheduled_time = datetime.now(timezone.utc) + timedelta(days=1)

    mock_table = mock_scheduling_db.client.table.return_value
    mock_select = mock_table.select.return_value
    mock_eq = mock_select.eq.return_value
    mock_neq_first = mock_eq.neq.return_value
    mock_gte = mock_eq.gte.return_value
    mock_lte = mock_gte.lte.return_value
    mock_neq_second = mock_lte.neq.return_value

    conflict = _mock_response([{
        "scheduled_at": scheduled_time.strftime("%Y-%m-%dT%H:%M:%S") + "Z",
        "duration_minutes": 30,
    }])
    mock_neq_first.execute.return_value = _mock_response([])
    mock_neq_second.execute.return_value = conflict

    appointment = AppointmentBase(
        patient_id=uuid4(),
        professional_id=uuid4(),
        service_id=uuid4(),
        scheduled_at=scheduled_time,
        duration_minutes=30,
    )

    with pytest.raises(DoubleBookingError) as exc_info:
        await scheduling_service.create_appointment(appointment)

    assert "agendamento" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_appointment_db_overlap_raises_409(scheduling_service, mock_scheduling_db, mocker):
    mocker.patch(
        "packages.scheduling.reminder_service.ReminderService.create_appointment_reminders",
        return_value=[],
    )
    mock_table = mock_scheduling_db.client.table.return_value
    mock_select = mock_table.select.return_value
    mock_eq = mock_select.eq.return_value
    mock_gte = mock_eq.gte.return_value
    mock_lte = mock_gte.lte.return_value
    mock_neq = mock_lte.neq.return_value
    mock_neq.execute.return_value = _mock_response([])

    mock_insert = mock_table.insert.return_value
    mock_insert.execute.side_effect = Exception("exclusion constraint appointments_no_overlap violated")

    appointment = AppointmentBase(
        patient_id=uuid4(),
        professional_id=uuid4(),
        service_id=uuid4(),
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
        duration_minutes=30,
    )

    with pytest.raises(DoubleBookingError):
        await scheduling_service.create_appointment(appointment)


@pytest.mark.asyncio
async def test_create_appointment_past_date(scheduling_service):
    appointment = AppointmentBase(
        patient_id=uuid4(),
        professional_id=uuid4(),
        service_id=uuid4(),
        scheduled_at=datetime.now() - timedelta(days=1),
        duration_minutes=30,
    )

    with pytest.raises(BusinessLogicError) as exc_info:
        await scheduling_service.create_appointment(appointment)

    assert "passado" in str(exc_info.value)


@pytest.mark.asyncio
async def test_update_appointment_status_success(scheduling_service, mock_scheduling_db):
    mock_table = mock_scheduling_db.client.table.return_value
    mock_update = mock_table.update.return_value
    mock_eq = mock_update.eq.return_value
    mock_eq.execute.return_value = _mock_response([{"id": "123", "status": "confirmed"}])

    result = await scheduling_service.update_appointment_status(uuid4(), AppointmentStatus.CONFIRMED)
    assert result["status"] == "confirmed"
