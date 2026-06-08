"""LGPD logging helpers."""

from __future__ import annotations


def mask_sender_id(sender_id: str | None) -> str:
    """Mask WhatsApp sender for logs — last 4 digits only."""
    if not sender_id:
        return "?"
    digits = "".join(c for c in sender_id if c.isdigit())
    if len(digits) >= 4:
        return f"***{digits[-4:]}"
    if len(sender_id) >= 4:
        return f"***{sender_id[-4:]}"
    return "***"
