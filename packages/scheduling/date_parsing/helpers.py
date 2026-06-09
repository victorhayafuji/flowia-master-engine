import logging
import re
from datetime import date, timedelta

from packages.scheduling.date_parsing.normalize import phrase_in_text
from packages.scheduling.date_parsing.types import (
    _NEXT_WEEK_PHRASES,
    _RELATIVE_OFFSETS,
    _WEEKDAY_ALIASES,
    _WEEKDAY_PT,
    CLARIFICATION_PROMPTS,
    REFERENCE_PAST_LIMIT_DAYS,
    DateParseMode,
    DateResolution,
)

logger = logging.getLogger(__name__)

def _clarification(
    reason: str,
    phrase: str,
    *,
    prompt: str | None = None,
    **prompt_vars: str,
) -> DateResolution:
    template = prompt or CLARIFICATION_PROMPTS.get(reason, "Qual dia você prefere?")
    try:
        message = template.format(**prompt_vars)
    except KeyError:
        message = template
    return DateResolution(
        iso=None,
        kind="clarification",
        phrase=phrase,
        needs_clarification=True,
        clarification_reason=reason,
        clarification_prompt=message,
    )


def _maybe_past_this_week_clarification(
    target: date,
    weekday: int,
    alias: str,
    *,
    reference: date,
    mode: DateParseMode,
) -> DateResolution | None:
    if mode != DateParseMode.BOOKING or target >= reference:
        return None
    weekday_label = _WEEKDAY_PT[weekday]
    return _clarification(
        "past_this_week",
        alias,
        weekday=weekday_label,
    )


def _resolved(iso: str, kind: str, phrase: str, offset_days: int | None = None) -> DateResolution:
    return DateResolution(iso=iso, kind=kind, phrase=phrase, offset_days=offset_days)


def _accept_resolution(
    resolution: DateResolution,
    *,
    reference: date,
    mode: DateParseMode,
) -> DateResolution | None:
    if resolution.needs_clarification or not resolution.iso:
        return resolution if resolution.needs_clarification else None
    try:
        parsed = date.fromisoformat(resolution.iso)
    except ValueError:
        return None
    if mode == DateParseMode.BOOKING and parsed < reference:
        return None
    if mode == DateParseMode.REFERENCE:
        if parsed > reference + timedelta(days=365):
            return None
        if parsed < reference - timedelta(days=REFERENCE_PAST_LIMIT_DAYS):
            return None
        if resolution.kind.endswith("_past") and mode == DateParseMode.BOOKING:
            return None
    return resolution


def _log_resolution(text: str, resolution: DateResolution | None) -> None:
    if resolution is None:
        logger.info("date_parse | outcome=none reason=- kind=-")
        return
    if resolution.needs_clarification:
        outcome = "clarify"
    elif resolution.iso:
        outcome = "resolved"
    else:
        outcome = "none"
    logger.info(
        "date_parse | outcome=%s reason=%s kind=%s",
        outcome,
        resolution.clarification_reason or "-",
        resolution.kind,
    )


def _has_plain_weekday(normalized: str) -> bool:
    return any(phrase_in_text(alias, normalized) for alias, _ in _WEEKDAY_ALIASES)


def _relative_phrase_matches(normalized: str, reference: date) -> list[tuple[str, str, int]]:
    """Non-overlapping relative phrases, longest match first."""
    matches: list[tuple[str, str, int]] = []
    used_spans: list[tuple[int, int]] = []
    ordered = sorted(_RELATIVE_OFFSETS, key=lambda item: len(item[0]), reverse=True)
    for phrase, day_offset in ordered:
        for match in re.finditer(rf"\b{re.escape(phrase)}\b", normalized):
            span = match.span()
            if any(not (span[1] <= start or span[0] >= end) for start, end in used_spans):
                continue
            target = reference + timedelta(days=day_offset)
            matches.append((phrase, target.isoformat(), day_offset))
            used_spans.append(span)
    return matches


def _is_plain_weekday_alias(normalized: str, alias: str) -> bool:
    """Weekday mention that is not essa/proxima/nesta/semana que vem qualified."""
    if not phrase_in_text(alias, normalized):
        return False
    compound_patterns = (
        rf"\bess[ae]\s+{re.escape(alias)}\b",
        rf"\best[ae]\s+{re.escape(alias)}\b",
        rf"\bproxim[oa]\s+{re.escape(alias)}\b",
        rf"\b{re.escape(alias)}\s+que vem\b",
        rf"\b{re.escape(alias)}\s+passad[oa]\b",
        rf"\bpassad[oa]\s+{re.escape(alias)}\b",
        rf"\bnest[ea]\s+{re.escape(alias)}\b",
    )
    if any(re.search(p, normalized) for p in compound_patterns):
        return False
    if any(phrase in normalized for phrase in _NEXT_WEEK_PHRASES) and phrase_in_text(alias, normalized):
        return False
    return True
