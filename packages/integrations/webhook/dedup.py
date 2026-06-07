"""Persistent webhook message deduplication via Supabase."""

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from packages.auth_core.config import settings
from packages.auth_core.database import db

logger = logging.getLogger(__name__)

PURGE_JOB_ID = "cron_purge_webhook_dedup"


def try_claim_message(message_id: str) -> bool:
    """
    Returns True if this message_id was newly claimed (should process).
    Returns False if already processed (duplicate — skip).
    """
    if not message_id or not db.client:
        return True

    try:
        db.client.table("webhook_message_dedup").insert({"message_id": message_id}).execute()
        return True
    except Exception as exc:
        err = str(exc).lower()
        if "duplicate" in err or "unique" in err or "23505" in err:
            logger.info("Duplicate webhook message_id=%s — skipping", message_id)
            return False
        logger.warning("Dedup insert failed for %s: %s — processing anyway", message_id, exc)
        return True


def purge_stale_entries(retention_days: int | None = None) -> int:
    """Remove dedup rows older than retention_days (default from settings). Returns rows removed."""
    if not db.client:
        return 0

    days = retention_days if retention_days is not None else settings.WEBHOOK_DEDUP_RETENTION_DAYS
    if days <= 0:
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()

    try:
        result = (
            db.client.table("webhook_message_dedup")
            .delete()
            .lt("processed_at", cutoff_iso)
            .execute()
        )
        removed = len(result.data or [])
        if removed:
            logger.info(
                "[webhook_dedup] Purged %s entries older than %s days (before %s)",
                removed,
                days,
                cutoff_iso,
            )
        return removed
    except Exception as exc:
        logger.warning("[webhook_dedup] Purge failed: %s", exc)
        return 0


def register_dedup_purge_job(scheduler: BackgroundScheduler) -> None:
    """Register daily purge of stale webhook dedup rows on the shared APScheduler."""
    scheduler.add_job(
        purge_stale_entries,
        "cron",
        hour=3,
        minute=0,
        id=PURGE_JOB_ID,
        replace_existing=True,
    )
    logger.info("[webhook_dedup] Registered daily purge job (%s)", PURGE_JOB_ID)
