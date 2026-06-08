"""DSAR data export (portability)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from packages.auth_core.database import db

logger = logging.getLogger(__name__)


def export_patient_data(org_id: str, patient_id: str) -> dict[str, Any]:
    """Bundle patient + appointments + conversation metrics metadata."""
    if not db.client:
        raise RuntimeError("Database unavailable")

    patient_q = db.client.table("patients").select("*").eq("id", patient_id)
    if org_id and org_id != "ALL":
        patient_q = patient_q.eq("organization_id", org_id)
    patient_res = patient_q.limit(1).execute()
    if not patient_res.data:
        raise ValueError("Cliente não encontrado")

    patient = patient_res.data[0]
    pid = patient["id"]

    appointments = (
        db.client.table("appointments")
        .select("id, scheduled_at, duration_minutes, status, created_at")
        .eq("patient_id", pid)
        .execute()
        .data
        or []
    )

    thread_ids: list[str] = []
    if patient.get("legacy_sender_id"):
        thread_ids.append(patient["legacy_sender_id"])
    if patient.get("phone"):
        thread_ids.append(patient["phone"])

    metrics: list[dict] = []
    for tid in thread_ids:
        mq = (
            db.client.table("conversation_metrics")
            .select(
                "thread_id, agent_type, messages_count, tokens_total, channel, "
                "created_at, handoff_requested, scheduling_path"
            )
            .eq("thread_id", tid)
        )
        if org_id and org_id != "ALL":
            mq = mq.eq("organization_id", org_id)
        metrics.extend(mq.order("created_at", desc=True).limit(100).execute().data or [])

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "format": "flowia-dsar-v1",
        "patient": patient,
        "appointments": appointments,
        "conversation_metrics": metrics,
        "note": "Conteúdo integral de mensagens não incluído; solicite ao encarregado se necessário.",
    }
