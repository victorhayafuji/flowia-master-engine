"""User message assessment and formatting for agent perimeter."""
from __future__ import annotations

import re
from enum import Enum

from packages.scheduling.guardrails import reject_sqlish_patterns

MAX_USER_MESSAGE_LEN = 2000

_BLOCKED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.I),
    re.compile(r"you\s+are\s+now\s+", re.I),
    re.compile(r"reveal\s+(your\s+)?(system\s+)?prompt", re.I),
    re.compile(r"<\s*script", re.I),
)

_SUSPICIOUS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"act\s+as\s+", re.I),
    re.compile(r"developer\s+mode", re.I),
    re.compile(r"jailbreak", re.I),
)

BLOCKED_USER_RESPONSE = (
    "Desculpe, não consegui processar essa mensagem. "
    "Como posso ajudar com serviços ou agendamento do salão?"
)


class MessageVerdict(str, Enum):
    ALLOWED = "allowed"
    SUSPICIOUS = "suspicious"
    BLOCKED = "blocked"


def assess_user_message(text: str) -> MessageVerdict:
    if not text or not text.strip():
        return MessageVerdict.BLOCKED

    if len(text) > MAX_USER_MESSAGE_LEN:
        return MessageVerdict.BLOCKED

    if "\x00" in text:
        return MessageVerdict.BLOCKED

    sql_tag = reject_sqlish_patterns(text)
    if sql_tag in ("delimiter", "comment", "sql"):
        return MessageVerdict.BLOCKED

    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(text):
            return MessageVerdict.BLOCKED

    for pattern in _SUSPICIOUS_PATTERNS:
        if pattern.search(text):
            return MessageVerdict.SUSPICIOUS

    if sql_tag in ("jailbreak", "spoof", "wildcard"):
        return MessageVerdict.SUSPICIOUS

    return MessageVerdict.ALLOWED


def format_user_message_for_agent(text: str) -> str:
    cleaned = text.strip()
    return f"[MENSAGEM DO CLIENTE]\n{cleaned}\n[FIM]"
