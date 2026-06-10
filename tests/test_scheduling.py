from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock
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


# A Wednesday — used so DEFAULT_WORKING_HOURS (mon-fri) applies.
_WORKDAY = date(2026, 6, 10)


def _stub_availability(
    service,
    mocker,
    *,
    working_hours,
    break_times=None,
    buffer=0,
    appointments=None,
    blocks=None,
    slot_step=30,
    min_notice_hours=0,
):
    """Patches the small DB helpers so get_available_slots can run in isolation."""
    # Freeze "now" before slot window so tests stay deterministic in CI (any clock time).
    mocker.patch(
        "packages.scheduling.services.availability.now_local_naive",
        return_value=datetime.combine(_WORKDAY, time(7, 0)),
    )
    service._get_professional_schedule = lambda _pid: {
        "working_hours": working_hours,
        "break_times": break_times or [],
        "buffer": buffer,
    }
    service._get_org_config = lambda: {
        "slot_step": slot_step,
        "min_notice_hours": min_notice_hours,
        "timezone": "America/Sao_Paulo",
    }
    service._get_day_appointments = lambda _pid, _d: appointments or []
    service._get_day_blocks = lambda _pid, _d: blocks or []


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
async def test_create_appointment_rejects_ineligible_professional(scheduling_service, mocker):
    mocker.patch("packages.auth_core.tenant.get_current_org_id", return_value="org-1")
    mocker.patch(
        "packages.scheduling.eligibility.assert_professional_eligible",
        side_effect=BusinessLogicError("O profissional selecionado não está elegível para executar este serviço."),
    )

    appointment = AppointmentBase(
        patient_id=uuid4(),
        professional_id=uuid4(),
        service_id=uuid4(),
        scheduled_at=datetime.now() + timedelta(days=1),
        duration_minutes=30,
    )

    with pytest.raises(BusinessLogicError, match="elegível"):
        await scheduling_service.create_appointment(appointment)


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


@pytest.mark.asyncio
async def test_reschedule_appointment_updates_duration(scheduling_service, mock_scheduling_db, mocker):
    appointment_id = uuid4()
    professional_id = uuid4()
    scheduled_at = datetime(2026, 6, 10, 14, 0, tzinfo=timezone.utc)

    existing_row = {
        "id": str(appointment_id),
        "patient_id": str(uuid4()),
        "professional_id": str(professional_id),
        "service_id": str(uuid4()),
        "scheduled_at": scheduled_at.isoformat(),
        "duration_minutes": 30,
        "status": "confirmed",
    }

    fetch_table = MagicMock()
    fetch_table.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
        _mock_response(existing_row)
    )

    conflict_table = MagicMock()
    conflict_table.select.return_value.eq.return_value.gte.return_value.lte.return_value.neq.return_value.neq.return_value.execute.return_value = (
        _mock_response([])
    )

    update_table = MagicMock()
    update_table.update.return_value.eq.return_value.execute.return_value = _mock_response(
        [{"id": str(appointment_id), "duration_minutes": 60}]
    )

    mock_scheduling_db.client.table.side_effect = [fetch_table, conflict_table, update_table]

    refresh = mocker.patch(
        "packages.scheduling.reminder_service.ReminderService.refresh_reminders_for_appointment",
        return_value=[],
    )

    result = await scheduling_service.reschedule_appointment(
        appointment_id,
        duration_minutes=60,
        organization_id="org-1",
    )
    assert result["duration_minutes"] == 60
    refresh.assert_called_once()


@pytest.mark.asyncio
async def test_slots_respect_professional_working_hours(scheduling_service, mocker):
    _stub_availability(
        scheduling_service,
        mocker,
        working_hours={"wed": {"start": "09:00", "end": "11:00"}},
        slot_step=30,
    )
    slots = await scheduling_service.get_available_slots(uuid4(), _WORKDAY, 30)
    times = [s[11:16] for s in slots]
    assert times == ["09:00", "09:30", "10:00", "10:30"]


@pytest.mark.asyncio
async def test_slots_empty_on_day_off(scheduling_service, mocker):
    _stub_availability(
        scheduling_service,
        mocker,
        working_hours={"mon": {"start": "08:00", "end": "18:00"}},  # no wed key
    )
    slots = await scheduling_service.get_available_slots(uuid4(), _WORKDAY, 30)
    assert slots == []


@pytest.mark.asyncio
async def test_slots_exclude_break_times(scheduling_service, mocker):
    _stub_availability(
        scheduling_service,
        mocker,
        working_hours={"wed": {"start": "09:00", "end": "12:00"}},
        break_times=[{"start": "10:00", "end": "11:00"}],
        slot_step=30,
    )
    slots = await scheduling_service.get_available_slots(uuid4(), _WORKDAY, 30)
    times = [s[11:16] for s in slots]
    assert "10:00" not in times and "10:30" not in times
    assert "09:00" in times and "11:00" in times


@pytest.mark.asyncio
async def test_slots_apply_buffer_around_appointment(scheduling_service, mocker):
    _stub_availability(
        scheduling_service,
        mocker,
        working_hours={"wed": {"start": "09:00", "end": "12:00"}},
        buffer=15,
        appointments=[{"scheduled_at": "2026-06-10T10:00:00", "duration_minutes": 30, "status": "confirmed"}],
        slot_step=30,
    )
    slots = await scheduling_service.get_available_slots(uuid4(), _WORKDAY, 30)
    times = [s[11:16] for s in slots]
    # Appointment 10:00-10:30 + 15min buffer each side blocks 09:45-10:45.
    assert "09:30" not in times  # would end 10:00, overlaps buffer start 09:45
    assert "10:30" not in times
    assert "09:00" in times and "11:00" in times


@pytest.mark.asyncio
async def test_slots_exclude_schedule_blocks(scheduling_service, mocker):
    _stub_availability(
        scheduling_service,
        mocker,
        working_hours={"wed": {"start": "09:00", "end": "12:00"}},
        blocks=[{"professional_id": None, "starts_at": "2026-06-10T09:00:00", "ends_at": "2026-06-10T10:00:00"}],
        slot_step=30,
    )
    slots = await scheduling_service.get_available_slots(uuid4(), _WORKDAY, 30)
    times = [s[11:16] for s in slots]
    assert "09:00" not in times and "09:30" not in times
    assert "10:00" in times


class _RecordingQuery:
    """Minimal chainable query stub that records the filters applied to it."""

    def __init__(self, data):
        self._data = data
        self.eq_calls: list[tuple[str, Any]] = []

    def select(self, *_args, **_kwargs):
        return self

    def lte(self, *_args, **_kwargs):
        return self

    def gte(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self.eq_calls.append((column, value))
        return self

    def execute(self):
        return _mock_response(self._data)


def test_get_day_blocks_filters_by_organization(scheduling_service, mock_scheduling_db):
    from packages.auth_core.tenant import set_tenant_context

    recorder = _RecordingQuery([])
    mock_scheduling_db.client.table.return_value = recorder

    with set_tenant_context("org-123"):
        scheduling_service._get_day_blocks(uuid4(), _WORKDAY)

    assert ("organization_id", "org-123") in recorder.eq_calls


@pytest.mark.asyncio
async def test_list_blocks_filters_by_organization(scheduling_service, mock_scheduling_db):
    from packages.auth_core.tenant import set_tenant_context

    recorder = _RecordingQuery([])
    mock_scheduling_db.client.table.return_value = recorder

    with set_tenant_context("org-456"):
        await scheduling_service.list_blocks(_WORKDAY, _WORKDAY)

    assert ("organization_id", "org-456") in recorder.eq_calls
