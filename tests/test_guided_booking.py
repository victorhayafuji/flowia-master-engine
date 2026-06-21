"""Unit tests for the channel-agnostic guided booking flow (hybrid agent).

The client is resolved *before* the flow — by ``patient_id`` (dev chat test-page
selector) or by ``patient_phone`` (WhatsApp sender) — never asked in-chat.
"""
from __future__ import annotations

import asyncio

import pytest

from packages.scheduling import guided_booking as gb
from packages.scheduling.guided_session_store import clear_session

ORG = "00000000-0000-0000-0000-0000000000aa"
SVC_1 = "11111111-1111-1111-1111-111111111111"
PRO_1 = "33333333-3333-3333-3333-333333333333"
PATIENT = "44444444-4444-4444-4444-444444444444"
SLOT_ISO = "2027-01-04T09:00:00"

SERVICES = [{"id": SVC_1, "name": "Corte", "duration_minutes": 30, "price": 50.0}]
PROS = [{"id": PRO_1, "name": "Ana"}]


class FakeService:
    created: list = []

    async def get_available_slots(self, professional_id, target_date, service_duration):
        return [SLOT_ISO, "2027-01-04T09:30:00"]

    async def create_appointment(self, appointment):
        row = {
            "id": "appt-1",
            "scheduled_at": appointment.scheduled_at.isoformat(),
            "status": appointment.status.value,
            "patient_id": str(appointment.patient_id),
            "source": appointment.source.value,
        }
        FakeService.created.append(row)
        return row


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    FakeService.created = []
    monkeypatch.setattr(gb, "list_catalog_services", lambda org_id: SERVICES)
    monkeypatch.setattr(gb, "list_eligible_professionals", lambda org_id, service_id: PROS)
    monkeypatch.setattr(gb, "SchedulingService", FakeService)
    monkeypatch.setattr(gb, "upsert_patient_by_phone", lambda org_id, name, phone: PATIENT)
    monkeypatch.setattr(gb, "find_patient_by_phone", lambda org_id, phone: None)
    yield


def _first_real_option(step):
    """First non-navigation option of a step."""
    return next(o for o in step.options if o.id not in (gb.BACK_ID, gb.CANCEL_ID))


def _book_from_service(tid: str):
    """Drive service → professional → date → slot → confirm → returns the POST step."""
    step = asyncio.run(gb.advance(tid, SVC_1))
    assert step.step == "professional"
    step = asyncio.run(gb.advance(tid, PRO_1))
    assert step.step == "date"
    step = asyncio.run(gb.advance(tid, _first_real_option(step).id))
    assert step.step == "slot"
    assert _first_real_option(step).id == SLOT_ISO
    assert _first_real_option(step).title == "09:00"
    step = asyncio.run(gb.advance(tid, SLOT_ISO))
    assert step.step == "confirm"
    return asyncio.run(gb.advance(tid, gb.CONFIRM_ID))


def test_chat_existing_patient_id_shortcuts_to_service():
    tid = "t-chat-existing"
    clear_session(tid)
    step = asyncio.run(gb.start_session(tid, org_id=ORG, patient_id=PATIENT))
    assert step.step == "service"

    post = _book_from_service(tid)
    assert post.step == "post"  # success → post-booking step
    assert "confirmado" in post.text.lower()
    assert {o.id for o in post.options} == {gb.BOOK_AGAIN_ID, gb.FINISH_ID}
    assert FakeService.created[-1]["patient_id"] == PATIENT
    assert FakeService.created[-1]["source"] == "dashboard"


def test_chat_unregistered_onboards_name_and_phone(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        gb, "upsert_patient_by_phone",
        lambda org_id, name, phone: captured.update(name=name, phone=phone) or PATIENT,
    )
    tid = "t-chat-new"
    clear_session(tid)
    step = asyncio.run(gb.start_session(tid, org_id=ORG))
    assert step.step == "patient_capture"
    assert step.kind == "input"

    step = asyncio.run(gb.advance(tid, "Maria Silva 11999998888"))
    assert step.step == "service"
    assert captured["phone"] == "11999998888"
    assert "Maria" in captured["name"]
    assert _book_from_service(tid).step == "post"


