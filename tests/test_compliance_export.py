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


def test_export_includes_anamnesis_and_payments(mock_db):
    """DSAR bundle must include anamnesis (health) + payments (financial)."""
    patient = {"id": "pat-1", "name": "Maria", "phone": "5511999999999", "legacy_sender_id": "5511999999999"}
    patients_table = MagicMock()
    patients_table.select.return_value = _chain_mock([patient])

    appt_table = MagicMock()
    appt_table.select.return_value = _chain_mock([{"id": "a1", "status": "scheduled"}])

    anamnesis_table = MagicMock()
    anamnesis_table.select.return_value = _chain_mock(
        [{"id": "an1", "appointment_id": "a1", "answers": {"allergy": "none"}}]
    )

    captured_in: dict = {}

    def _payments_chain():
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain

        def _in(col, ids):
            captured_in["col"] = col
            captured_in["ids"] = ids
            return chain

        chain.in_.side_effect = _in
        chain.execute.return_value = MagicMock(data=[{"id": "pay1", "appointment_id": "a1", "amount_cents": 5000}])
        return chain

    payments_table = MagicMock()
    payments_chain = _payments_chain()
    payments_table.select.return_value = payments_chain

    metrics_table = MagicMock()
    metrics_table.select.return_value = _chain_mock([{"thread_id": "5511999999999", "tokens_total": 10}])

    def table_router(name):
        if name == "patients":
            return patients_table
        if name == "appointments":
            return appt_table
        if name == "anamnesis_responses":
            return anamnesis_table
        if name == "appointment_payments":
            return payments_table
        return metrics_table

    mock_db.client.table.side_effect = table_router

    with patch("packages.compliance.export.db", mock_db):
        bundle = export_patient_data(ORG_A, "pat-1")

    assert len(bundle["anamnesis_responses"]) == 1
    assert bundle["anamnesis_responses"][0]["answers"] == {"allergy": "none"}
    assert len(bundle["appointment_payments"]) == 1
    # Payments correlated by THIS patient's appointment ids — not another patient's.
    assert captured_in["col"] == "appointment_id"
    assert captured_in["ids"] == ["a1"]


def test_export_no_appointments_skips_payments_in(mock_db):
    """Patient with no appointments must not call .in_ with an empty list."""
    patient = {"id": "pat-1", "name": "Maria", "phone": "5511999999999"}
    patients_table = MagicMock()
    patients_table.select.return_value = _chain_mock([patient])

    appt_table = MagicMock()
    appt_table.select.return_value = _chain_mock([])  # no appointments

    anamnesis_table = MagicMock()
    anamnesis_table.select.return_value = _chain_mock([])

    payments_table = MagicMock()
    payments_chain = _chain_mock([])
    payments_table.select.return_value = payments_chain

    metrics_table = MagicMock()
    metrics_table.select.return_value = _chain_mock([])

    def table_router(name):
        return {
            "patients": patients_table,
            "appointments": appt_table,
            "anamnesis_responses": anamnesis_table,
            "appointment_payments": payments_table,
        }.get(name, metrics_table)

    mock_db.client.table.side_effect = table_router

    with patch("packages.compliance.export.db", mock_db):
        bundle = export_patient_data(ORG_A, "pat-1")

    assert bundle["appointment_payments"] == []
    payments_chain.in_.assert_not_called()


def test_export_patient_not_found(mock_db):
    table = MagicMock()
    table.select.return_value = _chain_mock([])
    mock_db.client.table.return_value = table

    with patch("packages.compliance.export.db", mock_db):
        with pytest.raises(ValueError, match="não encontrado"):
            export_patient_data(ORG_A, "missing")
