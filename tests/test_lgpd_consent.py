"""Tests for LGPD consent gate."""
from unittest.mock import MagicMock, patch

from packages.compliance.consent import (
    ConsentAction,
    evaluate_consent_gate,
    has_valid_consent,
    record_notice_shown,
)
from tests.conftest import ORG_A


def test_has_valid_consent_requires_consent_at():
    assert has_valid_consent({"privacy_consent_at": "2026-06-01T00:00:00Z"}) is True
    assert has_valid_consent({"privacy_notice_shown_at": "2026-06-01T00:00:00Z"}) is False
    assert has_valid_consent(None) is False


def _chain_mock(data=None):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.update.return_value = chain
    chain.insert.return_value = chain
    chain.execute.return_value = MagicMock(data=data or [])
    return chain


def test_evaluate_consent_gate_first_contact_sends_notice(mock_db):
    table = MagicMock()
    table.select.return_value = _chain_mock([])
    table.insert.return_value = _chain_mock([{"id": "p1"}])
    mock_db.client.table.return_value = table

    org_table = MagicMock()
    org_table.select.return_value = _chain_mock([{"name": "Beauty Express"}])
    mock_db.client.table.side_effect = lambda name: org_table if name == "organizations" else table

    with patch("packages.compliance.consent.db", mock_db):
        action, msg, lgpd = evaluate_consent_gate(ORG_A, "5511999999999", "whatsapp")

    assert action == ConsentAction.SEND_NOTICE
    assert msg is not None
    assert "LGPD" in msg or "privacidade" in msg.lower() or "dados" in msg.lower()
    assert lgpd is False
    table.insert.assert_called()


def test_evaluate_consent_gate_second_message_records_consent(mock_db):
    patient = {
        "id": "p1",
        "privacy_notice_shown_at": "2026-06-01T00:00:00Z",
        "privacy_consent_at": None,
    }
    table = MagicMock()
    table.select.return_value = _chain_mock([patient])
    table.update.return_value = _chain_mock([patient])
    mock_db.client.table.return_value = table

    with patch("packages.compliance.consent.db", mock_db):
        action, msg, lgpd = evaluate_consent_gate(ORG_A, "5511999999999", "whatsapp")

    assert action == ConsentAction.RECORD_CONSENT
    assert msg is None
    assert lgpd is True
    table.update.assert_called()


def test_evaluate_consent_gate_already_consented(mock_db):
    patient = {
        "id": "p1",
        "privacy_consent_at": "2026-06-01T00:00:00Z",
    }
    table = MagicMock()
    table.select.return_value = _chain_mock([patient])
    mock_db.client.table.return_value = table

    with patch("packages.compliance.consent.db", mock_db):
        action, msg, lgpd = evaluate_consent_gate(ORG_A, "5511999999999", "whatsapp")

    assert action == ConsentAction.PROCEED
    assert lgpd is True


def test_record_notice_shown_updates_existing(mock_db):
    table = MagicMock()
    table.select.return_value = _chain_mock([{"id": "p1"}])
    table.update.return_value = _chain_mock()
    mock_db.client.table.return_value = table

    with patch("packages.compliance.consent.db", mock_db):
        record_notice_shown(ORG_A, "5511999999999", "chat_test")

    table.update.assert_called_once()
