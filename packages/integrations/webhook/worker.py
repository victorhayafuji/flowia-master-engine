"""Background worker for WhatsApp inbound job queue."""

from __future__ import annotations

import logging
import time

from packages.integrations.webhook.job_queue import claim_next_job, mark_job_done, mark_job_failed
from packages.integrations.webhook.processor import process_job_record

logger = logging.getLogger(__name__)

POLL_SECONDS = 2.0


def run_worker_loop(poll_seconds: float = POLL_SECONDS) -> None:
    logger.info("WhatsApp worker started (poll=%ss)", poll_seconds)
    while True:
        job = claim_next_job()
        if not job:
            time.sleep(poll_seconds)
            continue

        job_id = job["id"]
        try:
            process_job_record(job)
            mark_job_done(job_id)
        except Exception as exc:
            logger.error("Job %s failed: %s", job_id, exc, exc_info=True)
            mark_job_failed(job_id, str(exc))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_worker_loop()
