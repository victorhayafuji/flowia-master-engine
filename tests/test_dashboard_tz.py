"""Timezone-correctness of the dashboard date helpers (no DB).

Slicing the raw UTC ``scheduled_at`` string misclassifies appointments across the
day boundary at night; these guard the org-timezone conversion.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from apps.salon.api.routers.dashboard import _appt_day_in_tz, _parse_aware

SP = ZoneInfo("America/Sao_Paulo")  # UTC-3


def test_parse_aware_handles_z_naive_and_none():
    assert _parse_aware(None) is None
    assert _parse_aware("garbage") is None
    z = _parse_aware("2026-06-21T12:00:00Z")
    assert z is not None and z.tzinfo is not None
    naive = _parse_aware("2026-06-21T10:00:00")  # assume UTC
    assert naive is not None and naive.tzinfo is not None


def test_appt_day_crosses_midnight_in_org_tz():
    # 01:00 UTC on the 21st is 22:00 on the 20th in São Paulo.
    assert _appt_day_in_tz("2026-06-21T01:00:00+00:00", SP) == "2026-06-20"
    # 12:00 UTC on the 21st is 09:00 on the 21st in São Paulo.
    assert _appt_day_in_tz("2026-06-21T12:00:00Z", SP) == "2026-06-21"


def test_appt_day_fallback_on_unparseable():
    assert _appt_day_in_tz(None, SP) is None
    # Unparseable but date-like → first 10 chars as last resort.
    assert _appt_day_in_tz("2026-06-21 weird", SP) == "2026-06-21"


def test_appt_day_matches_naive_local_assumption():
    # Sanity: a midday UTC time stays on the same calendar day in SP.
    dt = datetime(2026, 6, 21, 15, 0, tzinfo=ZoneInfo("UTC"))
    assert _appt_day_in_tz(dt.isoformat(), SP) == "2026-06-21"
