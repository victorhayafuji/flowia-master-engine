from datetime import date
from typing import Any

from packages.scheduling.date_parsing.calendar import _infer_year
from packages.scheduling.date_parsing.helpers import _accept_resolution, _log_resolution, _resolved
from packages.scheduling.date_parsing.normalize import _is_currency_dmy_match, normalize_key
from packages.scheduling.date_parsing.relative import (
    _parse_date_alternatives,
    _parse_dia_n,
    _parse_numeric_offset,
    _parse_relative,
)
from packages.scheduling.date_parsing.types import (
    _DMY_IN_TEXT_RE,
    _DMY_SLASH_RE,
    _ISO_DATE_IN_TEXT_RE,
    _ISO_DATE_RE,
    _PT_DATE_IN_TEXT_RE,
    _PT_DATE_RE,
    _PT_MONTHS,
    DateParseMode,
    DateResolution,
)
from packages.scheduling.date_parsing.weekday import (
    _parse_neste_weekday,
    _parse_week_hint_only,
    _parse_week_phrases,
    _parse_week_with_weekday,
    _parse_weekday_compound,
    _parse_weekday_this_or_next_alternatives,
    _parse_weekend_phrases,
)


def normalize_booking_date(
    date_str: str,
    reference: date | None = None,
) -> str | None:
    if not date_str or not date_str.strip():
        return None
    ref = reference or date.today()
    cleaned = date_str.replace("\x00", " ").strip()
    cleaned = " ".join(cleaned.split())
    if not cleaned or len(cleaned) > 40:
        return None
    normalized = normalize_key(cleaned)
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
        month = _PT_MONTHS.get(normalize_key(pt_match.group(2)))
        if not month:
            return None
        year = int(pt_match.group(3)) if pt_match.group(3) else _infer_year(day, month, ref)
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None
    resolution = resolve_date_from_text(cleaned, reference=ref, mode=DateParseMode.REFERENCE)
    return resolution.iso if resolution else None


def resolve_date_detailed(
    text: str,
    *,
    reference: date | None = None,
    mode: DateParseMode = DateParseMode.BOOKING,
    org_settings: dict[str, Any] | None = None,
) -> DateResolution | None:
    del org_settings
    if not text or not text.strip():
        return None

    ref = reference or date.today()
    normalized = normalize_key(text)

    for iso_match in _ISO_DATE_IN_TEXT_RE.finditer(text):
        resolution = _resolved(iso_match.group(1), "absolute", iso_match.group(1))
        accepted = _accept_resolution(resolution, reference=ref, mode=mode)
        if accepted:
            _log_resolution(text, accepted)
            return accepted

    for pt_match in _PT_DATE_IN_TEXT_RE.finditer(normalized):
        day, month, year_part = pt_match.group(1), pt_match.group(2), pt_match.group(3)
        fragment = f"{day} de {month}" + (f" de {year_part}" if year_part else "")
        iso = normalize_booking_date(fragment, reference=ref)
        if iso:
            resolution = _resolved(iso, "absolute", fragment)
            accepted = _accept_resolution(resolution, reference=ref, mode=mode)
            if accepted:
                _log_resolution(text, accepted)
                return accepted

    dia_res = _parse_dia_n(normalized, ref, mode)
    if dia_res:
        if dia_res.needs_clarification:
            _log_resolution(text, dia_res)
            return dia_res
        accepted = _accept_resolution(dia_res, reference=ref, mode=mode)
        if accepted:
            _log_resolution(text, accepted)
            return accepted

    for slash_match in _DMY_IN_TEXT_RE.finditer(text):
        if _is_currency_dmy_match(text, slash_match.start(), slash_match.end()):
            continue
        day, month, year = slash_match.group(1), slash_match.group(2), slash_match.group(3)
        fragment = f"{day}/{month}/{year}" if year else f"{day}/{month}/{ref.year}"
        iso = normalize_booking_date(fragment, reference=ref)
        if iso:
            resolution = _resolved(iso, "absolute", fragment)
            accepted = _accept_resolution(resolution, reference=ref, mode=mode)
            if accepted:
                _log_resolution(text, accepted)
                return accepted

    parsers: tuple[Any, ...] = (
        _parse_week_hint_only,
        _parse_numeric_offset,
        _parse_weekday_this_or_next_alternatives,
        _parse_week_with_weekday,
        _parse_week_phrases,
        _parse_neste_weekday,
        _parse_weekend_phrases,
        _parse_date_alternatives,
        _parse_weekday_compound,
        _parse_relative,
    )
    for parser in parsers:
        if parser in (
            _parse_week_phrases,
            _parse_weekday_compound,
            _parse_week_with_weekday,
            _parse_neste_weekday,
            _parse_week_hint_only,
            _parse_weekday_this_or_next_alternatives,
            _parse_date_alternatives,
            _parse_relative,
        ):
            resolution = parser(normalized, ref, mode)
        elif parser is _parse_weekend_phrases:
            resolution = parser(normalized, ref)
        else:
            resolution = parser(normalized, ref)
        if resolution:
            if resolution.needs_clarification:
                _log_resolution(text, resolution)
                return resolution
            accepted = _accept_resolution(resolution, reference=ref, mode=mode)
            if accepted:
                _log_resolution(text, accepted)
                return accepted

    _log_resolution(text, None)
    return None


def resolve_date_from_text(
    text: str,
    *,
    reference: date | None = None,
    mode: DateParseMode = DateParseMode.BOOKING,
    org_settings: dict[str, Any] | None = None,
) -> DateResolution | None:
    """Resolve date; returns None when ambiguous (needs_clarification)."""
    detailed = resolve_date_detailed(
        text,
        reference=reference,
        mode=mode,
        org_settings=org_settings,
    )
    if detailed is None or detailed.needs_clarification or not detailed.iso:
        return None
    return detailed


def extract_booking_date_from_text(
    text: str,
    org_settings: dict[str, Any] | None = None,
    reference: date | None = None,
) -> str | None:
    detailed = resolve_date_detailed(
        text,
        reference=reference,
        mode=DateParseMode.BOOKING,
        org_settings=org_settings,
    )
    if detailed and not detailed.needs_clarification and detailed.iso:
        return detailed.iso
    return None


def extract_reference_date_from_text(
    text: str,
    org_settings: dict[str, Any] | None = None,
    reference: date | None = None,
) -> str | None:
    detailed = resolve_date_detailed(
        text,
        reference=reference,
        mode=DateParseMode.REFERENCE,
        org_settings=org_settings,
    )
    if detailed and not detailed.needs_clarification and detailed.iso:
        return detailed.iso
    return None
