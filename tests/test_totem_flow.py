"""Totem (kiosk) channel — device auth + outer-flow state machine.

The DB and the shared booking/consent helpers are mocked at the seams so these
tests assert the totem orchestration only (identify → consent → menu →
booking/check-in), not Supabase.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.compliance.consent import ConsentAction
from packages.integrations.totem import service as totem
from packages.integrations.totem.session_store import reset_for_tests
from packages.scheduling import guided_booking as gb

ORG = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(autouse=True)
def _clean_sessions():
    reset_for_tests()
    yield
    reset_for_tests()


class _Fluent:
    """Chainable query stub: every builder method returns self; execute() yields data."""

    def __init__(self, data):
        self._data = list(data)

    def __getattr__(self, _name):
        return lambda *a, **k: self

    def execute(self):
        res = MagicMock()
        res.data = self._data
        return res


# --- Device-token resolution (fail-closed) ---------------------------------

def test_resolver_returns_none_when_no_device(mocker):
    from packages.integrations.totem import tenant_resolver

    mock_db = mocker.patch.object(tenant_resolver, "db")
    mock_db.client.table.return_value = _Fluent([])  # no matching active device

    assert tenant_resolver.resolve_org_id_from_device_token("kdev_whatever") is None


def test_resolver_returns_org_on_match(mocker):
    from packages.integrations.totem import tenant_resolver

    mock_db = mocker.patch.object(tenant_resolver, "db")
    mock_db.client.table.return_value = _Fluent([{"id": "dev1", "organization_id": ORG}])

    assert tenant_resolver.resolve_org_id_from_device_token("kdev_good") == ORG


@pytest.mark.asyncio
async def test_dependency_403_when_unresolved(mocker):
    from fastapi import HTTPException

    from packages.integrations.totem import dependencies

    mocker.patch.object(dependencies, "resolve_org_id_from_device_token", return_value=None)
    with pytest.raises(HTTPException) as exc:
        await dependencies.resolve_kiosk_tenant(x_device_token=None)
    assert exc.value.status_code == 403


# --- Outer flow -------------------------------------------------------------

def _start():
    out = totem.start_totem_session(ORG)
    assert out["step"]["step"] == "identify"
    return out["session_id"]


@pytest.mark.asyncio
async def test_identify_to_consent(mocker):
    mocker.patch.object(totem, "upsert_patient_by_phone", return_value="pat1")
    mocker.patch.object(
        totem, "evaluate_consent_gate",
        return_value=(ConsentAction.SEND_NOTICE, "Aviso LGPD…", False),
    )
    sid = _start()
    out = await totem.advance_totem(sid, "Maria 11999998888")
    assert out["step"]["step"] == "consent"
    assert {o["id"] for o in out["step"]["options"]} == {gb.CONSENT_ACCEPT_ID, gb.CONSENT_DECLINE_ID}


@pytest.mark.asyncio
async def test_identify_proceed_straight_to_menu(mocker):
    mocker.patch.object(totem, "upsert_patient_by_phone", return_value="pat1")
    mocker.patch.object(
        totem, "evaluate_consent_gate", return_value=(ConsentAction.PROCEED, None, True)
    )
    sid = _start()
    out = await totem.advance_totem(sid, "Maria 11999998888")
    assert out["step"]["step"] == "menu"
    ids = {o["id"] for o in out["step"]["options"]}
    assert totem.MENU_CHECKIN_ID in ids and gb.MENU_BOOK_ID in ids and gb.MENU_FAQ_ID in ids


@pytest.mark.asyncio
async def test_identify_rejects_bad_input(mocker):
    sid = _start()
    out = await totem.advance_totem(sid, "oi")  # no phone
    assert out["step"]["step"] == "identify"  # re-ask, stays in identify


@pytest.mark.asyncio
async def test_consent_accept_then_menu(mocker):
    mocker.patch.object(totem, "upsert_patient_by_phone", return_value="pat1")
    mocker.patch.object(
        totem, "evaluate_consent_gate",
        return_value=(ConsentAction.SEND_NOTICE, "Aviso", False),
    )
    rec = mocker.patch.object(totem, "record_consent")
    sid = _start()
    await totem.advance_totem(sid, "Maria 11999998888")
    out = await totem.advance_totem(sid, gb.CONSENT_ACCEPT_ID)
    assert out["step"]["step"] == "menu"
    rec.assert_called_once()


@pytest.mark.asyncio
async def test_consent_decline_ends(mocker):
    mocker.patch.object(totem, "upsert_patient_by_phone", return_value="pat1")
    mocker.patch.object(
        totem, "evaluate_consent_gate",
        return_value=(ConsentAction.SEND_NOTICE, "Aviso", False),
    )
    dec = mocker.patch.object(totem, "record_decline")
    sid = _start()
    await totem.advance_totem(sid, "Maria 11999998888")
    out = await totem.advance_totem(sid, gb.CONSENT_DECLINE_ID)
    assert out["done"] is True
    dec.assert_called_once()


@pytest.mark.asyncio
async def test_menu_book_enters_booking(mocker):
    mocker.patch.object(totem, "upsert_patient_by_phone", return_value="pat1")
    mocker.patch.object(
        totem, "evaluate_consent_gate", return_value=(ConsentAction.PROCEED, None, True)
    )
    first_step = gb.StructuredStep("service", "Qual serviço?", "list", [])
    mocker.patch.object(gb, "start_session", new=AsyncMock(return_value=first_step))
    sid = _start()
    await totem.advance_totem(sid, "Maria 11999998888")
    out = await totem.advance_totem(sid, gb.MENU_BOOK_ID)
    assert out["step"]["step"] == "service"
    assert totem.get_session(sid).phase == totem.PHASE_BOOKING


@pytest.mark.asyncio
async def test_checkin_success(mocker):
    mocker.patch.object(totem, "upsert_patient_by_phone", return_value="pat1")
    mocker.patch.object(
        totem, "evaluate_consent_gate", return_value=(ConsentAction.PROCEED, None, True)
    )
    mocker.patch.object(totem, "find_patient_by_phone", return_value={"id": "pat1", "name": "Maria"})
    mocker.patch.object(totem, "_org_timezone", return_value="America/Sao_Paulo")
    mock_db = mocker.patch.object(totem, "db")
    appt_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    mock_db.client.table.return_value = _Fluent(
        [{"id": appt_id, "scheduled_at": "2026-06-29T13:00:00+00:00", "status": "confirmed",
          "service": {"name": "Corte"}}]
    )
    sched = mocker.patch("packages.scheduling.service.SchedulingService")
    sched.return_value.update_appointment_status = AsyncMock(return_value={"id": appt_id})

    sid = _start()
    await totem.advance_totem(sid, "Maria 11999998888")
    out = await totem.advance_totem(sid, totem.MENU_CHECKIN_ID)
    assert "check-in confirmado" in out["response"].lower()
    sched.return_value.update_appointment_status.assert_awaited_once()


@pytest.mark.asyncio
async def test_checkin_no_appointment(mocker):
    mocker.patch.object(totem, "upsert_patient_by_phone", return_value="pat1")
    mocker.patch.object(
        totem, "evaluate_consent_gate", return_value=(ConsentAction.PROCEED, None, True)
    )
    mocker.patch.object(totem, "find_patient_by_phone", return_value={"id": "pat1", "name": "Maria"})
    mocker.patch.object(totem, "_org_timezone", return_value="America/Sao_Paulo")
    mock_db = mocker.patch.object(totem, "db")
    mock_db.client.table.return_value = _Fluent([])  # no appointments today

    sid = _start()
    await totem.advance_totem(sid, "Maria 11999998888")
    out = await totem.advance_totem(sid, totem.MENU_CHECKIN_ID)
    assert "não encontrei agendamento" in out["response"].lower()
