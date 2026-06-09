"""Tests for tenant-scoped conversation metrics."""
from unittest.mock import MagicMock, patch

from packages.engine.metrics.service import get_recent_conversations, get_tokens_daily
from tests.conftest import ORG_A


def test_get_recent_conversations_filters_by_org(mock_db):
    list_chain = MagicMock()
    list_chain.select.return_value = list_chain
    list_chain.order.return_value = list_chain
    list_chain.limit.return_value = list_chain
    list_chain.eq.return_value = list_chain
    list_chain.execute.return_value = MagicMock(
        data=[
            {"thread_id": "t1", "organization_id": ORG_A, "tokens_total": 0},
            {"thread_id": "t2", "organization_id": ORG_A, "tokens_total": 5},
        ]
    )

    totals_chain = MagicMock()
    totals_chain.select.return_value = totals_chain
    totals_chain.gte.return_value = totals_chain
    totals_chain.in_.return_value = totals_chain
    totals_chain.eq.return_value = totals_chain
    totals_chain.limit.return_value = totals_chain
    totals_chain.execute.return_value = MagicMock(
        data=[
            {"thread_id": "t1", "tokens_total": 0},
            {"thread_id": "t1", "tokens_total": 120},
            {"thread_id": "t2", "tokens_total": 5},
        ]
    )

    mock_db.client.table.side_effect = lambda _name: list_chain if list_chain.execute.call_count == 0 else totals_chain
    # Fix side_effect: first call list, second totals
    call_count = {"n": 0}

    def table(_name):
        call_count["n"] += 1
        return list_chain if call_count["n"] == 1 else totals_chain

    mock_db.client.table.side_effect = table
    mock_db.wait_for_ready.return_value = True

    with patch("packages.engine.metrics.service.db", mock_db):
        rows = get_recent_conversations(limit=10, organization_id=ORG_A, days=7)

    list_chain.eq.assert_called_with("organization_id", ORG_A)
    assert len(rows) == 2
    by_thread = {r["thread_id"]: r for r in rows}
    assert by_thread["t1"]["tokens_turn"] == 0
    assert by_thread["t1"]["tokens_thread_7d"] == 120
    assert by_thread["t2"]["tokens_turn"] == 5
    assert by_thread["t2"]["tokens_thread_7d"] == 5


def test_metrics_conversations_endpoint_requires_tenant(client, user_token, mock_db):
    list_chain = MagicMock()
    list_chain.select.return_value = list_chain
    list_chain.order.return_value = list_chain
    list_chain.limit.return_value = list_chain
    list_chain.eq.return_value = list_chain
    list_chain.execute.return_value = MagicMock(data=[])

    totals_chain = MagicMock()
    totals_chain.select.return_value = totals_chain
    totals_chain.gte.return_value = totals_chain
    totals_chain.in_.return_value = totals_chain
    totals_chain.eq.return_value = totals_chain
    totals_chain.limit.return_value = totals_chain
    totals_chain.execute.return_value = MagicMock(data=[])

    call_count = {"n": 0}

    def table(_name):
        call_count["n"] += 1
        return list_chain if call_count["n"] == 1 else totals_chain

    mock_db.client.table.side_effect = table
    mock_db.wait_for_ready.return_value = True

    res = client.get(
        "/api/v1/metrics/conversations",
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_A},
    )
    assert res.status_code == 200


def test_get_tokens_daily_filters_by_org(mock_db):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.gte.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.eq.return_value = chain
    chain.execute.return_value = MagicMock(
        data=[{"created_at": "2026-06-08T10:00:00", "tokens_total": 10}]
    )
    mock_db.client.table.return_value = chain
    mock_db.wait_for_ready.return_value = True

    with patch("packages.engine.metrics.service.db", mock_db):
        rows = get_tokens_daily(days=7, organization_id=ORG_A)

    chain.eq.assert_called_with("organization_id", ORG_A)
    assert rows[0]["tokens"] == 10


def test_metrics_tokens_daily_endpoint_requires_tenant(client, user_token, mock_db):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.gte.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.eq.return_value = chain
    chain.execute.return_value = MagicMock(data=[])
    mock_db.client.table.return_value = chain
    mock_db.wait_for_ready.return_value = True

    with patch("packages.engine.metrics.service.db", mock_db):
        res = client.get(
            "/api/v1/metrics/tokens-daily",
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
    assert res.status_code == 200
    chain.eq.assert_called_with("organization_id", ORG_A)
