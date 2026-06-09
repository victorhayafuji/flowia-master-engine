"""Tests for booking state sync."""
from datetime import date

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from packages.scheduling.booking_flow_memory import BookingFlowStep
from packages.scheduling.booking_state_sync import (
    clear_booking_state,
    derive_booking_step,
    derive_missing_fields,
    derive_pending_clarification,
    has_open_date_clarification,
    snapshot_to_state_patch,
    sync_booking_state,
)

ORG = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(autouse=True)
def _mock_catalog(mocker):
    mocker.patch(
        "packages.scheduling.booking_executor.list_catalog_services",
        return_value=[
            {"id": "1", "name": "Corte Masculino", "duration_minutes": 45, "price": 80},
        ],
    )


def test_clear_booking_state_zeros_all_slots():
    cleared = clear_booking_state()
    assert all(v is None for v in cleared.values())
    assert set(cleared.keys()) == {
        "booking_date",
        "booking_service",
        "booking_time",
        "booking_patient_name",
        "booking_patient_phone",
        "booking_step",
        "booking_pending_clarification",
        "booking_missing_fields",
    }


def test_snapshot_to_state_patch_exports_checkpoint_fields():
    snap = sync_booking_state(
        [HumanMessage(content="Quero corte masculino amanhã ou sexta")],
        ORG,
    )
    patch = snapshot_to_state_patch(snap)
    assert patch["booking_pending_clarification"] == "date"
    assert "date" in (patch["booking_missing_fields"] or [])


def test_sync_pending_date_clarification_on_ambiguous_thread(mocker):
    class _FixedToday(date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 9)

    mocker.patch("packages.scheduling.booking_executor.date", _FixedToday)
    snap = sync_booking_state(
        [HumanMessage(content="Gostaria de agendar um corte masculino para amanhã ou sexta")],
        ORG,
    )
    assert snap.pending_clarification == "date"
    assert has_open_date_clarification(snap)
    assert snap.missing_fields == ("date",)
    assert snap.booking_service == "Corte Masculino"
    assert snap.booking_date is None


def test_sync_clears_pending_after_explicit_date_pick(mocker):
    class _FixedToday(date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 9)

    mocker.patch("packages.scheduling.booking_executor.date", _FixedToday)
    messages = [
        HumanMessage(content="Gostaria de agendar um corte masculino para amanhã ou sexta"),
        AIMessage(content="Qual dia você prefere: amanhã (10/06) ou sexta (12/06)?"),
        HumanMessage(content="Pode ser amanhã"),
        HumanMessage(content="Corte Masculino"),
    ]
    snap = sync_booking_state(
        messages,
        ORG,
        booking_date="2026-06-10",
        booking_service="Corte Masculino",
    )
    assert snap.booking_date == "2026-06-10"
    assert snap.pending_clarification is None
    assert has_open_date_clarification(snap) is False
    assert "date" not in snap.missing_fields
    assert "time" in snap.missing_fields


def test_derive_missing_fields_awaiting_patient_data():
    missing = derive_missing_fields(
        booking_date="2026-06-10",
        booking_service="Corte Masculino",
        booking_time="09:00",
        booking_patient_name=None,
        booking_patient_phone=None,
        step=BookingFlowStep.AWAITING_PATIENT,
    )
    assert missing == ("patient_name", "patient_phone")


def test_derive_pending_only_when_clarification_open():
    assert derive_pending_clarification(clarification="Qual dia?", booking_date=None) == "date"
    assert derive_pending_clarification(clarification="Qual dia?", booking_date="2026-06-10") is None
    assert derive_pending_clarification(clarification=None, booking_date=None) is None


def test_sync_preserves_date_service_when_last_message_is_time_only(mocker):
    class _FixedToday(date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 10)

    mocker.patch("packages.scheduling.booking_executor.date", _FixedToday)
    messages = [
        HumanMessage(content="Quero corte masculino amanhã"),
        HumanMessage(content="08:00"),
    ]
    snap = sync_booking_state(
        messages,
        ORG,
        booking_date="2026-06-11",
        booking_service="Corte Masculino",
    )
    assert snap.booking_date == "2026-06-11"
    assert snap.booking_service == "Corte Masculino"
    assert snap.booking_time == "08:00"
    assert snap.booking_step == BookingFlowStep.AWAITING_PATIENT.value


def test_sync_clears_time_when_date_changes(mocker):
    class _FixedToday(date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 10)

    mocker.patch("packages.scheduling.booking_executor.date", _FixedToday)
    messages = [HumanMessage(content="Prefiro depois de amanhã")]
    snap = sync_booking_state(
        messages,
        ORG,
        booking_date="2026-06-11",
        booking_service="Corte Masculino",
        booking_time="08:00",
    )
    assert snap.booking_date == "2026-06-12"
    assert snap.booking_time is None


def test_sync_clears_date_and_time_on_reset_phrase():
    messages = [HumanMessage(content="Quero outro dia")]
    snap = sync_booking_state(
        messages,
        ORG,
        booking_date="2026-06-11",
        booking_service="Corte Masculino",
        booking_time="08:00",
    )
    assert snap.booking_date is None
    assert snap.booking_time is None
    assert snap.booking_service == "Corte Masculino"
    assert snap.pending_clarification is None
    assert snap.missing_fields == ("date",)


def test_derive_awaiting_patient_with_time_slot():
    step = derive_booking_step(
        [],
        booking_date="2026-06-11",
        booking_service="Corte Masculino",
        booking_time="09:00",
        booking_patient_name=None,
        booking_patient_phone=None,
    )
    assert step == BookingFlowStep.AWAITING_PATIENT


def test_derive_awaiting_time_without_time():
    step = derive_booking_step(
        [],
        booking_date="2026-06-11",
        booking_service="Corte Masculino",
        booking_time=None,
        booking_patient_name=None,
        booking_patient_phone=None,
    )
    assert step == BookingFlowStep.AWAITING_TIME
