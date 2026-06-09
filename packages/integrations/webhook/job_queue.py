"""Supabase-backed FIFO queue for inbound WhatsApp jobs."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from packages.auth_core.config import settings
from packages.auth_core.conversation_thread import build_thread_id
from packages.auth_core.database import db
from packages.integrations.webhook.dedup import try_claim_message
from packages.integrations.webhook.processor import MAX_JOB_ATTEMPTS, process_job_record
from packages.integrations.webhook.schemas import WhatsAppWebhookPayload
from packages.integrations.webhook.tenant_resolver import resolve_org_id_from_webhook_value

logger = logging.getLogger(__name__)

JOB_TABLE = "whatsapp_inbound_jobs"


def enqueue_job(
    *,
    organization_id: str,
    message_id: str,
    sender_id: str,
    text_body: str,
) -> str | None:
    """Insert a pending job. Returns job id or None if duplicate message_id."""
    if not db.client:
        return None

    thread_id = build_thread_id(organization_id, sender_id)
    row = {
        "organization_id": organization_id,
        "message_id": message_id,
        "sender_id": sender_id,
        "thread_id": thread_id,
        "payload": {
            "org_id": organization_id,
            "message_id": message_id,
            "sender_id": sender_id,
            "text_body": text_body,
        },
        "status": "pending",
    }
    try:
        result = db.client.table(JOB_TABLE).insert(row).execute()
        if result.data:
            return result.data[0]["id"]
    except Exception as exc:
        err = str(exc).lower()
        if "duplicate" in err or "unique" in err or "23505" in err:
            logger.info("Duplicate whatsapp job message_id=%s — skipping enqueue", message_id)
            return None
        raise
    return None


def claim_next_job() -> dict[str, Any] | None:
    """Claim oldest pending job (FIFO) with per-thread serialization."""
    if not settings.SUPABASE_DB_URL:
        return None

    sql = """
        WITH next_job AS (
            SELECT j.id
            FROM whatsapp_inbound_jobs j
            WHERE j.status = 'pending'
              AND j.attempts < %s
              AND NOT EXISTS (
                  SELECT 1
                  FROM whatsapp_inbound_jobs busy
                  WHERE busy.thread_id = j.thread_id
                    AND busy.status = 'processing'
              )
            ORDER BY j.created_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        UPDATE whatsapp_inbound_jobs
        SET status = 'processing',
            started_at = now(),
            attempts = attempts + 1
        WHERE id = (SELECT id FROM next_job)
        RETURNING *
    """
    try:
        import psycopg

        with psycopg.connect(settings.SUPABASE_DB_URL, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (MAX_JOB_ATTEMPTS,))
                row = cur.fetchone()
                if not row:
                    return None
                columns = [desc.name for desc in cur.description]
                return dict(zip(columns, row, strict=False))
    except Exception as exc:
        logger.warning("claim_next_job failed: %s", exc)
        return None


def mark_job_done(job_id: str) -> None:
    if not db.client:
        return
    db.client.table(JOB_TABLE).update(
        {
            "status": "done",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error": None,
        }
    ).eq("id", job_id).execute()


def mark_job_failed(job_id: str, error: str, *, retry: bool = True) -> None:
    if not db.client:
        return
    job_res = db.client.table(JOB_TABLE).select("attempts").eq("id", job_id).limit(1).execute()
    attempts = (job_res.data or [{}])[0].get("attempts") or MAX_JOB_ATTEMPTS
    status = "pending" if retry and attempts < MAX_JOB_ATTEMPTS else "failed"
    db.client.table(JOB_TABLE).update(
        {
            "status": status,
            "finished_at": datetime.now(timezone.utc).isoformat() if status == "failed" else None,
            "error": error[:500],
        }
    ).eq("id", job_id).execute()


def process_job_by_id(job_id: str) -> None:
    if not db.client:
        raise RuntimeError("Database unavailable")
    result = db.client.table(JOB_TABLE).select("*").eq("id", job_id).limit(1).execute()
    if not result.data:
        raise ValueError(f"Job not found: {job_id}")
    job = result.data[0]
    try:
        process_job_record(job)
        mark_job_done(job_id)
    except Exception as exc:
        mark_job_failed(job_id, str(exc))
        raise


def dispatch_whatsapp_payload(payload: WhatsAppWebhookPayload) -> None:
    """Enqueue each text message; process inline when WHATSAPP_QUEUE_MODE=inline."""
    from packages.integrations.webhook.processor import iter_text_messages

    inline = settings.WHATSAPP_QUEUE_MODE.lower() != "worker"

    for value, msg in iter_text_messages(payload):
        message_id = msg.get("id")
        sender_id = msg.get("from", "unknown")
        text_body = msg.get("text", {}).get("body", "")
        if not text_body:
            continue

        if message_id and not try_claim_message(str(message_id)):
            logger.info("Duplicate webhook message_id=%s — skipping enqueue", message_id)
            continue

        org_id = resolve_org_id_from_webhook_value(value)
        if not org_id:
            logger.error("Skipping message — organization unresolved for webhook")
            continue

        if not message_id:
            if inline:
                from packages.integrations.webhook.processor import process_inbound_text_message

                process_inbound_text_message(
                    org_id=org_id,
                    sender_id=sender_id,
                    text_body=text_body,
                    message_id=None,
                )
            continue

        job_id = enqueue_job(
            organization_id=org_id,
            message_id=str(message_id),
            sender_id=str(sender_id),
            text_body=str(text_body),
        )
        if job_id and inline:
            try:
                process_job_by_id(job_id)
            except Exception as exc:
                logger.error("Inline job %s failed: %s", job_id, exc, exc_info=True)
