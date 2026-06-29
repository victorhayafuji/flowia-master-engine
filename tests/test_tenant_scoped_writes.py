"""Wave 1 — tenant-scoped writes harden.

Two halves:
  1. The appointment write paths scope the UPDATE by organization_id (not just
     the SELECT), so isolation holds by construction. super_admin (ALL) still
     writes cross-tenant.
  2. The CI guard `scripts/check_tenant_scoped_writes.py` has teeth — a mutation
     (a business-table write with no org filter) is caught; a scoped one passes.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from packages.models.enums import AppointmentStatus
from packages.scheduling.service import SchedulingService

ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Helpers (mirror tests/test_scheduling.py mock style)
# --------------------------------------------------------------------------- #
def _mock_response(data):
    class MockResponse:
        def __init__(self, payload):
            self.data = payload

    return MockResponse(data)


class _RecordingWrite:
    """Chainable stub for an UPDATE chain that records every .eq filter and the
    payload, so a test can assert the write was scoped by organization_id."""

    def __init__(self, returned):
        self._returned = returned
        self.payload = None
        self.eq_calls: list[tuple[str, object]] = []

    def update(self, payload):
        self.payload = payload
        return self

    def delete(self):
        return self

    def select(self, *_a, **_k):
        return self

    def eq(self, column, value):
        self.eq_calls.append((column, value))
        return self

    def maybe_single(self):
        return self

    def execute(self):
        return _mock_response(self._returned)


def _scoped_fetch(row):
    """SELECT stub whose .eq returns itself (absorbs any number of filters)."""
    table = MagicMock()
    chain = table.select.return_value
    chain.eq.return_value = chain
    chain.maybe_single.return_value.execute.return_value = _mock_response(row)
    return table


@pytest.fixture
def mock_scheduling_db(mocker):
    return mocker.patch("packages.scheduling.service.db")


@pytest.fixture
def scheduling_service(mock_scheduling_db):
    return SchedulingService()


# --------------------------------------------------------------------------- #
# 1. Scoped-by-construction: the UPDATE carries organization_id
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_update_status_write_is_org_scoped(scheduling_service, mock_scheduling_db, mocker):
    """update_appointment_status with a concrete org → the UPDATE chain filters
    by organization_id (not just the SELECT)."""
    appt_id = uuid4()
    fetch = _scoped_fetch(
        {"id": str(appt_id), "status": "confirmed", "patient_id": None,
         "organization_id": "org-1"}
    )
    write = _RecordingWrite([{"id": str(appt_id), "status": "completed"}])
    mock_scheduling_db.client.table.side_effect = [fetch, write]

    await scheduling_service.update_appointment_status(
        appt_id, AppointmentStatus.COMPLETED, organization_id="org-1"
    )
    assert ("organization_id", "org-1") in write.eq_calls
    assert ("id", str(appt_id)) in write.eq_calls


@pytest.mark.asyncio
async def test_reschedule_write_is_org_scoped(scheduling_service, mock_scheduling_db, mocker):
    """reschedule_appointment with a concrete org → the UPDATE chain filters by
    organization_id."""
    mocker.patch(
        "packages.scheduling.reminder_service.ReminderService.refresh_reminders_for_appointment",
        return_value=[],
    )
    appt_id = uuid4()
    existing = {
        "id": str(appt_id),
        "patient_id": str(uuid4()),
        "professional_id": str(uuid4()),
        "service_id": str(uuid4()),
        "scheduled_at": "2026-06-10T14:00:00+00:00",
        "duration_minutes": 30,
        "status": "confirmed",
        "organization_id": "org-1",
    }
    fetch = _scoped_fetch(existing)
    # conflict query returns no rows
    conflict = MagicMock()
    conflict.select.return_value.eq.return_value.gte.return_value.lte.return_value.not_.in_.return_value.neq.return_value.execute.return_value = (
        _mock_response([])
    )
    write = _RecordingWrite([{"id": str(appt_id), "duration_minutes": 60}])
    mock_scheduling_db.client.table.side_effect = [fetch, conflict, write]

    await scheduling_service.reschedule_appointment(
        appt_id, duration_minutes=60, organization_id="org-1"
    )
    assert ("organization_id", "org-1") in write.eq_calls


@pytest.mark.asyncio
async def test_super_admin_write_stays_cross_tenant(scheduling_service, mock_scheduling_db, mocker):
    """super_admin (organization_id='ALL') must NOT add an org filter to the write —
    cross-tenant operation is intentional."""
    appt_id = uuid4()
    fetch = _scoped_fetch(
        {"id": str(appt_id), "status": "confirmed", "patient_id": None,
         "organization_id": "org-7"}
    )
    write = _RecordingWrite([{"id": str(appt_id), "status": "completed"}])
    mock_scheduling_db.client.table.side_effect = [fetch, write]

    await scheduling_service.update_appointment_status(
        appt_id, AppointmentStatus.COMPLETED, organization_id="ALL"
    )
    org_filters = [c for c in write.eq_calls if c[0] == "organization_id"]
    assert org_filters == []  # no org filter on the write for ALL


@pytest.mark.asyncio
async def test_no_show_count_write_is_org_scoped(scheduling_service, mock_scheduling_db, mocker):
    """Entering no_show adjusts patients.no_show_count; that patients write is
    scoped by the appointment's org."""
    appt_id = uuid4()
    patient_id = str(uuid4())
    fetch = _scoped_fetch(
        {"id": str(appt_id), "status": "confirmed", "patient_id": patient_id,
         "organization_id": "org-9"}
    )
    appt_write = _RecordingWrite([{"id": str(appt_id), "status": "no_show"}])
    patient_select = _RecordingWrite({"no_show_count": 2})
    patient_write = _RecordingWrite([{"id": patient_id, "no_show_count": 3}])
    mock_scheduling_db.client.table.side_effect = [
        fetch, appt_write, patient_select, patient_write
    ]

    await scheduling_service.update_appointment_status(
        appt_id, AppointmentStatus.NO_SHOW, organization_id="org-9"
    )
    assert ("organization_id", "org-9") in patient_select.eq_calls
    assert ("organization_id", "org-9") in patient_write.eq_calls
    assert patient_write.payload == {"no_show_count": 3}


