"""Booking input guardrails (fail-closed, lakehouse-style)."""
from __future__ import annotations

import re
import time
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from packages.scheduling.eligibility import (
    _SERVICE_SEARCH_SYNONYMS,
    list_catalog_services,
)

GENERIC_INVALID_MSG = "Entrada inválida para agendamento."

MAX_NAME_LEN = 80
MAX_SERVICE_QUERY_LEN = 100
MAX_PROFESSIONAL_LEN = 80
DEFAULT_MAX_ADVANCE_DAYS = 90

# Rate limits per sender_id (in-process TTL)
_RATE_BUCKETS: dict[str, list[float]] = defaultdict(list)
_RATE_LIMITS = {
    "check_availability": (20, 60),
    "book_time": (3, 3600),
}

_SQLISH_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r";"), "delimiter"),
    (re.compile(r"--"), "comment"),
    (re.compile(r"/\*|\*/"), "comment"),
    (re.compile(r"\bSELECT\b", re.I), "sql"),
    (re.compile(r"\bWHERE\b", re.I), "sql"),
    (re.compile(r"\bOR\b\s+['\"]?\s*1\s*=\s*1", re.I), "sql"),
    (re.compile(r"\bDROP\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b", re.I), "sql"),
    (re.compile(r"ignore\s+previous", re.I), "jailbreak"),
    (re.compile(r"\[SISTEMA\]|\[SYSTEM\]", re.I), "spoof"),
    (re.compile(r"^system\s*:", re.I | re.M), "spoof"),
)

_TRIVIAL_PHONES = frozenset(
    {"0000000000", "1111111111", "2222222222", "9999999999", "1234567890"}
)


def normalize_phone(phone: str) -> str:
    return "".join(filter(str.isdigit, phone))


def _normalize_key(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in folded if not unicodedata.combining(c))
    return " ".join(ascii_text.lower().split())


def sanitize_text_field(value: str | None, max_len: int) -> tuple[str | None, str | None]:
    if value is None:
        return None, "empty"
    cleaned = value.replace("\x00", " ").strip()
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return None, "empty"
    if len(cleaned) > max_len:
        return None, "too_long"
    reason = reject_sqlish_patterns(cleaned)
    if reason:
        return None, reason
    return cleaned, None


def reject_sqlish_patterns(text: str) -> str | None:
    for pattern, tag in _SQLISH_PATTERNS:
        if pattern.search(text):
            return tag
    if "%" in text or "_" in text:
        return "wildcard"
    return None


def mask_phone(phone: str) -> str:
    digits = normalize_phone(phone)
    if len(digits) <= 4:
        return "****"
    return f"{digits[:3]}****{digits[-4:]}"


def validate_phone(phone: str) -> tuple[str | None, str | None]:
    digits = normalize_phone(phone)
    if not digits or len(digits) < 10 or len(digits) > 13:
        return None, "phone_length"
    if digits in _TRIVIAL_PHONES or len(set(digits)) == 1:
        return None, "phone_trivial"
    sql_reason = reject_sqlish_patterns(phone)
    if sql_reason:
        return None, sql_reason
    return digits, None


