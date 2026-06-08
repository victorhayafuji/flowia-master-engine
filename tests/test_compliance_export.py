"""Tests for DSAR export."""
from unittest.mock import MagicMock, patch

import pytest

from packages.compliance.export import export_patient_data
from tests.conftest import ORG_A


def _chain_mock(data=None):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.order.return_value = chain
    chain.execute.return_value = MagicMock(data=data or [])
    return chain


def test_export_patient_data_bundle(mock_db):
    patient = {"id": "pat-1", "name": "Maria", "phone": "5511999999999", "legacy_sender_id": "5511999999999"}
    patients_table = MagicMock()
    patients_table.select.return_value = _chain_mock([patient])

    appt_table = MagicMock()
    appt_table.select.return_value = _chain_mock([{"id": "a1", "status": "scheduled"}])

    metrics_table = MagicMock()
    metrics_table.select.return_value = _chain_mock([{"thread_id": "5511999999999", "tokens_total": 10}])

    def table_router(name):
        if name == "patients":
            return patients_table
        if name == "appointments":
            return appt_table
        return metrics_table

    mock_db.client.table.side_effect = table_router

    with patch("packages.compliance.export.db", mock_db):
        bundle = export_patient_data(ORG_A, "pat-1")

    assert bundle["format"] == "flowia-dsar-v1"
    assert bundle["patient"]["name"] == "Maria"
    assert len(bundle["appointments"]) == 1
    assert len(bundle["conversation_metrics"]) >= 1


def test_export_patient_not_found(mock_db):
    table = MagicMock()
    table.select.return_value = _chain_mock([])
    mock_db.client.table.return_value = table

    with patch("packages.compliance.export.db", mock_db):
        with pytest.raises(ValueError, match="não encontrado"):
            export_patient_data(ORG_A, "missing")
