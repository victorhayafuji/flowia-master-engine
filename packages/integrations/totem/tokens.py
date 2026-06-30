"""Kiosk device token helpers.

A device token is a high-entropy secret shown to the operator exactly once at
provisioning time. We persist only its SHA-256 hash, so a database leak never
exposes a usable token. SHA-256 (unsalted) is appropriate here — unlike a
low-entropy password, the token is random and must be looked up by hash, which
a salted scheme (bcrypt) cannot do efficiently.
"""
from __future__ import annotations

import hashlib
import secrets

# Visible prefix so a token is recognizable in logs/support without revealing it.
_TOKEN_PREFIX = "kdev_"


def generate_device_token() -> str:
    """Return a fresh, URL-safe device token (shown to the operator once)."""
    return _TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_device_token(token: str) -> str:
    """Deterministic hash for indexed lookup. Empty/whitespace → empty string."""
    cleaned = (token or "").strip()
    if not cleaned:
        return ""
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
