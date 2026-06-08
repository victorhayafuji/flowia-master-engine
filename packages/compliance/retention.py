"""LGPD retention — purge stale conversation_metrics and checkpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from packages.auth_core.config import settings
from packages.auth_core.database import db

logger = logging.getLogger(__name__)

METRICS_PURGE_JOB_ID = "cron_purge_conversation_metrics"
CHECKPOINT_PURGE_JOB_ID = "cron_purge_checkpoints"


def _stale_thread_ids(cutoff_iso: str) -> list[str]:
    if not db.client:
        return []
    try:
        response = (
            db.client.table("conversation_metrics")
            .select("thread_id")
            .lt("created_at", cutoff_iso)
            .limit(5000)
            .execute()
        )
        return list({r["thread_id"] for r in (response.data or []) if r.get("thread_id")})
    except Exception as exc:
        logger.warning("[compliance] stale thread lookup failed: %s", exc)
        return []


def purge_checkpoints_for_threads(thread_ids: list[str]) -> int:
    if not thread_ids or not settings.SUPABASE_DB_URL:
        return 0
    total = 0
    tables = ("checkpoint_writes", "checkpoint_blobs", "checkpoints")
    try:
        import psycopg

        with psycopg.connect(settings.SUPABASE_DB_URL, autocommit=True) as conn:
            with conn.cursor() as cur:
                for tid in thread_ids:
                    for table in tables:
                        cur.execute(f"DELETE FROM {table} WHERE thread_id = %s", (tid,))
                        total += cur.rowcount
    except Exception as exc:
        logger.warning("[compliance] checkpoint purge by thread failed: %s", exc)
    return total


def purge_stale_metrics(retention_days: int | None = None) -> int:
    if not db.client:
        return 0
    days = retention_days if retention_days is not None else settings.CONVERSATION_METRICS_RETENTION_DAYS
    if days <= 0:
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        result = db.client.table("conversation_metrics").delete().lt("created_at", cutoff).execute()
        removed = len(result.data or [])
        if removed:
            logger.info("[compliance] Purged %s conversation_metrics older than %s days", removed, days)
        return removed
    except Exception as exc:
        logger.warning("[compliance] metrics purge failed: %s", exc)
        return 0


def purge_stale_checkpoints(retention_days: int | None = None) -> int:
    days = retention_days if retention_days is not None else settings.CHECKPOINT_RETENTION_DAYS
    if days <= 0:
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    thread_ids = _stale_thread_ids(cutoff)
    removed = purge_checkpoints_for_threads(thread_ids)
    if removed:
        logger.info("[compliance] Purged ~%s checkpoint rows for %s stale threads", removed, len(thread_ids))
    return removed


def register_retention_jobs(scheduler: BackgroundScheduler) -> None:
    scheduler.add_job(
        purge_stale_checkpoints,
        "cron",
        hour=4,
        minute=0,
        id=CHECKPOINT_PURGE_JOB_ID,
        replace_existing=True,
    )
    scheduler.add_job(
        purge_stale_metrics,
        "cron",
        hour=4,
        minute=30,
        id=METRICS_PURGE_JOB_ID,
        replace_existing=True,
    )
    logger.info("[compliance] Registered retention purge jobs")
