"""Timezone normalization for scheduling."""
from datetime import date, datetime, timezone

from packages.scheduling.timezone_utils import (
    local_day_utc_bounds,
    normalize_to_utc,
    storage_iso,
    to_local_naive,
)


def test_naive_local_interpreted_as_sao_paulo():
    dt = datetime(2026, 6, 10, 14, 0)
    utc = normalize_to_utc(dt, "America/Sao_Paulo")
    assert utc == datetime(2026, 6, 10, 17, 0, tzinfo=timezone.utc)


def test_aware_utc_passthrough():
    dt = datetime(2026, 6, 10, 17, 0, tzinfo=timezone.utc)
    utc = normalize_to_utc(dt, "America/Sao_Paulo")
    assert utc == dt


def test_storage_iso_uses_z_suffix():
    dt = datetime(2026, 6, 10, 17, 0, tzinfo=timezone.utc)
    assert storage_iso(dt) == "2026-06-10T17:00:00Z"


def test_local_day_bounds_for_sao_paulo():
    start, end = local_day_utc_bounds(date(2026, 6, 10), "America/Sao_Paulo")
    assert start == "2026-06-10T03:00:00Z"
    assert end.startswith("2026-06-11T02:59:59")


def test_roundtrip_local_display():
    local = datetime(2026, 6, 10, 14, 0)
    utc = normalize_to_utc(local, "America/Sao_Paulo")
    back = to_local_naive(utc, "America/Sao_Paulo")
    assert back == local
