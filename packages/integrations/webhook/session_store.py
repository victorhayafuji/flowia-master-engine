"""Persist WhatsApp/chat session state (handoff) on patients."""
from __future__ import annotations

import time
from collections import defaultdict

from packages.auth_core.conversation_thread import build_thread_id
from packages.auth_core.tenant import get_current_org_id

_HANDOFF_AT: dict[str, float] = {}
_RESUME_ATTEMPTS: dict[str, list[float]] = defaultdict(list)

HANDOFF_COOLDOWN_SECONDS = 86400  # 24h
RESUME_MIN_WAIT_SECONDS = 300  # 5 min after handoff
RESUME_MAX_PER_HOUR = 3
RESUME_WINDOW_SECONDS = 3600  # 1h sliding window for resume attempts


def _session_key(org_id: str | None, sender_id: str) -> str:
    oid = org_id or get_current_org_id()
    if oid and oid != "ALL":
        return build_thread_id(oid, sender_id)
    return sender_id


def update_session_state(sender_id: str, data: dict, org_id: str | None = None) -> bool:
    from apps.salon.domain.clients.repository import PatientRepository

    reason = data.get("handoff_reason") or data.get("reason")
    ok = PatientRepository().upsert_handoff_by_sender(sender_id, reason=reason)
    if ok:
        record_handoff(sender_id, org_id=org_id)
    return ok


def record_handoff(sender_id: str, org_id: str | None = None) -> None:
    _HANDOFF_AT[_session_key(org_id, sender_id)] = time.time()


def can_request_handoff(sender_id: str, org_id: str | None = None) -> tuple[bool, str | None]:
    last = _HANDOFF_AT.get(_session_key(org_id, sender_id))
    if last is None:
        return True, None
    elapsed = time.time() - last
    if elapsed < HANDOFF_COOLDOWN_SECONDS:
        return False, "cooldown"
    return True, None


def can_resume_ai(sender_id: str, org_id: str | None = None) -> tuple[bool, str | None]:
    key = _session_key(org_id, sender_id)
    last = _HANDOFF_AT.get(key)
    if last is None:
        return False, "no_handoff"

    elapsed = time.time() - last
    if elapsed < RESUME_MIN_WAIT_SECONDS:
        return False, "too_soon"

    now = time.time()
    attempts = [t for t in _RESUME_ATTEMPTS[key] if now - t < RESUME_WINDOW_SECONDS]
    _RESUME_ATTEMPTS[key] = attempts
    if len(attempts) >= RESUME_MAX_PER_HOUR:
        return False, "rate_limit"

    attempts.append(now)
    _RESUME_ATTEMPTS[key] = attempts
    return True, None


def clear_handoff_session(sender_id: str, org_id: str | None = None) -> None:
    _HANDOFF_AT.pop(_session_key(org_id, sender_id), None)


def reset_session_store_for_tests() -> None:
    _HANDOFF_AT.clear()
    _RESUME_ATTEMPTS.clear()
