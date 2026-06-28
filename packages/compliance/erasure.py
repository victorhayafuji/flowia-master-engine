"""DSAR erasure — anonymize patient and purge conversation artifacts."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from packages.auth_core.config import settings
from packages.auth_core.conversation_thread import patient_thread_id_candidates
from packages.auth_core.database import db

logger = logging.getLogger(__name__)


def _anonymized_phone(patient_id: str) -> str:
    digest = hashlib.sha256(patient_id.encode()).hexdigest()[:12]
    return f"removed-{digest}"


def purge_checkpoints(thread_id: str) -> int:
    """Delete LangGraph checkpoint rows for thread_id. Returns approximate rows removed."""
    if not thread_id or not settings.SUPABASE_DB_URL:
        return 0
    tables = ("checkpoint_writes", "checkpoint_blobs", "checkpoints")
    total = 0
    try:
        import psycopg

        with psycopg.connect(settings.SUPABASE_DB_URL, autocommit=True) as conn:
            with conn.cursor() as cur:
                for table in tables:
                    cur.execute(f"DELETE FROM {table} WHERE thread_id = %s", (thread_id,))
                    total += cur.rowcount
    except Exception as exc:
        logger.warning("purge_checkpoints failed for thread %s: %s", thread_id[:8], exc)
    return total


def purge_conversation_metrics(org_id: str, thread_ids: list[str]) -> int:
    if not db.client:
        return 0
    removed = 0
    for tid in thread_ids:
        if not tid:
            continue
        try:
            q = db.client.table("conversation_metrics").delete().eq("thread_id", tid)
            if org_id and org_id != "ALL":
                q = q.eq("organization_id", org_id)
            result = q.execute()
            removed += len(result.data or [])
        except Exception as exc:
            logger.warning("purge metrics failed: %s", exc)
    return removed


def erase_patient_data(org_id: str, patient_id: str) -> dict[str, Any]:
    if not db.client:
        raise RuntimeError("Database unavailable")

    patient_q = db.client.table("patients").select("*").eq("id", patient_id)
    if org_id and org_id != "ALL":
        patient_q = patient_q.eq("organization_id", org_id)
    patient_res = patient_q.limit(1).execute()
    if not patient_res.data:
        raise ValueError("Cliente não encontrado")

    patient = patient_res.data[0]
    # Patient's own appointment ids — used to correlate appointment_payments
    # (which has no patient_id column) without touching another patient's rows.
    appointments = (
        db.client.table("appointments")
        .select("id")
        .eq("patient_id", patient_id)
        .execute()
        .data
        or []
    )
    effective_org = org_id if org_id and org_id != "ALL" else str(patient.get("organization_id") or "")
    thread_ids = patient_thread_id_candidates(effective_org, patient) if effective_org else []
    anon = _anonymized_phone(patient_id)
    if anon not in thread_ids:
        thread_ids.append(anon)

    checkpoints_removed = 0
    for tid in thread_ids:
        checkpoints_removed += purge_checkpoints(tid)

    metrics_removed = purge_conversation_metrics(org_id, thread_ids)

    # Anamnesis responses (sensitive health PII): anonymize the content rather than
    # deleting the row — appointments hold an FK, and the project policy is
    # anonymization over hard delete (CLAUDE.md §14). Zeroing `answers` removes the PII
    # while preserving referential integrity with appointments.
    anamnesis_anonymized = 0
    try:
        aq = db.client.table("anamnesis_responses").update({"answers": {}}).eq("patient_id", patient_id)
        if org_id and org_id != "ALL":
            aq = aq.eq("organization_id", org_id)
        anamnesis_anonymized = len(aq.execute().data or [])
    except Exception as exc:
        logger.warning("erase anamnesis_responses failed: %s", exc)

    # Appointment payments (financial, FK ON DELETE RESTRICT): never delete — strip the
    # identifiable fields (external_id, metadata) for the patient's own appointments.
    payments_anonymized = 0
    appointment_ids = [a["id"] for a in appointments if a.get("id")]
    if appointment_ids:
        try:
            pq = (
                db.client.table("appointment_payments")
                .update({"external_id": None, "metadata": {}})
                .in_("appointment_id", appointment_ids)
            )
            if org_id and org_id != "ALL":
                pq = pq.eq("organization_id", org_id)
            payments_anonymized = len(pq.execute().data or [])
        except Exception as exc:
            logger.warning("erase appointment_payments failed: %s", exc)

    anon_phone = _anonymized_phone(patient_id)
    update_payload = {
        "name": "[Removido]",
        "phone": anon_phone,
        "email": None,
        "legacy_sender_id": None,
        "handoff_requested_at": None,
        "handoff_reason": None,
        "is_active": False,
        "privacy_consent_at": None,
        "privacy_notice_shown_at": None,
        "privacy_notice_version": None,
        "privacy_consent_channel": None,
        "privacy_declined_at": None,
    }
    db.client.table("patients").update(update_payload).eq("id", patient_id).execute()

    return {
        "status": "erased",
        "patient_id": patient_id,
        "checkpoints_rows_removed": checkpoints_removed,
        "metrics_rows_removed": metrics_removed,
        "anamnesis_rows_anonymized": anamnesis_anonymized,
        "payments_rows_anonymized": payments_anonymized,
    }
