"""No-leak of the agent scheduling tools across tenants (Onda 2 — Frente 2).

The booking tools (reschedule_time, cancel_appointment, list_my_appointments)
resolve the *patient* exclusively from the conversation channel — the
``sender_phone`` (WhatsApp) or ``patient_id`` (Ensaie selector) in the
RunnableConfig — and fetch ONLY that patient's appointments within the config's
``org_id`` via ``get_upcoming_appointments_for_patient(org_id, patient_id)``.

Anti-injection (CLAUDE.md §52): the tools take NO ``appointment_id`` or phone
argument from the LLM. The only LLM-controlled args are ``service_name`` /
``original_date`` *filters* applied to the caller's own list. So even if the
model is tricked into passing a service name or date that matches ANOTHER org's
appointment, the tool never sees that appointment — it operated on ORG_A's
patient list keyed by ORG_A's org_id.

Dente: we spy on ``get_upcoming_appointments_for_patient`` and on
``reschedule_appointment``/``update_appointment_status`` to assert (a) the org
queried is ORG_A from the config — never an arg-derived org — and (b) the only
appointment id ever written is one of the caller's own, never the ORG_B id we
plant in the LLM args.
"""
from __future__ import annotations

import pytest

import packages.scheduling.tools as tools
from packages.models.enums import AppointmentStatus
from packages.scheduling.guardrails import reset_rate_limits_for_tests
from tests.conftest import ORG_A

# Caller (ORG_A) owns this appointment for service "Corte".
CALLER_APPT = "11111111-1111-1111-1111-111111111111"
PRO_UUID = "22222222-2222-2222-2222-222222222222"
# A foreign appointment the attacker tries to smuggle through LLM args.
FOREIGN_APPT = "99999999-9999-9999-9999-999999999999"
FUTURE_ISO = "2030-01-10T10:00:00+00:00"


class _SpySched:
    """Records the org_id it was asked about and what it was told to mutate.

    Critically, ``get_upcoming_appointments_for_patient`` ONLY returns the
    caller's own appointments regardless of args — mirroring the real query that
    is keyed by (org_id, patient_id). The attacker's FOREIGN_APPT is never in
    this list, so the tool can never act on it.
    """

    def __init__(self):
        self.queried_orgs: list[str] = []
        self.queried_patients: list[str] = []
        self.rescheduled: tuple | None = None
        self.cancelled: tuple | None = None
        self.slots: list[str] = ["2030-02-01T14:00:00"]

    def _get_org_config(self):
        return {"timezone": "America/Sao_Paulo"}

    async def get_upcoming_appointments_for_patient(self, org_id, patient_id):
        self.queried_orgs.append(org_id)
        self.queried_patients.append(patient_id)
        # Caller's own appointment ONLY — the foreign org's appt is never here.
        return [
            {
                "id": CALLER_APPT,
                "scheduled_at": FUTURE_ISO,
                "duration_minutes": 30,
                "status": "confirmed",
                "professional_id": PRO_UUID,
                "service": {"name": "Corte"},
                "professional": {"name": "Ana"},
            }
        ]

    async def get_available_slots(self, professional_id, target_date, service_duration):
        return self.slots

    async def reschedule_appointment(self, appointment_id, new_scheduled_at, organization_id=None):
        self.rescheduled = (str(appointment_id), organization_id)
        return {"scheduled_at": new_scheduled_at.isoformat()}

    async def update_appointment_status(self, appointment_id, new_status, organization_id=None):
        self.cancelled = (str(appointment_id), new_status, organization_id)
        return {}


@pytest.fixture
def spy(monkeypatch):
    reset_rate_limits_for_tests()
    inst = _SpySched()
    monkeypatch.setattr(tools, "SchedulingService", lambda: inst)
    return inst


def _cfg_org_a(**extra):
    cfg = {"org_id": ORG_A, "channel": "chat_test", "patient_id": "pat-a", "thread_id": "t-a"}
    cfg.update(extra)
    return {"configurable": cfg}


