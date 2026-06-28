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
    chain.in_.return_value = chain
    chain.execute.return_value = MagicMock(data=data or [])
    return chain


def _build_tables(patient, appointments):
    patients_table = MagicMock()
    patients_table.select.return_value = _chain_mock([patient])
    patients_table.update.return_value = _chain_mock([{"id": patient["id"]}])

    appt_table = MagicMock()
    appt_table.select.return_value = _chain_mock(appointments)

    anamnesis_table = MagicMock()
    anamnesis_table.update.return_value = _chain_mock([{"id": "an1"}])

    payments_table = MagicMock()
    payments_table.update.return_value = _chain_mock([{"id": "pay1"}])

    metrics_table = MagicMock()
    metrics_table.delete.return_value = _chain_mock([{"id": "m1"}])

    def table_router(name):
        return {
            "patients": patients_table,
            "appointments": appt_table,
            "anamnesis_responses": anamnesis_table,
            "appointment_payments": payments_table,
        }.get(name, metrics_table)

    return table_router, patients_table, anamnesis_table, payments_table


def test_erase_patient_anonymizes(mock_db):
    patient = {
        "id": "pat-1",
        "name": "Maria",
        "phone": "5511999999999",
        "legacy_sender_id": "5511999999999",
    }
    router, patients_table, anamnesis_table, payments_table = _build_tables(
        patient, [{"id": "a1"}]
    )
    mock_db.client.table.side_effect = router

    with patch("packages.compliance.erasure.db", mock_db), patch(
        "packages.compliance.erasure.purge_checkpoints", return_value=3
    ):
        result = erase_patient_data(ORG_A, "pat-1")

    assert result["status"] == "erased"
    update_payload = patients_table.update.call_args[0][0]
    assert update_payload["name"] == "[Removido]"
    assert update_payload["is_active"] is False
    assert update_payload["legacy_sender_id"] is None
    # Persisted refusal must be reset on erase.
    assert update_payload["privacy_declined_at"] is None

    # Anamnesis answers zeroed (health PII anonymized, row preserved).
    assert anamnesis_table.update.call_args[0][0] == {"answers": {}}
    # Payments anonymized (financial, never deleted).
    payments_payload = payments_table.update.call_args[0][0]
    assert payments_payload["external_id"] is None
    assert payments_payload["metadata"] == {}

    assert result["anamnesis_rows_anonymized"] == 1
    assert result["payments_rows_anonymized"] == 1


def test_erase_no_appointments_skips_payments(mock_db):
    patient = {"id": "pat-1", "name": "Maria", "phone": "5511999999999"}
    router, _patients, _anamnesis, payments_table = _build_tables(patient, [])
    mock_db.client.table.side_effect = router

    with patch("packages.compliance.erasure.db", mock_db), patch(
        "packages.compliance.erasure.purge_checkpoints", return_value=0
    ):
        result = erase_patient_data(ORG_A, "pat-1")

    payments_table.update.assert_not_called()
    assert result["payments_rows_anonymized"] == 0


def test_erase_is_fail_soft_when_anamnesis_fails(mock_db):
    """One table failing must not abort the whole erase."""
    patient = {"id": "pat-1", "name": "Maria", "phone": "5511999999999"}
    router, patients_table, anamnesis_table, _payments = _build_tables(
        patient, [{"id": "a1"}]
    )
    anamnesis_table.update.side_effect = RuntimeError("boom")
    mock_db.client.table.side_effect = router

    with patch("packages.compliance.erasure.db", mock_db), patch(
        "packages.compliance.erasure.purge_checkpoints", return_value=0
    ):
        result = erase_patient_data(ORG_A, "pat-1")

    # Patient still anonymized despite anamnesis failure.
    assert result["status"] == "erased"
    assert result["anamnesis_rows_anonymized"] == 0
    patients_table.update.assert_called()