def test_whatsapp_existing_patient_by_phone(monkeypatch):
    monkeypatch.setattr(gb, "find_patient_by_phone", lambda org_id, phone: {"id": PATIENT, "name": "Maria"})
    tid = "t-wa-existing"
    clear_session(tid)
    step = asyncio.run(
        gb.start_session(tid, org_id=ORG, patient_phone="5511999998888", channel="whatsapp")
    )
    assert step.step == "service"
    _book_from_service(tid)
    assert FakeService.created[-1]["source"] == "whatsapp"


def test_whatsapp_unregistered_asks_name_only(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        gb, "upsert_patient_by_phone",
        lambda org_id, name, phone: captured.update(name=name, phone=phone) or PATIENT,
    )
    tid = "t-wa-new"
    clear_session(tid)
    step = asyncio.run(
        gb.start_session(tid, org_id=ORG, patient_phone="5511999998888", channel="whatsapp")
    )
    assert step.step == "patient_capture"
    step = asyncio.run(gb.advance(tid, "Maria Silva"))
    assert step.step == "service"
    assert captured["phone"] == "5511999998888"


def test_cancel_option_aborts():
    tid = "t-cancel"
    clear_session(tid)
    asyncio.run(gb.start_session(tid, org_id=ORG, patient_id=PATIENT))  # service step
    outcome = asyncio.run(gb.advance(tid, gb.CANCEL_ID))
    assert isinstance(outcome, gb.BookingOutcome)
    assert outcome.success is False
    assert "cancel" in outcome.message.lower()


def test_back_navigation_returns_to_previous_step():
    tid = "t-back"
    clear_session(tid)
    asyncio.run(gb.start_session(tid, org_id=ORG, patient_id=PATIENT))
    step = asyncio.run(gb.advance(tid, SVC_1))  # → professional
    assert step.step == "professional"
    step = asyncio.run(gb.advance(tid, gb.BACK_ID))  # ↩ back to service
    assert step.step == "service"


def test_post_booking_book_again_keeps_patient():
    tid = "t-again"
    clear_session(tid)
    asyncio.run(gb.start_session(tid, org_id=ORG, patient_id=PATIENT))
    post = _book_from_service(tid)
    assert post.step == "post"
    step = asyncio.run(gb.advance(tid, gb.BOOK_AGAIN_ID))
    assert step.step == "service"  # new booking, patient kept
    # And finishing ends the session.
    asyncio.run(gb.start_session(tid, org_id=ORG, patient_id=PATIENT))
    _book_from_service(tid)
    outcome = asyncio.run(gb.advance(tid, gb.FINISH_ID))
    assert isinstance(outcome, gb.BookingOutcome)
    assert outcome.success is True


def test_menu_and_faq_builders():
    menu = gb.menu_step()
    assert menu.step == "menu"
    assert {o.id for o in menu.options} == {gb.MENU_BOOK_ID, gb.MENU_FAQ_ID}

    faq = gb.faq_topics_step()
    assert faq.step == "faq"
    ids = {o.id for o in faq.options}
    assert set(gb.FAQ_TOPIC_QUESTIONS.keys()).issubset(ids)
    assert "menu" in ids  # ↩ Voltar ao menu
    # Canonical questions must not contain scheduling keywords (would force booking).
    assert "horário" not in gb.FAQ_TOPIC_QUESTIONS["faq_horario"].lower()


def test_post_faq_step_returns_to_deterministic_flow():
    step = gb.post_faq_step()
    assert step.step == "faq_followup"
    assert step.kind == "buttons"
    assert {o.id for o in step.options} == {gb.MENU_BOOK_ID, gb.MENU_FAQ_ID}