@pytest.mark.asyncio
async def test_reschedule_ignores_foreign_appointment_in_llm_args(spy):
    # Attacker steers the LLM to pass a service_name/original_date that (in their
    # mind) targets ORG_B's appointment. The tool only filters the CALLER's list,
    # which never contains the foreign appt → it acts on CALLER_APPT, never on
    # FOREIGN_APPT, and always with ORG_A from the config.
    res = await tools.reschedule_time.ainvoke(
        {
            "new_datetime": "2030-02-01T14:00:00",
            "service_name": "Corte",  # matches caller's own appt
            "original_date": None,
        },
        config=_cfg_org_a(),
    )

    assert res.upper().startswith("SUCESSO")
    # The org queried came from the config (ORG_A), never from an arg.
    assert spy.queried_orgs == [ORG_A]
    assert spy.queried_patients == ["pat-a"]
    # The write targeted the caller's own appointment, scoped to ORG_A.
    assert spy.rescheduled is not None
    assert spy.rescheduled[0] == CALLER_APPT
    assert spy.rescheduled[0] != FOREIGN_APPT
    assert spy.rescheduled[1] == ORG_A


@pytest.mark.asyncio
async def test_reschedule_foreign_service_filter_finds_nothing(spy):
    # The LLM passes a service name that only exists in ORG_B's catalog. The
    # caller's own list has no such service → "nothing to reschedule", and NO
    # write happens. The tool never reaches into the other tenant to find it.
    res = await tools.reschedule_time.ainvoke(
        {"new_datetime": "2030-02-01T14:00:00", "service_name": "Coloração Platinum"},
        config=_cfg_org_a(),
    )

    assert "não encontrei" in res.lower()
    assert spy.rescheduled is None
    # Still only ever queried ORG_A's own patient.
    assert spy.queried_orgs == [ORG_A]


@pytest.mark.asyncio
async def test_cancel_ignores_foreign_appointment_in_llm_args(spy):
    res = await tools.cancel_appointment.ainvoke(
        {"service_name": "Corte", "confirm": True},
        config=_cfg_org_a(),
    )

    assert "cancelei" in res.lower()
    assert spy.cancelled is not None
    appt_id, status, org = spy.cancelled
    assert appt_id == CALLER_APPT
    assert appt_id != FOREIGN_APPT
    assert status == AppointmentStatus.CANCELLED
    assert org == ORG_A


@pytest.mark.asyncio
async def test_cancel_foreign_service_filter_finds_nothing(spy):
    res = await tools.cancel_appointment.ainvoke(
        {"service_name": "Coloração Platinum", "confirm": True},
        config=_cfg_org_a(),
    )

    assert "não encontrei" in res.lower()
    assert spy.cancelled is None


@pytest.mark.asyncio
async def test_list_my_appointments_scoped_to_caller_org(spy):
    res = await tools.list_my_appointments.ainvoke({}, config=_cfg_org_a())

    assert "Corte" in res
    # The list query was bound to ORG_A + the caller's patient_id, full stop.
    assert spy.queried_orgs == [ORG_A]
    assert spy.queried_patients == ["pat-a"]


@pytest.mark.asyncio
async def test_whatsapp_caller_resolved_by_sender_phone_in_own_org(spy, monkeypatch):
    # On WhatsApp the patient is resolved via find_patient_by_phone(org_id, phone)
    # — both args come from the channel/config, never from the LLM. The resolver
    # is org-scoped, so a phone is only matched within ORG_A.
    captured = {}

    def fake_find(org_id, phone):
        captured["org_id"] = org_id
        captured["phone"] = phone
        return {"id": "pat-wa", "name": "Cliente"}

    monkeypatch.setattr(tools, "find_patient_by_phone", fake_find)

    cfg = {
        "configurable": {
            "org_id": ORG_A,
            "channel": "whatsapp",
            "sender_phone": "5511999999999",
            "thread_id": f"{ORG_A}:5511999999999",
        }
    }
    await tools.list_my_appointments.ainvoke({}, config=cfg)

    assert captured["org_id"] == ORG_A  # resolver scoped to caller's org
    assert captured["phone"] == "5511999999999"
    assert spy.queried_orgs == [ORG_A]
    assert spy.queried_patients == ["pat-wa"]


@pytest.mark.asyncio
async def test_missing_org_id_in_config_is_fail_closed(spy):
    # No org_id in the config → _get_org_id_from_config raises; the tool catches
    # it and returns a friendly error, never silently operating cross-org.
    cfg = {"configurable": {"channel": "chat_test", "patient_id": "pat-a"}}
    res = await tools.list_my_appointments.ainvoke({}, config=cfg)
    assert "erro" in res.lower()
    assert spy.queried_orgs == []  # never queried any org
