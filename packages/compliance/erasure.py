"""DSAR erasure — anonymize patient and purge conversation artifacts."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from packages.auth_core.config import settings
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
    thread_ids = list(
        {
            tid
            for tid in (
                patient.get("legacy_sender_id"),
                patient.get("phone"),
                _anonymized_phone(patient_id),
            )
            if tid
        }
    )

    checkpoints_removed = 0
    for tid in thread_ids:
        checkpoints_removed += purge_checkpoints(tid)

    metrics_removed = purge_conversation_metrics(org_id, thread_ids)

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
    }
    db.client.table("patients").update(update_payload).eq("id", patient_id).execute()

    return {
        "status": "erased",
        "patient_id": patient_id,
        "checkpoints_rows_removed": checkpoints_removed,
        "metrics_rows_removed": metrics_removed,
    }
