"""Tests for org-scoped conversation thread_id helpers."""

from packages.auth_core.conversation_thread import (
    build_thread_id,
    patient_thread_id_candidates,
    thread_id_candidates,
)
from tests.conftest import ORG_A


def test_build_thread_id():
    assert build_thread_id(ORG_A, "5511999999999") == f"{ORG_A}:5511999999999"


def test_thread_id_candidates_includes_legacy():
    candidates = thread_id_candidates(ORG_A, "5511999999999")
    assert candidates[0] == f"{ORG_A}:5511999999999"
    assert "5511999999999" in candidates


def test_patient_thread_id_candidates_dedupes():
    patient = {
        "legacy_sender_id": "5511999999999",
        "phone": "5511999999999",
    }
    ids = patient_thread_id_candidates(ORG_A, patient)
    assert ids[0] == f"{ORG_A}:5511999999999"
    assert len(ids) == 2
