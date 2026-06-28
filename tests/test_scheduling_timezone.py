"""Timezone normalization for scheduling."""
from datetime import date, datetime, timezone

import pytest

import packages.scheduling.timezone_utils as tz_utils
from packages.scheduling.timezone_utils import (
    DEFAULT_TIMEZONE,
    local_day_utc_bounds,
    normalize_to_utc,
    resolve_org_timezone,
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


# --- resolve_org_timezone TTL cache (perf §39) ---

ORG = "11111111-1111-1111-1111-111111111111"


@pytest.fixture(autouse=True)
def _clear_tz_cache():
    """Cache is process-global — wipe it before/after each test to avoid leakage."""
    tz_utils._TZ_CACHE.clear()
    yield
    tz_utils._TZ_CACHE.clear()


def _patch_db(mocker, tzname="America/Recife"):
    """Mock the lazily-imported global db singleton and return the execute mock."""
    fake_db = mocker.MagicMock()
    chain = fake_db.client.table.return_value
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.maybe_single.return_value = chain
    chain.execute.return_value = mocker.MagicMock(data={"timezone": tzname})
    mocker.patch("packages.auth_core.database.db", fake_db)
    return chain.execute


def test_resolve_org_timezone_caches_after_first_query(mocker):
    execute = _patch_db(mocker, "America/Recife")

    first = resolve_org_timezone(ORG)
    second = resolve_org_timezone(ORG)

    assert first == "America/Recife"
    assert second == "America/Recife"
    assert execute.call_count == 1  # second call served from cache


def test_resolve_org_timezone_requeries_after_ttl_expiry(mocker):
    execute = _patch_db(mocker, "America/Recife")
    # Freeze monotonic so we control TTL expiry deterministically.
    clock = {"t": 1000.0}
    mocker.patch.object(tz_utils._time, "monotonic", lambda: clock["t"])

    resolve_org_timezone(ORG)
    assert execute.call_count == 1

    clock["t"] += tz_utils._TZ_CACHE_TTL_SECONDS + 1  # past TTL window
    resolve_org_timezone(ORG)
    assert execute.call_count == 2  # cache expired → fresh query


def test_resolve_org_timezone_wildcard_and_none_never_query(mocker):
    execute = _patch_db(mocker, "America/Recife")

    assert resolve_org_timezone("ALL") == DEFAULT_TIMEZONE
    assert resolve_org_timezone(None) == DEFAULT_TIMEZONE

    assert execute.call_count == 0  # short-circuit before any DB access


def test_resolve_org_timezone_transient_failure_not_cached(mocker):
    fake_db = mocker.MagicMock()
    fake_db.client.table.side_effect = RuntimeError("db down")
    mocker.patch("packages.auth_core.database.db", fake_db)

    # Fallback returned but NOT cached — a later success must re-query.
    assert resolve_org_timezone(ORG) == DEFAULT_TIMEZONE
    assert ORG not in tz_utils._TZ_CACHE
