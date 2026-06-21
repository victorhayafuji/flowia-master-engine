"""In-memory per-thread state for the guided booking flow (channel-agnostic).

Mirrors ``packages/integrations/webhook/session_store.py``: process-local and lost
on restart — acceptable for short-lived guided booking sessions (MVP). Not shared
across replicas; move to a shared store before scale>1 (see CLAUDE.md §20).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

SESSION_TTL_SECONDS = 1800  # 30 min idle → session discarded

# Flow steps, in order. The client is resolved before the flow (by phone on
# WhatsApp, by the test-page selector on the dev chat) — never asked in-chat.
STEP_PATIENT_CAPTURE = "patient_capture"  # onboarding: typed name (+ phone on web)
STEP_SERVICE = "service"
STEP_PROFESSIONAL = "professional"
STEP_DATE = "date"
STEP_SLOT = "slot"
STEP_CONFIRM = "confirm"
STEP_POST = "post"  # after a successful booking: [Agendar outro] [Encerrar]
STEP_DONE = "done"


@dataclass
class GuidedSession:
    org_id: str
    step: str = STEP_SERVICE
    channel: str = "chat_test"  # chat_test | whatsapp → appointment source
    tzname: str | None = None  # org timezone, resolved once at session start
    # Customer resolution.
    patient_id: str | None = None  # set once the client is resolved
    patient_phone: str | None = None  # known phone (WhatsApp sender) or captured
    needs_phone: bool = False  # capture must also ask the phone (web "not registered")
    # Booking selections.
    service_id: str | None = None
    service_name: str | None = None
    service_duration: int | None = None
    service_price: float | None = None
    professional_id: str | None = None
    professional_name: str | None = None
    date: str | None = None  # YYYY-MM-DD
    slot: str | None = None  # full ISO datetime (as returned by get_available_slots)
    updated_at: float = field(default_factory=time.time)


_SESSIONS: dict[str, GuidedSession] = {}


def _expired(session: GuidedSession) -> bool:
    return (time.time() - session.updated_at) > SESSION_TTL_SECONDS


def get_session(thread_id: str) -> GuidedSession | None:
    session = _SESSIONS.get(thread_id)
    if session and _expired(session):
        _SESSIONS.pop(thread_id, None)
        return None
    return session


def set_session(thread_id: str, session: GuidedSession) -> None:
    session.updated_at = time.time()
    _SESSIONS[thread_id] = session


def clear_session(thread_id: str) -> None:
    _SESSIONS.pop(thread_id, None)


def has_active_session(thread_id: str) -> bool:
    return get_session(thread_id) is not None