_PT_MONTHS: dict[str, int] = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DMY_SLASH_RE = re.compile(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$")
_PT_DATE_RE = re.compile(r"^(\d{1,2})\s+de\s+(\w+)(?:\s+de\s+(\d{4}))?$")
_PT_DATE_IN_TEXT_RE = re.compile(
    r"\b(?:dia\s+)?(\d{1,2})\s+de\s+"
    r"(janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
    r"(?:\s+de\s+(\d{4}))?\b",
    re.I,
)
_ISO_DATE_IN_TEXT_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_DMY_IN_TEXT_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?\b")

# Longest aliases first (segunda feira before segunda).
_WEEKDAY_ALIASES: tuple[tuple[str, int], ...] = (
    ("domingo", 6),
    ("segunda feira", 0),
    ("segunda", 0),
    ("terca feira", 1),
    ("terca", 1),
    ("quarta feira", 2),
    ("quarta", 2),
    ("quinta feira", 3),
    ("quinta", 3),
    ("sexta feira", 4),
    ("sexta", 4),
    ("sabado", 5),
)


def _next_occurrence_of_weekday(weekday: int, reference: date) -> date:
    """Next calendar occurrence of weekday (0=Mon … 6=Sun); same day if reference matches."""
    days_ahead = (weekday - reference.weekday()) % 7
    return reference + timedelta(days=days_ahead)


def _parse_weekday_from_normalized(normalized: str, reference: date) -> str | None:
    for alias, weekday in _WEEKDAY_ALIASES:
        if re.search(rf"\b{re.escape(alias)}\b", normalized):
            return _next_occurrence_of_weekday(weekday, reference).isoformat()
    return None


def _infer_year(day: int, month: int, reference: date) -> int:
    candidate = date(reference.year, month, day)
    if candidate >= reference:
        return reference.year
    return reference.year + 1


def normalize_booking_date(
    date_str: str,
    reference: date | None = None,
) -> str | None:
    """Parse common PT/BR date strings into ISO YYYY-MM-DD."""
    cleaned, err = sanitize_text_field(date_str, 40)
    if err or not cleaned:
        return None

    ref = reference or date.today()
    normalized = _normalize_key(cleaned)

    if _ISO_DATE_RE.match(cleaned):
        return cleaned

    slash_match = _DMY_SLASH_RE.match(cleaned)
    if slash_match:
        day, month, year = (int(slash_match.group(i)) for i in (1, 2, 3))
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None

    pt_match = _PT_DATE_RE.match(normalized)
    if pt_match:
        day = int(pt_match.group(1))
        month = _PT_MONTHS.get(pt_match.group(2))
        if not month:
            return None
        year = int(pt_match.group(3)) if pt_match.group(3) else _infer_year(day, month, ref)
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None

    weekday_iso = _parse_weekday_from_normalized(normalized, ref)
    if weekday_iso:
        return weekday_iso

    return None


def _coerce_future_booking_date(
    parsed: date,
    reference: date,
    org_settings: dict[str, Any] | None,
) -> tuple[date | None, str | None]:
    """Remap month/day to a valid future date when LLM sends a stale year (e.g. 2024)."""
    for year in (reference.year, reference.year + 1):
        try:
            candidate = date(year, parsed.month, parsed.day)
        except ValueError:
            continue
        validated, err = validate_date(candidate.isoformat(), org_settings)
        if validated:
            return validated, None
    return None, "past_date"


def extract_booking_date_from_text(
    text: str,
    org_settings: dict[str, Any] | None = None,
    reference: date | None = None,
) -> str | None:
    """Best-effort date extraction from free-form PT booking messages."""
    if not text or not text.strip():
        return None

    ref = reference or date.today()
    normalized = _normalize_key(text)

    for iso_match in _ISO_DATE_IN_TEXT_RE.finditer(text):
        parsed, err = parse_booking_date(iso_match.group(1), org_settings, reference=ref)
        if parsed:
            return parsed.isoformat()

    for pt_match in _PT_DATE_IN_TEXT_RE.finditer(normalized):
        day = pt_match.group(1)
        month = pt_match.group(2)
        year = pt_match.group(3)
        fragment = f"{day} de {month}" + (f" de {year}" if year else "")
        parsed, err = parse_booking_date(fragment, org_settings, reference=ref)
        if parsed:
            return parsed.isoformat()

    for slash_match in _DMY_IN_TEXT_RE.finditer(text):
        day, month, year = slash_match.group(1), slash_match.group(2), slash_match.group(3)
        fragment = f"{day}/{month}/{year}" if year else f"{day}/{month}/{ref.year}"
        parsed, err = parse_booking_date(fragment, org_settings, reference=ref)
        if parsed:
            return parsed.isoformat()

    weekday_iso = _parse_weekday_from_normalized(normalized, ref)
    if weekday_iso:
        parsed, err = parse_booking_date(weekday_iso, org_settings, reference=ref)
        if parsed:
            return parsed.isoformat()

    return None


def parse_booking_date(
    date_str: str,
    org_settings: dict[str, Any] | None = None,
    reference: date | None = None,
) -> tuple[date | None, str | None]:
    """Normalize colloquial dates, then validate scheduling window."""
    ref = reference or date.today()
    iso = normalize_booking_date(date_str, reference=ref)
    if iso:
        try:
            parsed = datetime.strptime(iso, "%Y-%m-%d").date()
        except ValueError:
            return None, "date_format"
        validated, err = validate_date(iso, org_settings)
        if validated:
            return validated, None
        if err == "past_date" and parsed.year < ref.year - 1:
            coerced, coerce_err = _coerce_future_booking_date(parsed, ref, org_settings)
            if coerced:
                return coerced, None
            return None, coerce_err or err
        return None, err
    return validate_date(date_str, org_settings)


def _scheduling_settings(org_settings: dict[str, Any] | None) -> dict[str, Any]:
    scheduling = (org_settings or {}).get("scheduling") or {}
    return {
        "max_advance_days": int(scheduling.get("max_advance_days") or DEFAULT_MAX_ADVANCE_DAYS),
        "min_notice_hours": int(scheduling.get("min_notice_hours") or 0),
    }


def validate_date(date_str: str, org_settings: dict[str, Any] | None = None) -> tuple[date | None, str | None]:
    cleaned, err = sanitize_text_field(date_str, 10)
    if err or not cleaned:
        return None, err or "empty"
    try:
        parsed = datetime.strptime(cleaned, "%Y-%m-%d").date()
    except ValueError:
        return None, "date_format"
    cfg = _scheduling_settings(org_settings)
    today = date.today()
    if parsed < today:
        return None, "past_date"
    if parsed > today + timedelta(days=cfg["max_advance_days"]):
        return None, "too_far"
    return parsed, None


def validate_datetime(
    dt_str: str,
    org_settings: dict[str, Any] | None = None,
) -> tuple[datetime | None, str | None]:
    cleaned, err = sanitize_text_field(dt_str, 32)
    if err or not cleaned:
        return None, err or "empty"
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        return None, "datetime_format"
    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)
    date_ok, date_err = validate_date(parsed.date().isoformat(), org_settings)
    if date_err:
        return None, date_err
    cfg = _scheduling_settings(org_settings)
    if cfg["min_notice_hours"] > 0 and parsed < datetime.now() + timedelta(hours=cfg["min_notice_hours"]):
        return None, "min_notice"
    return parsed, None


