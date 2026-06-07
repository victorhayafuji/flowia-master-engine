"""LangGraph checkpointer — PostgreSQL (Supabase) with MemorySaver fallback."""
from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

_checkpointer: Any = None
_pg_conn: Any = None
_compiled_engine: Any = None


def init_checkpointer() -> None:
    """Initialize checkpointer once at app startup."""
    global _checkpointer, _pg_conn

    if _checkpointer is not None:
        return

    from packages.auth_core.config import settings

    if settings.CHECKPOINTER_BACKEND == "memory":
        _checkpointer = MemorySaver()
        logger.info("[FlowIA] Checkpointer: MemorySaver (config)")
        return

    if settings.CHECKPOINTER_BACKEND not in ("auto", "postgres"):
        _checkpointer = MemorySaver()
        logger.info("[FlowIA] Checkpointer: MemorySaver (unknown backend)")
        return

    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg import Connection
        from psycopg.rows import dict_row

        _pg_conn = Connection.connect(
            settings.SUPABASE_DB_URL,
            autocommit=True,
            prepare_threshold=0,
            row_factory=dict_row,
        )
        saver = PostgresSaver(_pg_conn)
        saver.setup()
        _checkpointer = saver
        logger.info("[FlowIA] Checkpointer: PostgreSQL (Supabase)")
    except Exception as exc:
        logger.warning(
            "[FlowIA] PostgreSQL checkpointer unavailable (%s); using MemorySaver",
            exc,
        )
        _checkpointer = MemorySaver()


def get_checkpointer() -> Any:
    if _checkpointer is None:
        init_checkpointer()
    return _checkpointer


def get_compiled_engine() -> Any:
    """Return the compiled LangGraph engine (lazy, after checkpointer init)."""
    global _compiled_engine
    if _compiled_engine is None:
        from packages.engine.engine import compile_master_engine

        _compiled_engine = compile_master_engine(get_checkpointer())
    return _compiled_engine


def shutdown_checkpointer() -> None:
    global _checkpointer, _pg_conn, _compiled_engine
    if _pg_conn is not None:
        try:
            _pg_conn.close()
        except Exception:
            pass
    _pg_conn = None
    _checkpointer = None
    _compiled_engine = None


class MasterEngineProxy:
    """Lazy proxy so imports work before lifespan init (tests use MemorySaver fallback)."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_compiled_engine(), name)


master_engine = MasterEngineProxy()
