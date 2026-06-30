"""In-memory outer-flow state for a totem (kiosk) attendance.

Mirrors ``packages/scheduling/guided_session_store.py``: process-local, lost on
restart, not shared across replicas (acceptable for the single-instance pilot —
see CLAUDE.md §20; move to a shared store before scale > 1 replica).

This holds the *outer* totem flow (identify → consent → menu → booking/FAQ). The
booking sub-flow keeps its own state in ``guided_session_store``, keyed by the
booking thread ``{org_id}:{phone}``. Keyed here by an opaque ``session_id`` so a
customer's phone never travels in the client-facing handle.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

# Short idle window: a public device must not keep a customer's data around.
SESSION_TTL_SECONDS = 180  # 3 min idle → discarded (front-end also resets to attract)

PHASE_IDENTIFY = "identify"
PHASE_CONSENT = "consent"
PHASE_MENU = "menu"
PHASE_BOOKING = "booking"
PHASE_FAQ = "faq"
PHASE_DONE = "done"


@dataclass
class TotemSession:
    org_id: str
    phase: str = PHASE_IDENTIFY
    name: str | None = None
    phone: str | None = None
    patient_id: str | None = None
    booking_thread_id: str | None = None  # {org_id}:{phone} — booking + consent identity
    updated_at: float = field(default_factory=time.time)


_SESSIONS: dict[str, TotemSession] = {}


def _expired(session: TotemSession) -> bool:
    return (time.time() - session.updated_at) > SESSION_TTL_SECONDS


def get_session(session_id: str) -> TotemSession | None:
    session = _SESSIONS.get(session_id)
    if session and _expired(session):
        _SESSIONS.pop(session_id, None)
        return None
    return session


def set_session(session_id: str, session: TotemSession) -> None:
    session.updated_at = time.time()
    _SESSIONS[session_id] = session


def clear_session(session_id: str) -> None:
    _SESSIONS.pop(session_id, None)


def reset_for_tests() -> None:
    _SESSIONS.clear()
