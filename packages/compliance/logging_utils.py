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


def mask_email(email: str | None) -> str:
    """Mask an email for logs — keep first char + domain (j***@domain.com)."""
    if not email:
        return "?"
    local, sep, domain = email.partition("@")
    if not sep:
        return "***"
    head = local[0] if local else ""
    return f"{head}***@{domain}"


def mask_thread_id(thread_id: str | None) -> str:
    """Mask a conversation thread id ({org_id}:{sender}) — keep org, mask sender."""
    if not thread_id:
        return "?"
    org, sep, sender = thread_id.partition(":")
    if not sep:
        return org
    return f"{org}:{mask_sender_id(sender)}"
