"""Tests for WhatsApp handoff persistence on patients."""
from unittest.mock import MagicMock, patch

from apps.salon.domain.clients.repository import PatientRepository
from packages.auth_core.tenant import set_tenant_context
from tests.conftest import ORG_A


def _chain_mock(data=None):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.update.return_value = chain
    chain.insert.return_value = chain
    chain.execute.return_value = MagicMock(data=data or [])
    return chain


def test_upsert_handoff_updates_existing_patient(mock_db):
    table = MagicMock()
    table.select.return_value = _chain_mock([{"id": "pat-1"}])
    table.update.return_value = _chain_mock()
    mock_db.client.table.return_value = table

    with patch("apps.salon.domain.clients.repository.db", mock_db), set_tenant_context(ORG_A):
        ok = PatientRepository().upsert_handoff_by_sender("5511999999999", reason="Cliente pediu humano")

    assert ok is True
    table.update.assert_called_once()
    update_payload = table.update.call_args[0][0]
    assert update_payload["handoff_reason"] == "Cliente pediu humano"
    assert "handoff_requested_at" in update_payload


def test_upsert_handoff_creates_patient_when_missing(mock_db):
    select_chain = _chain_mock([])
    insert_chain = _chain_mock([{"id": "pat-new"}])
    table = MagicMock()
    table.select.return_value = select_chain
    table.insert.return_value = insert_chain
    mock_db.client.table.return_value = table

    with patch("apps.salon.domain.clients.repository.db", mock_db), set_tenant_context(ORG_A):
        ok = PatientRepository().upsert_handoff_by_sender("5511888777666", reason="KB insuficiente")

    assert ok is True
    table.insert.assert_called_once()
    insert_payload = table.insert.call_args[0][0]
    assert insert_payload["organization_id"] == ORG_A
    assert insert_payload["legacy_sender_id"] == "5511888777666"
    assert insert_payload["phone"] == "5511888777666"


def test_upsert_handoff_requires_org_id(mock_db):
    with patch("apps.salon.domain.clients.repository.db", mock_db), set_tenant_context("ALL"):
        ok = PatientRepository().upsert_handoff_by_sender("5511999999999", reason="test")
    assert ok is False


def test_update_session_state_delegates_to_repository():
    with patch(
        "apps.salon.domain.clients.repository.PatientRepository.upsert_handoff_by_sender",
        return_value=True,
    ) as upsert:
        from packages.integrations.webhook.session_store import update_session_state

        assert update_session_state("wa-123", {"handoff_reason": "Precisa de humano"}) is True
        upsert.assert_called_once_with("wa-123", reason="Precisa de humano")
