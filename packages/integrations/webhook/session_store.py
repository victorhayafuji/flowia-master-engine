"""Persist WhatsApp/chat session state (handoff) on patients."""
from __future__ import annotations

import time
from collections import defaultdict

_HANDOFF_AT: dict[str, float] = {}
_RESUME_ATTEMPTS: dict[str, list[float]] = defaultdict(list)

HANDOFF_COOLDOWN_SECONDS = 86400  # 24h
RESUME_MIN_WAIT_SECONDS = 300  # 5 min after handoff
RESUME_MAX_PER_HOUR = 3


def update_session_state(sender_id: str, data: dict) -> bool:
    from apps.salon.domain.clients.repository import PatientRepository

    reason = data.get("handoff_reason") or data.get("reason")
    ok = PatientRepository().upsert_handoff_by_sender(sender_id, reason=reason)
    if ok:
        record_handoff(sender_id)
    return ok


def record_handoff(sender_id: str) -> None:
    _HANDOFF_AT[sender_id] = time.time()


def can_request_handoff(sender_id: str) -> tuple[bool, str | None]:
    last = _HANDOFF_AT.get(sender_id)
    if last is None:
        return True, None
    elapsed = time.time() - last
    if elapsed < HANDOFF_COOLDOWN_SECONDS:
        return False, "cooldown"
    return True, None


def can_resume_ai(sender_id: str) -> tuple[bool, str | None]:
    last = _HANDOFF_AT.get(sender_id)
    if last is None:
        return False, "no_handoff"

    elapsed = time.time() - last
    if elapsed < RESUME_MIN_WAIT_SECONDS:
        return False, "too_soon"

    now = time.time()
    attempts = [t for t in _RESUME_ATTEMPTS[sender_id] if now - t < 3600]
    _RESUME_ATTEMPTS[sender_id] = attempts
    if len(attempts) >= RESUME_MAX_PER_HOUR:
        return False, "rate_limit"

    attempts.append(now)
    _RESUME_ATTEMPTS[sender_id] = attempts
    return True, None


def clear_handoff_session(sender_id: str) -> None:
    _HANDOFF_AT.pop(sender_id, None)


def reset_session_store_for_tests() -> None:
    _HANDOFF_AT.clear()
    _RESUME_ATTEMPTS.clear()