# --------------------------------------------------------------------------- #
# 2. The CI guard has teeth (mutation check, à la GAP 3 of #46)
# --------------------------------------------------------------------------- #
def _load_guard():
    """Import the standalone guard script as a module."""
    path = ROOT / "scripts" / "check_tenant_scoped_writes.py"
    name = "check_tenant_scoped_writes"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses can resolve cls.__module__.__dict__.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_UNSCOPED_SRC = '''
def bad(db, appointment_id):
    return (
        db.client.table("appointments")
        .update({"status": "cancelled"})
        .eq("id", appointment_id)
        .execute()
    )
'''

_SCOPED_SRC = '''
def good(db, appointment_id, org_id):
    return (
        db.client.table("appointments")
        .update({"status": "cancelled"})
        .eq("id", appointment_id)
        .eq("organization_id", org_id)
        .execute()
    )
'''

_EXEMPT_SRC = '''
def cron(db, appointment_id):
    # tenant-scope-exempt: platform-wide job keyed by the appointment PK.
    return (
        db.client.table("appointments")
        .update({"status": "no_show"})
        .eq("id", appointment_id)
        .execute()
    )
'''

_INTERNAL_TABLE_SRC = '''
def purge(db, tid):
    return db.client.table("webhook_message_dedup").delete().eq("message_id", tid).execute()
'''


def test_guard_flags_unscoped_business_write(tmp_path):
    guard = _load_guard()
    f = tmp_path / "bad.py"
    f.write_text(_UNSCOPED_SRC, encoding="utf-8")
    findings = guard.scan_paths([f])
    assert len(findings) == 1
    assert findings[0].table == "appointments"
    assert findings[0].method == "update"


def test_guard_passes_scoped_business_write(tmp_path):
    guard = _load_guard()
    f = tmp_path / "good.py"
    f.write_text(_SCOPED_SRC, encoding="utf-8")
    assert guard.scan_paths([f]) == []


def test_guard_honors_exempt_marker(tmp_path):
    guard = _load_guard()
    f = tmp_path / "cron.py"
    f.write_text(_EXEMPT_SRC, encoding="utf-8")
    assert guard.scan_paths([f]) == []


def test_guard_ignores_internal_tables(tmp_path):
    guard = _load_guard()
    f = tmp_path / "internal.py"
    f.write_text(_INTERNAL_TABLE_SRC, encoding="utf-8")
    assert guard.scan_paths([f]) == []


def test_guard_main_exit_codes(tmp_path):
    guard = _load_guard()
    bad = tmp_path / "bad.py"
    bad.write_text(_UNSCOPED_SRC, encoding="utf-8")
    good = tmp_path / "good.py"
    good.write_text(_SCOPED_SRC, encoding="utf-8")

    assert guard.main(["prog", str(bad)]) == 1
    assert guard.main(["prog", str(good)]) == 0


def test_guard_clean_on_current_codebase():
    """Sanity net: the live tree must pass (Task 1 + exemptions in place)."""
    guard = _load_guard()
    findings = guard.scan_paths([ROOT / "packages", ROOT / "apps"])
    assert findings == [], "unexpected unscoped business writes:\n" + "\n".join(
        str(f) for f in findings
    )