def resolve_service_from_catalog(
    org_id: str,
    query: str,
    catalog: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Catalog-only service resolution (no user-controlled ILIKE wildcards)."""
    cleaned, err = sanitize_text_field(query, MAX_SERVICE_QUERY_LEN)
    if err or not cleaned:
        return None, err or "empty"

    rows = catalog if catalog is not None else list_catalog_services(org_id)
    if not rows:
        return None, "no_catalog"

    norm_query = _normalize_key(cleaned)

    exact = [r for r in rows if _normalize_key(r["name"]) == norm_query]
    if len(exact) == 1:
        return exact[0], None
    if len(exact) > 1:
        return None, "ambiguous"

    lowered = cleaned.lower()
    for synonym, target in _SERVICE_SEARCH_SYNONYMS.items():
        if synonym in lowered:
            target_norm = _normalize_key(target)
            syn_matches = [r for r in rows if target_norm in _normalize_key(r["name"])]
            if len(syn_matches) == 1:
                return syn_matches[0], None
            if len(syn_matches) > 1:
                return None, "ambiguous"

    partial = [r for r in rows if norm_query in _normalize_key(r["name"])]
    if len(partial) == 1:
        return partial[0], None
    if len(partial) > 1:
        return None, "ambiguous"

    return None, "not_found"


def validate_professional_name(
    name: str | None,
    eligible: list[dict[str, str]],
) -> tuple[list[dict[str, str]], str | None]:
    if not name or not name.strip():
        return eligible, None
    cleaned, err = sanitize_text_field(name, MAX_PROFESSIONAL_LEN)
    if err or not cleaned:
        return [], err or "empty"
    needle = cleaned.lower()
    matched = [p for p in eligible if needle in p["name"].lower()]
    if not matched:
        return [], "not_found"
    return matched, None


def check_rate_limit(sender_key: str, action: str) -> tuple[bool, str | None]:
    if not sender_key:
        return True, None
    limit, window = _RATE_LIMITS.get(action, (999, 60))
    now = time.time()
    key = f"{sender_key}:{action}"
    bucket = [t for t in _RATE_BUCKETS[key] if now - t < window]
    if len(bucket) >= limit:
        _RATE_BUCKETS[key] = bucket
        return False, "rate_limit"
    bucket.append(now)
    _RATE_BUCKETS[key] = bucket
    return True, None


def reset_rate_limits_for_tests() -> None:
    _RATE_BUCKETS.clear()


def resolve_booking_phone(
    patient_phone: str,
    config: dict[str, Any],
) -> tuple[str | None, str | None]:
    """WhatsApp channel: bind to sender_phone when provided."""
    phone, err = validate_phone(patient_phone)
    if err:
        return None, err

    channel = config.get("channel")
    sender_phone = config.get("sender_phone")
    if channel == "whatsapp" and sender_phone:
        bound, bound_err = validate_phone(sender_phone)
        if bound_err:
            return None, bound_err
        if phone != bound:
            return bound, "phone_overridden"
    return phone, None
