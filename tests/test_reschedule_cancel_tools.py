"""Tools de reagendar/cancelar — agem só no agendamento do próprio cliente."""
import pytest

import packages.scheduling.tools as tools
from packages.auth_core.exceptions import DoubleBookingError
from packages.models.enums import AppointmentStatus
from packages.scheduling.guardrails import reset_rate_limits_for_tests

FUTURE_ISO = "2030-01-10T10:00:00+00:00"
APPT_UUID = "11111111-1111-1111-1111-111111111111"


class _FakeSched:
    def __init__(self):
        self.appts: list[dict] = []
        self.reschedule_exc: Exception | None = None
        self.cancelled: tuple | None = None
        self.rescheduled: tuple | None = None

    def _get_org_config(self):
        return {"timezone": "America/Sao_Paulo"}

    async def get_upcoming_appointments_for_patient(self, org_id, patient_id):
        return self.appts

    async def reschedule_appointment(self, appointment_id, new_scheduled_at, organization_id=None):
        if self.reschedule_exc:
            raise self.reschedule_exc
        self.rescheduled = (str(appointment_id), new_scheduled_at)
        return {"scheduled_at": new_scheduled_at.isoformat()}

    async def update_appointment_status(self, appointment_id, new_status, organization_id=None):
        self.cancelled = (str(appointment_id), new_status)
        return {}


def _appt(appt_id=APPT_UUID, service="Corte", pro="Ana"):
    return {
        "id": appt_id,
        "scheduled_at": FUTURE_ISO,
        "duration_minutes": 30,
        "status": "confirmed",
        "service": {"name": service},
        "professional": {"name": pro},
    }


@pytest.fixture
def fake(monkeypatch):
    reset_rate_limits_for_tests()
    inst = _FakeSched()
    monkeypatch.setattr(tools, "SchedulingService", lambda: inst)
    return inst


def _cfg(**extra):
    cfg = {"org_id": "org-1", "channel": "chat_test", "patient_id": "pat-1", "thread_id": "t1"}
    cfg.update(extra)
    return {"configurable": cfg}


@pytest.mark.asyncio
async def test_list_my_appointments_lists_caller(fake):
    fake.appts = [_appt()]
    res = await tools.list_my_appointments.ainvoke({}, config=_cfg())
    assert "Corte" in res and "Ana" in res


@pytest.mark.asyncio
async def test_reschedule_success(fake):
    fake.appts = [_appt()]
    res = await tools.reschedule_time.ainvoke({"new_datetime": "2030-02-01T14:00:00"}, config=_cfg())
    assert res.upper().startswith("SUCESSO")
    assert fake.rescheduled and fake.rescheduled[0] == APPT_UUID


@pytest.mark.asyncio
async def test_reschedule_conflict_friendly(fake):
    fake.appts = [_appt()]
    fake.reschedule_exc = DoubleBookingError("ocupado")
    res = await tools.reschedule_time.ainvoke({"new_datetime": "2030-02-01T14:00:00"}, config=_cfg())
    assert "ocupado" in res.lower() and "check_availability" in res


@pytest.mark.asyncio
async def test_cancel_requires_confirmation(fake):
    fake.appts = [_appt()]
    res = await tools.cancel_appointment.ainvoke({}, config=_cfg())
    assert "confirma" in res.lower()
    assert fake.cancelled is None  # nada cancelado sem confirmação


@pytest.mark.asyncio
async def test_cancel_with_confirm(fake):
    fake.appts = [_appt()]
    res = await tools.cancel_appointment.ainvoke({"confirm": True}, config=_cfg())
    assert fake.cancelled == (APPT_UUID, AppointmentStatus.CANCELLED)
    assert "cancelei" in res.lower()


@pytest.mark.asyncio
async def test_no_appointments(fake):
    fake.appts = []
    res = await tools.cancel_appointment.ainvoke({"confirm": True}, config=_cfg())
    assert "não encontrei" in res.lower()
    assert fake.cancelled is None


@pytest.mark.asyncio
async def test_multiple_appointments_ask_which(fake):
    fake.appts = [_appt("a1", "Corte"), _appt("a2", "Coloração")]
    res = await tools.reschedule_time.ainvoke({"new_datetime": "2030-02-01T14:00:00"}, config=_cfg())
    assert "mais de um" in res.lower()
    assert fake.rescheduled is None


@pytest.mark.asyncio
async def test_caller_bound_to_sender_phone_not_llm_input(fake, monkeypatch):
    """No WhatsApp, o paciente vem do telefone do sender — nunca de input do LLM."""
    captured = {}

    def fake_find(org_id, phone):
        captured["phone"] = phone
        return {"id": "pat-from-phone", "name": "Cliente"}

    monkeypatch.setattr(tools, "find_patient_by_phone", fake_find)
    fake.appts = [_appt()]
    cfg = {"configurable": {"org_id": "org-1", "channel": "whatsapp", "sender_phone": "5511999999999"}}
    await tools.list_my_appointments.ainvoke({}, config=cfg)
    assert captured["phone"] == "5511999999999"
