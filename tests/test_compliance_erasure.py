"""Tests for DSAR erasure."""
from unittest.mock import MagicMock, patch

from packages.compliance.erasure import erase_patient_data
from tests.conftest import ORG_A


def _chain_mock(data=None):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.update.return_value = chain
    chain.delete.return_value = chain
    chain.execute.return_value = MagicMock(data=data or [])
    return chain


def test_erase_patient_anonymizes(mock_db):
    patient = {
        "id": "pat-1",
        "name": "Maria",
        "phone": "5511999999999",
        "legacy_sender_id": "5511999999999",
    }
    patients_table = MagicMock()
    patients_table.select.return_value = _chain_mock([patient])
    patients_table.update.return_value = _chain_mock([{"id": "pat-1"}])

    metrics_table = MagicMock()
    metrics_table.delete.return_value = _chain_mock([{"id": "m1"}])

    def table_router(name):
        if name == "patients":
            return patients_table
        return metrics_table

    mock_db.client.table.side_effect = table_router

    with patch("packages.compliance.erasure.db", mock_db), patch(
        "packages.compliance.erasure.purge_checkpoints", return_value=3
    ):
        result = erase_patient_data(ORG_A, "pat-1")

    assert result["status"] == "erased"
    update_payload = patients_table.update.call_args[0][0]
    assert update_payload["name"] == "[Removido]"
    assert update_payload["is_active"] is False
    assert update_payload["legacy_sender_id"] is None
