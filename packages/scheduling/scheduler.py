import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

from packages.scheduling.no_show_service import NoShowService
from packages.scheduling.reminder_service import ReminderService

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def is_scheduler_enabled() -> bool:
    from packages.auth_core.config import settings

    if not settings.SCHEDULER_ENABLED:
        return False
    return os.getenv("SCHEDULER_ENABLED", "true").lower() not in ("0", "false", "no")


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if not is_scheduler_enabled():
        logger.info("[scheduler] Disabled via SCHEDULER_ENABLED")
        return None
    if _scheduler is not None:
        return _scheduler

    reminder_service = ReminderService()
    no_show_service = NoShowService()

    _scheduler = BackgroundScheduler()

    _scheduler.add_job(
        reminder_service.process_pending_reminders,
        "interval",
        minutes=5,
        id="cron_send_reminders",
        replace_existing=True,
    )
    _scheduler.add_job(
        no_show_service.detect_no_shows,
        "interval",
        minutes=15,
        id="cron_detect_no_shows",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("[scheduler] Background jobs started")
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("[scheduler] Stopped")


def get_scheduler() -> BackgroundScheduler | None:
    return _scheduler
