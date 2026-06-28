"""DSAR data export (portability)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from packages.auth_core.conversation_thread import patient_thread_id_candidates
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

    # Anamnesis responses (sensitive health PII) — filed directly against the patient.
    anamnesis_q = (
        db.client.table("anamnesis_responses")
        .select("id, appointment_id, answers, status, created_at, updated_at")
        .eq("patient_id", pid)
    )
    if org_id and org_id != "ALL":
        anamnesis_q = anamnesis_q.eq("organization_id", org_id)
    anamnesis_responses = anamnesis_q.execute().data or []

    # Appointment payments (financial PII) — no patient_id column; correlate via
    # the patient's own appointment ids (never another patient's).
    appointment_payments: list[dict] = []
    appointment_ids = [a["id"] for a in appointments if a.get("id")]
    if appointment_ids:
        payments_q = (
            db.client.table("appointment_payments")
            .select(
                "id, appointment_id, amount_cents, currency, status, "
                "provider, external_id, metadata, created_at"
            )
            .in_("appointment_id", appointment_ids)
        )
        if org_id and org_id != "ALL":
            payments_q = payments_q.eq("organization_id", org_id)
        appointment_payments = payments_q.execute().data or []

    effective_org = org_id if org_id and org_id != "ALL" else str(patient.get("organization_id") or "")
    thread_ids = patient_thread_id_candidates(effective_org, patient) if effective_org else []

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
        "anamnesis_responses": anamnesis_responses,
        "appointment_payments": appointment_payments,
        "conversation_metrics": metrics,
        "note": "Conteúdo integral de mensagens não incluído; solicite ao encarregado se necessário.",
    }
