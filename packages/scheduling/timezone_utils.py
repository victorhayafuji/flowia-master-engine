"""Timezone helpers for salon scheduling (org-local wall clock ↔ UTC storage)."""
from __future__ import annotations

import re
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "America/Sao_Paulo"
_TZ_SUFFIX_RE = re.compile(r"[+-]\d{2}:\d{2}$")
_TIME_HHMM_RE = re.compile(r"\b(\d{1,2}):(\d{2})\b")
_TIME_AS_RE = re.compile(r"\b(?:as|às)\s*(\d{1,2})(?::(\d{2}))?\b", re.I)
_TIME_H_RE = re.compile(r"\b(\d{1,2})h(\d{2})?\b", re.I)


def resolve_zone(tzname: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tzname or DEFAULT_TIMEZONE)
    except Exception:
        return ZoneInfo(DEFAULT_TIMEZONE)


def normalize_to_utc(dt: datetime, tzname: str | None = None) -> datetime:
    """Naive datetimes are interpreted as org-local wall clock."""
    zone = resolve_zone(tzname)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=zone).astimezone(timezone.utc)
    return dt.astimezone(timezone.utc)


def to_local_naive(dt: datetime, tzname: str | None = None) -> datetime:
    """Convert stored instant to naive local datetime for slot math."""
    zone = resolve_zone(tzname)
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(zone).replace(tzinfo=None)


def storage_iso(dt_utc: datetime) -> str:
    """Serialize UTC instant for timestamptz columns (Z suffix)."""
    return dt_utc.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def local_day_utc_bounds(target_date: date, tzname: str | None = None) -> tuple[str, str]:
    """Inclusive org-calendar day range as UTC ISO strings for DB filters."""
    zone = resolve_zone(tzname)
    start = datetime.combine(target_date, time.min, tzinfo=zone).astimezone(timezone.utc)
    end = datetime.combine(target_date, time.max, tzinfo=zone).astimezone(timezone.utc)
    return storage_iso(start), storage_iso(end)


def local_date_range_utc_bounds(start_date: date, end_date: date, tzname: str | None = None) -> tuple[str, str]:
    start_iso, _ = local_day_utc_bounds(start_date, tzname)
    _, end_iso = local_day_utc_bounds(end_date, tzname)
    return start_iso, end_iso


def now_local_naive(tzname: str | None = None) -> datetime:
    return datetime.now(resolve_zone(tzname)).replace(tzinfo=None)


def strip_timezone_suffix(dt_str: str) -> str:
    """Agent inputs must be org-local wall clock — drop accidental Z/offsets."""
    cleaned = dt_str.strip()
    if cleaned.endswith("Z") or cleaned.endswith("z"):
        cleaned = cleaned[:-1]
    cleaned = _TZ_SUFFIX_RE.sub("", cleaned)
    return cleaned


def parse_booking_datetime(
    dt_str: str,
    tzname: str | None = None,
    *,
    assume_local_wall_clock: bool = True,
) -> tuple[datetime | None, datetime | None, str | None]:
    """Parse booking datetime → (local_naive, utc_aware, error)."""
    cleaned = strip_timezone_suffix(dt_str) if assume_local_wall_clock else dt_str.strip()
    try:
        local_naive = datetime.fromisoformat(cleaned)
    except ValueError:
        return None, None, "datetime_format"

    if not assume_local_wall_clock and local_naive.tzinfo is not None:
        utc = local_naive.astimezone(timezone.utc)
        return to_local_naive(utc, tzname), utc, None

    if local_naive.tzinfo is not None:
        local_naive = local_naive.replace(tzinfo=None)

    utc = normalize_to_utc(local_naive, tzname)
    return local_naive, utc, None


def build_local_datetime(date_iso: str, time_hhmm: str) -> str:
    hour, minute = time_hhmm.split(":")
    return f"{date_iso}T{int(hour):02d}:{int(minute):02d}:00"


def format_local_datetime_label(local_naive: datetime, tzname: str | None = None) -> str:
    zone = resolve_zone(tzname)
    label = DEFAULT_TIMEZONE if str(zone) == DEFAULT_TIMEZONE else str(zone)
    return f"{local_naive.strftime('%d/%m/%Y %H:%M')} ({label})"


def extract_booking_time_from_text(text: str) -> str | None:
    """Extract HH:MM from PT booking phrases (11:00, às 11, 11h30)."""
    if not text:
        return None
    normalized = text.lower().strip()

    for pattern in (_TIME_AS_RE, _TIME_HHMM_RE, _TIME_H_RE):
        match = pattern.search(normalized)
        if not match:
            continue
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    return None
