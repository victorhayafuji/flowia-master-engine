import re
from datetime import date, timedelta

from packages.scheduling.date_parsing.calendar import _add_business_days, _infer_year, _next_occurrence_of_weekday
from packages.scheduling.date_parsing.helpers import (
    _clarification,
    _is_plain_weekday_alias,
    _relative_phrase_matches,
    _resolved,
)
from packages.scheduling.date_parsing.normalize import format_date_label_pt, normalize_key
from packages.scheduling.date_parsing.types import (
    _DIA_N_RE,
    _OFFSET_BUSINESS_DAYS_RE,
    _OFFSET_DAYS_RE,
    _OFFSET_WEEKS_RE,
    _PT_MONTHS,
    _WEEKDAY_ALIASES,
    DateParseMode,
    DateResolution,
)


def _parse_date_alternatives(
    normalized: str,
    reference: date,
    mode: DateParseMode,
) -> DateResolution | None:
    """Clarify when client mixes relative + plain weekday (e.g. amanhã ou sexta)."""
    if mode != DateParseMode.BOOKING:
        return None

    relatives = _relative_phrase_matches(normalized, reference)
    weekday_alts: list[tuple[str, str]] = []
    weekday_spans: list[tuple[int, int]] = []

    for alias, weekday in _WEEKDAY_ALIASES:
        if not _is_plain_weekday_alias(normalized, alias):
            continue
        for match in re.finditer(rf"\b{re.escape(alias)}\b", normalized):
            span = match.span()
            if any(not (span[1] <= start or span[0] >= end) for start, end in weekday_spans):
                continue
            iso = _next_occurrence_of_weekday(weekday, reference).isoformat()
            weekday_alts.append((alias, iso))
            weekday_spans.append(span)

    if not relatives or not weekday_alts:
        return None

    alternatives = [(phrase, iso) for phrase, iso, _ in relatives] + weekday_alts
    unique_isos = {iso for _, iso in alternatives}
    if len(unique_isos) >= 2:
        seen_iso: set[str] = set()
        option_parts: list[str] = []
        for phrase, iso in alternatives:
            if iso in seen_iso:
                continue
            seen_iso.add(iso)
            option_parts.append(f"{phrase} ({format_date_label_pt(iso)})")
        options = " ou ".join(option_parts)
        return _clarification("multiple_dates", alternatives[0][0], options=options)

    phrase, iso = alternatives[0]
    return _resolved(iso, "date_alternatives_same", phrase)


def _parse_relative(
    normalized: str,
    reference: date,
    mode: DateParseMode,
) -> DateResolution | None:
    matches = _relative_phrase_matches(normalized, reference)
    if not matches:
        return None
    unique_isos = {iso for _, iso, _ in matches}
    if mode == DateParseMode.BOOKING and len(unique_isos) >= 2:
        options = " ou ".join(
            f"{phrase} ({format_date_label_pt(iso)})" for phrase, iso, _ in matches
        )
        return _clarification("multiple_dates", matches[0][0], options=options)
    phrase, iso, day_offset = matches[0]
    return _resolved(iso, "relative", phrase, day_offset)


def _parse_numeric_offset(normalized: str, reference: date) -> DateResolution | None:
    business_match = _OFFSET_BUSINESS_DAYS_RE.search(normalized)
    if business_match:
        days = int(business_match.group(1))
        target = _add_business_days(reference, days)
        return _resolved(target.isoformat(), "offset_business", business_match.group(0), days)

    week_match = _OFFSET_WEEKS_RE.search(normalized)
    if week_match:
        weeks = int(week_match.group(1))
        target = reference + timedelta(weeks=weeks)
        return _resolved(target.isoformat(), "offset", week_match.group(0), weeks * 7)

    day_match = _OFFSET_DAYS_RE.search(normalized)
    if day_match:
        days = int(day_match.group(1))
        target = reference + timedelta(days=days)
        return _resolved(target.isoformat(), "offset", day_match.group(0), days)
    return None


def _parse_dia_n(normalized: str, reference: date, mode: DateParseMode) -> DateResolution | None:
    match = _DIA_N_RE.search(normalized)
    if not match:
        return None
    day = int(match.group(1))
    month_name = match.group(2)
    year_str = match.group(3)
    if month_name:
        month = _PT_MONTHS.get(normalize_key(month_name))
        if not month:
            return None
        year = int(year_str) if year_str else _infer_year(day, month, reference)
        try:
            iso = date(year, month, day).isoformat()
        except ValueError:
            return None
        return _resolved(iso, "absolute", match.group(0))
    if mode == DateParseMode.BOOKING:
        if day >= reference.day:
            month, year = reference.month, reference.year
        else:
            month = reference.month + 1
            year = reference.year
            if month > 12:
                month, year = 1, year + 1
        try:
            iso = date(year, month, day).isoformat()
        except ValueError:
            return _clarification("day_without_month", match.group(0), day=str(day))
        return _resolved(iso, "absolute", match.group(0))
    return _clarification("day_without_month", match.group(0), day=str(day))
