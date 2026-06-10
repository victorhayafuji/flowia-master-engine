"""LangGraph checkpointer — async PostgreSQL (Supabase) with MemorySaver fallback."""
from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

_checkpointer: Any = None
_async_pg_conn: Any = None
_compiled_engine: Any = None


def _use_memory_backend() -> bool:
    from packages.auth_core.config import settings

    return settings.CHECKPOINTER_BACKEND == "memory" or settings.CHECKPOINTER_BACKEND not in (
        "auto",
        "postgres",
    )


def _init_memory_checkpointer() -> None:
    global _checkpointer
    _checkpointer = MemorySaver()
    logger.info("[FlowIA] Checkpointer: MemorySaver")


async def init_checkpointer_async() -> None:
    """Initialize checkpointer at app startup (async graph requires async saver)."""
    global _checkpointer, _async_pg_conn

    if _checkpointer is not None:
        return

    from packages.auth_core.config import settings

    if _use_memory_backend():
        _init_memory_checkpointer()
        return

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg import AsyncConnection
        from psycopg.rows import dict_row

        _async_pg_conn = await AsyncConnection.connect(
            settings.SUPABASE_DB_URL,
            autocommit=True,
            prepare_threshold=0,
            row_factory=dict_row,
            connect_timeout=15,
        )
        saver = AsyncPostgresSaver(_async_pg_conn)
        await saver.setup()
        _checkpointer = saver
        logger.info("[FlowIA] Checkpointer: AsyncPostgresSaver (Supabase)")
    except Exception as exc:
        logger.warning(
            "[FlowIA] Async PostgreSQL checkpointer unavailable (%s); using MemorySaver",
            exc,
        )
        _async_pg_conn = None
        _init_memory_checkpointer()


def init_checkpointer() -> None:
    """Sync init — MemorySaver only (tests/CI). Production uses init_checkpointer_async()."""
    global _checkpointer

    if _checkpointer is not None:
        return

    if _use_memory_backend():
        _init_memory_checkpointer()
        return

    logger.info(
        "[FlowIA] Checkpointer postgres deferred — await init_checkpointer_async() in lifespan"
    )


def get_checkpointer() -> Any:
    if _checkpointer is None:
        init_checkpointer()
    if _checkpointer is None:
        raise RuntimeError(
            "Checkpointer not initialized. Ensure app lifespan ran init_checkpointer_async()."
        )
    return _checkpointer


def get_compiled_engine() -> Any:
    """Return the compiled LangGraph engine (lazy, after checkpointer init)."""
    global _compiled_engine
    if _compiled_engine is None:
        from packages.engine.engine import compile_master_engine

        _compiled_engine = compile_master_engine(get_checkpointer())
    return _compiled_engine


async def shutdown_checkpointer_async() -> None:
    global _checkpointer, _async_pg_conn, _compiled_engine

    if _async_pg_conn is not None:
        try:
            await _async_pg_conn.close()
        except Exception:
            pass
    _async_pg_conn = None
    _checkpointer = None
    _compiled_engine = None


def shutdown_checkpointer() -> None:
    """Sync shutdown (tests). Async connections closed via shutdown_checkpointer_async()."""
    global _checkpointer, _async_pg_conn, _compiled_engine

    _async_pg_conn = None
    _checkpointer = None
    _compiled_engine = None


class MasterEngineProxy:
    """Lazy proxy so imports work before lifespan init (tests use MemorySaver fallback)."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_compiled_engine(), name)


master_engine = MasterEngineProxy()