def test_no_slots_returns_to_date(monkeypatch):
    class NoSlots(FakeService):
        async def get_available_slots(self, *a, **k):
            return []

    monkeypatch.setattr(gb, "SchedulingService", NoSlots)
    tid = "t-noslot"
    clear_session(tid)
    asyncio.run(gb.start_session(tid, org_id=ORG, patient_id=PATIENT))
    asyncio.run(gb.advance(tid, SVC_1))
    date_step = asyncio.run(gb.advance(tid, PRO_1))
    step = asyncio.run(gb.advance(tid, _first_real_option(date_step).id))
    assert step.step == "date"


def test_expired_session_returns_outcome():
    outcome = asyncio.run(gb.advance("missing-thread", "x"))
    assert isinstance(outcome, gb.BookingOutcome)
    assert outcome.success is False


def test_recovery_booking_data_reply_without_session_lands_on_service():
    """A name+phone reply with no active session (e.g. dev hot-reload dropped it)
    must restart the guided flow and consume the reply — not leak to the LLM."""
    from packages.engine.service import _maybe_guided_turn

    tid = "t-recover"
    clear_session(tid)
    result = asyncio.run(_maybe_guided_turn(tid, ORG, "Victor 11999998888", patient_id=None))
    assert result is not None  # did NOT fall through to the free-text engine
    assert result["step"]["step"] == "service"
    assert result["triage_source"] == "guided"


def test_no_recovery_for_plain_question_without_session():
    """A non-booking message with no session still defers to the LLM engine (None)."""
    from packages.engine.service import _maybe_guided_turn

    tid = "t-no-recover"
    clear_session(tid)
    result = asyncio.run(_maybe_guided_turn(tid, ORG, "quais servicos voces tem?", patient_id=None))
    assert result is None


def _drive_to_slot(tid: str):
    """Drive service → professional → date so the session sits at the slot step."""
    asyncio.run(gb.start_session(tid, org_id=ORG, patient_id=PATIENT))
    asyncio.run(gb.advance(tid, SVC_1))
    date_step = asyncio.run(gb.advance(tid, PRO_1))
    step = asyncio.run(gb.advance(tid, _first_real_option(date_step).id))
    assert step.step == "slot"


def test_slot_step_rejects_non_iso_selection():
    """A typed reply that isn't an offered ISO slot must not become a garbage slot."""
    tid = "t-slot-bad"
    clear_session(tid)
    _drive_to_slot(tid)
    step = asyncio.run(gb.advance(tid, "amanhã de manhã"))  # not an ISO datetime
    assert step.step == "slot"  # re-rendered, NOT confirm
    step = asyncio.run(gb.advance(tid, SLOT_ISO))  # valid slot proceeds
    assert step.step == "confirm"


def test_date_step_uses_org_timezone(monkeypatch):
    """'Hoje' must be the org's calendar day, not the server's (UTC drift)."""
    from datetime import datetime as _dt

    from packages.scheduling.guided_session_store import GuidedSession

    monkeypatch.setattr(gb, "now_local_naive", lambda tz=None: _dt(2026, 3, 10, 8, 0))
    session = GuidedSession(org_id=ORG, tzname="America/Sao_Paulo")
    step = gb._date_step(gb._today_for(session))
    assert step.options[0].id == "2026-03-10"  # first option = org "today"
    assert step.options[0].title.startswith("Hoje")


def test_create_appointment_with_corrupt_slot_returns_friendly_outcome():
    """A corrupted slot must surface a friendly outcome, never raise (silent WhatsApp drop)."""
    from packages.scheduling.guided_session_store import GuidedSession

    session = GuidedSession(org_id=ORG, patient_id=PATIENT)
    session.service_id = SVC_1
    session.professional_id = PRO_1
    session.slot = "not-a-datetime"
    outcome = asyncio.run(gb._create_appointment(session))
    assert isinstance(outcome, gb.BookingOutcome)
    assert outcome.success is False
