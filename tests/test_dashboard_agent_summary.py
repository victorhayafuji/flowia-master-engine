"""Tests for /dashboard/agent-summary tenant isolation and aggregation."""
from datetime import datetime
from unittest.mock import MagicMock

from tests.conftest import ORG_A, ORG_B


def _chain_mock(execute_result):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.lte.return_value = chain
    chain.limit.return_value = chain
    chain.not_.is_.return_value = chain
    chain.execute.return_value = execute_result
    return chain


def _patch_agent_summary_db(mocker, *, handoffs=0, whatsapp_today=0, threads=None):
    threads = threads or []
    mocker.patch(
        "apps.salon.api.routers.dashboard._day_bounds",
        return_value=(
            datetime(2026, 6, 9, 12, 0, 0),
            datetime(2026, 6, 9, 0, 0, 0),
            datetime(2026, 6, 9, 23, 59, 59),
        ),
    )

    mock_db = mocker.patch("apps.salon.api.routers.dashboard.db")
    mock_db.client = MagicMock()

    patients_result = MagicMock()
    patients_result.count = handoffs

    appt_result = MagicMock()
    appt_result.count = whatsapp_today

    metrics_result = MagicMock()
    metrics_result.data = [{"thread_id": tid} for tid in threads]

    def table(name):
        t = MagicMock()
        if name == "patients":
            t.table = name
            chain = _chain_mock(patients_result)
            t.select.return_value = chain
        elif name == "appointments":
            chain = _chain_mock(appt_result)
            t.select.return_value = chain
        elif name == "conversation_metrics":
            chain = _chain_mock(metrics_result)
            t.select.return_value = chain
        return t

    mock_db.client.table.side_effect = table
    return mock_db


class TestAgentSummary:
    def test_org_admin_matching_org_allowed(self, client, user_token, mocker):
        _patch_agent_summary_db(mocker, handoffs=2, whatsapp_today=3, threads=["a", "b"])
        response = client.get(
            "/api/v1/dashboard/agent-summary",
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["handoffsPending"] == 2
        assert data["appointmentsWhatsappToday"] == 3
        assert data["conversationsThisWeek"] == 2

    def test_org_admin_spoofed_org_returns_403(self, client, user_token):
        response = client.get(
            "/api/v1/dashboard/agent-summary",
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_B},
        )
        assert response.status_code == 403

    def test_super_admin_all_header_allowed(self, client, admin_token, mocker):
        _patch_agent_summary_db(mocker)
        response = client.get(
            "/api/v1/dashboard/agent-summary",
            cookies={"session_token": admin_token},
            headers={"x-organization-id": "ALL"},
        )
        assert response.status_code == 200

    def test_missing_auth_returns_401(self, client):
        response = client.get(
            "/api/v1/dashboard/agent-summary",
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 401
