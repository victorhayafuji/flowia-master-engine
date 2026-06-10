"""Background warmup so Render health checks pass within 5s (lifespan must not block listen)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

_warmup_task: asyncio.Task[None] | None = None
_state: dict[str, Any] = {
    "ready": False,
    "database": "warming",
    "checkpointer": "warming",
}


def is_ready() -> bool:
    return bool(_state["ready"])


def get_warmup_snapshot() -> dict[str, Any]:
    return dict(_state)


async def _run_warmup() -> None:
    global _state

    try:
        from packages.engine.checkpointer import init_checkpointer_async

        await init_checkpointer_async()
        _state["checkpointer"] = "ready"
    except Exception as exc:
        logger.error("[FlowIA] Checkpointer warmup failed: %s", exc)
        _state["checkpointer"] = "error"

    try:
        from packages.auth_core.database import SupabaseHandler

        db = SupabaseHandler()
        if db.is_ready:
            db.client.table("conversation_metrics").select("id").limit(1).execute()
            _state["database"] = "connected"
            logger.info("[FlowIA] Supabase conectado!")
        else:
            _state["database"] = "disconnected"
            logger.error("[FlowIA] Supabase offline")
    except Exception as exc:
        _state["database"] = "error"
        logger.error("[FlowIA] Erro no aquecimento Supabase: %s", exc)

    try:
        from packages.compliance.retention import register_retention_jobs
        from packages.integrations.webhook.dedup import register_dedup_purge_job
        from packages.scheduling.scheduler import get_scheduler, start_scheduler

        start_scheduler()
        if sched := get_scheduler():
            register_dedup_purge_job(sched)
            register_retention_jobs(sched)
    except Exception as exc:
        logger.error("[FlowIA] Scheduler warmup failed: %s", exc)

    _state["ready"] = True
    logger.info("[FlowIA] Aquecimento concluído")


def start_background_warmup() -> asyncio.Task[None]:
    global _warmup_task
    if _warmup_task is None or _warmup_task.done():
        _warmup_task = asyncio.create_task(_run_warmup())
    return _warmup_task


async def shutdown_warmup() -> None:
    global _warmup_task, _state

    if _warmup_task is not None and not _warmup_task.done():
        _warmup_task.cancel()
        try:
            await _warmup_task
        except asyncio.CancelledError:
            pass
    _warmup_task = None

    from packages.scheduling.scheduler import stop_scheduler

    stop_scheduler()

    from packages.engine.checkpointer import shutdown_checkpointer_async

    await shutdown_checkpointer_async()

    _state = {
        "ready": False,
        "database": "warming",
        "checkpointer": "warming",
    }
