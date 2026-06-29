"""Exhaustive cross-tenant spoof-403 matrix (Onda 2 — no-leak).

An ``org_admin`` whose JWT is bound to ORG_A but who sends
``x-organization-id: ORG_B`` must be barred by ``validated_tenant_context``
(403) BEFORE the handler runs any query. This is the first defense layer of the
multi-tenant isolation (CLAUDE.md §17) and the backend uses SERVICE_ROLE
(bypasses RLS), so the header≠JWT guard is load-bearing.

Pattern mirrored from tests/test_tenant.py and the per-endpoint
``test_*_tenant_spoof_returns_403`` cases. Endpoints already covered elsewhere
(scheduling/, scheduling/calendar, scheduling/calendar/{id}, patients/,
organizations/services, dashboard/agent-summary) are NOT duplicated here.

Dente: each 403 must come from the tenant guard, not from a 404/422/401 for
another reason. We assert the handler's DB/service is NEVER reached on spoof —
``mock_db`` would otherwise let the request proceed and return 200/4xx-other.
The guard short-circuits the dependency, so no table()/service call happens.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from tests.conftest import ORG_A, ORG_B

# (method, path, json_body) — org_admin token (ORG_A) + header ORG_B → 403.
# GET endpoints carry the params they require so a 200-path is reachable when
# the header matches (the guard is the only thing that should produce 403).
_GET_SPOOF_CASES = [
    ("/api/v1/dashboard/stats", None),
    ("/api/v1/dashboard/today-board", None),
    ("/api/v1/dashboard/professional-kpi", None),
    ("/api/v1/dashboard/financial", None),
    ("/api/v1/organizations/professionals", None),
    ("/api/v1/scheduling/blocks?start_date=2026-06-01&end_date=2026-06-30", None),
    ("/api/v1/metrics/kpis", None),
    ("/api/v1/metrics/conversations", None),
    ("/api/v1/metrics/tokens-daily", None),
    ("/api/v1/metrics/knowledge-gaps", None),
    ("/api/v1/metrics/scheduling-observability", None),
    ("/api/v1/lakehouse/status", None),
    ("/api/v1/lakehouse/documents", None),
]


@pytest.fixture(autouse=True)
def _guard_db_untouched(mock_db):
    """A spy on the Supabase client: on a real 403 the handler never queries.

    If the guard ever regressed and the request proceeded, the handler would
    call ``db.client.table(...)`` — we assert it was NOT called, proving the
    403 is the tenant guard short-circuiting and not an incidental error.
    """
    return mock_db


@pytest.mark.parametrize("path,_body", _GET_SPOOF_CASES, ids=[c[0] for c in _GET_SPOOF_CASES])
def test_get_endpoint_tenant_spoof_returns_403(client, user_token, path, _body, mock_db):
    response = client.get(
        path,
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_B},
    )
    assert response.status_code == 403, f"{path} did not 403 on spoof: {response.text}"
    mock_db.client.table.assert_not_called()


def test_professionals_create_spoof_returns_403(client, user_token, mock_db):
    response = client.post(
        "/api/v1/organizations/professionals",
        json={"name": "Ana", "specialty": "corte"},
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_B},
    )
    assert response.status_code == 403
    mock_db.client.table.assert_not_called()


def test_professionals_update_spoof_returns_403(client, user_token, mock_db):
    response = client.put(
        f"/api/v1/organizations/professionals/{uuid4()}",
        json={"name": "Ana"},
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_B},
    )
    assert response.status_code == 403
    mock_db.client.table.assert_not_called()


def test_professionals_delete_spoof_returns_403(client, user_token, mock_db):
    response = client.delete(
        f"/api/v1/organizations/professionals/{uuid4()}",
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_B},
    )
    assert response.status_code == 403
    mock_db.client.table.assert_not_called()


def test_blocks_create_spoof_returns_403(client, user_token, mock_db):
    response = client.post(
        "/api/v1/scheduling/blocks",
        json={
            "starts_at": "2030-01-10T10:00:00+00:00",
            "ends_at": "2030-01-10T11:00:00+00:00",
            "block_type": "manual",
        },
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_B},
    )
    assert response.status_code == 403
    mock_db.client.table.assert_not_called()


def test_blocks_delete_spoof_returns_403(client, user_token, mock_db):
    response = client.delete(
        f"/api/v1/scheduling/blocks/{uuid4()}",
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_B},
    )
    assert response.status_code == 403
    mock_db.client.table.assert_not_called()


def test_lakehouse_ingest_spoof_returns_403(client, user_token, mock_db):
    response = client.post(
        "/api/v1/lakehouse/ingest",
        json={"file_path": "/tmp/x.pdf"},
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_B},
    )
    assert response.status_code == 403
    mock_db.client.table.assert_not_called()


def test_lakehouse_sync_spoof_returns_403(client, user_token, mock_db):
    response = client.post(
        "/api/v1/lakehouse/sync",
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_B},
    )
    assert response.status_code == 403
    mock_db.client.table.assert_not_called()


def test_compliance_export_spoof_returns_403(client, user_token, mock_db):
    response = client.get(
        f"/api/v1/compliance/patients/{uuid4()}/export",
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_B},
    )
    assert response.status_code == 403
    mock_db.client.table.assert_not_called()


def test_compliance_erase_spoof_returns_403(client, user_token, mock_db):
    response = client.post(
        f"/api/v1/compliance/patients/{uuid4()}/erase",
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_B},
    )
    assert response.status_code == 403
    mock_db.client.table.assert_not_called()


# --- Counter-proof the guard isn't blanket-403: the same endpoints with a
# matching header reach the handler (200/4xx-other), so 403 is specifically the
# spoof, never a route that simply always denies. We sample a couple. ---
def test_spoof_guard_is_specific_dashboard_stats_matching_ok(client, user_token, mocker):
    # Matching header → handler runs; mock returns empty so it's a clean 200.
    chain = mocker.MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.lte.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.maybe_single.return_value = chain
    chain.execute.return_value = mocker.MagicMock(data=[], count=0)
    mocker.patch("apps.salon.api.routers.dashboard.db.client.table", return_value=chain)

    response = client.get(
        "/api/v1/dashboard/stats",
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_A},
    )
    assert response.status_code == 200
