import re
from datetime import date, timedelta

from packages.scheduling.date_parsing.calendar import (
    _last_weekday_occurrence,
    _monday_of_week,
    _next_occurrence_of_weekday,
    _next_weekday_strict,
    _saturday_of_week,
    _weekday_in_current_week,
)
from packages.scheduling.date_parsing.helpers import (
    _clarification,
    _has_plain_weekday,
    _maybe_past_this_week_clarification,
    _resolved,
)
from packages.scheduling.date_parsing.normalize import format_date_label_pt, phrase_in_text
from packages.scheduling.date_parsing.types import (
    _NEXT_WEEK_PHRASES,
    _PAST_WEEK_PHRASES,
    _WEEK_HINT_ONLY_PHRASES,
    _WEEKDAY_ALIASES,
    _WEEKEND_GENERIC_PHRASES,
    _WEEKEND_NEXT_PHRASES,
    _WEEKEND_THIS_PHRASES,
    DateParseMode,
    DateResolution,
)


def _parse_week_hint_only(
    normalized: str,
    reference: date,
    mode: DateParseMode,
) -> DateResolution | None:
    del reference, mode
    for phrase in _WEEK_HINT_ONLY_PHRASES:
        if phrase_in_text(phrase, normalized):
            return _clarification("week_hint_only", phrase)
    return None


def _weekday_next_week_date(weekday: int, reference: date) -> date:
    monday = _monday_of_week(reference, week_offset=1)
    return monday + timedelta(days=weekday)


def _parse_weekday_this_or_next_alternatives(
    normalized: str,
    reference: date,
    mode: DateParseMode,
) -> DateResolution | None:
    """Clarify when the same weekday is mentioned for this week AND next week."""
    if mode != DateParseMode.BOOKING:
        return None

    processed_weekdays: set[int] = set()
    for alias, weekday in _WEEKDAY_ALIASES:
        if weekday in processed_weekdays:
            continue
        if not phrase_in_text(alias, normalized):
            continue
        processed_weekdays.add(weekday)

        this_label: str | None = None
        this_iso: str | None = None
        next_label: str | None = None
        next_iso: str | None = None

        for pat, label in (
            (rf"\bess[ae]\s+{re.escape(alias)}\b", f"essa {alias}"),
            (rf"\best[ae]\s+{re.escape(alias)}\b", f"esta {alias}"),
            (rf"\bnest[ea]\s+{re.escape(alias)}\b", f"nesta {alias}"),
        ):
            if re.search(pat, normalized):
                this_label = label
                this_iso = _weekday_in_current_week(weekday, reference).isoformat()
                break

        for pat, label in (
            (rf"\bproxim[oa]\s+{re.escape(alias)}\b", f"próxima {alias}"),
            (rf"\b{re.escape(alias)}\s+que\s+vem\b", f"{alias} que vem"),
            (rf"\b{re.escape(alias)}\s+da\s+semana\s+que\s+vem\b", f"{alias} da semana que vem"),
            (rf"\b{re.escape(alias)}\s+na\s+semana\s+que\s+vem\b", f"{alias} na semana que vem"),
            (rf"\b{re.escape(alias)}\s+da\s+proxim[oa]\s+semana\b", f"{alias} da próxima semana"),
            (rf"\b{re.escape(alias)}\s+na\s+proxim[oa]\s+semana\b", f"{alias} na próxima semana"),
        ):
            if re.search(pat, normalized):
                next_label = label
                next_iso = _weekday_next_week_date(weekday, reference).isoformat()
                break

        if next_iso and not this_iso:
            weekday_mentions = list(re.finditer(rf"\b{re.escape(alias)}\b", normalized))
            if len(weekday_mentions) >= 2:
                for match in weekday_mentions:
                    start = match.start()
                    prefix = normalized[max(0, start - 24):start]
                    if re.search(
                        r"(?:da\s+(?:semana\s+que\s+vem|proxim[oa]\s+semana)|na\s+(?:semana\s+que\s+vem|proxim[oa]\s+semana)|que\s+vem|proxim[oa])\s*$",
                        prefix,
                    ):
                        continue
                    if re.search(r"(?:ess[ae]|est[ae]|nest[ea])\s*$", prefix):
                        continue
                    this_label = alias
                    this_iso = _weekday_in_current_week(weekday, reference).isoformat()
                    break

        options: list[tuple[str, str]] = []
        if this_iso:
            options.append((this_label or alias, this_iso))
        if next_iso and next_iso != this_iso:
            options.append((next_label or f"{alias} que vem", next_iso))

        unique_isos = {iso for _, iso in options}
        if len(unique_isos) >= 2:
            option_parts = [f"{label} ({format_date_label_pt(iso)})" for label, iso in options]
            return _clarification("multiple_dates", alias, options=" ou ".join(option_parts))

    return None


def _parse_week_with_weekday(
    normalized: str,
    reference: date,
    mode: DateParseMode,
) -> DateResolution | None:
    if not any(phrase in normalized for phrase in _NEXT_WEEK_PHRASES):
        return None
    for alias, weekday in _WEEKDAY_ALIASES:
        if phrase_in_text(alias, normalized):
            monday = _monday_of_week(reference, week_offset=1)
            target = monday + timedelta(days=weekday)
            return _resolved(target.isoformat(), "week_future_weekday", f"semana+{alias}")
    return None


def _parse_neste_weekday(
    normalized: str,
    reference: date,
    mode: DateParseMode,
) -> DateResolution | None:
    for alias, weekday in _WEEKDAY_ALIASES:
        if re.search(rf"\b(?:neste|nesse|esse|este)\s+{re.escape(alias)}\b", normalized):
            target = _weekday_in_current_week(weekday, reference)
            clarify = _maybe_past_this_week_clarification(
                target, weekday, f"neste {alias}", reference=reference, mode=mode
            )
            if clarify:
                return clarify
            return _resolved(target.isoformat(), "weekday_this_week", f"neste {alias}")
    return None


def _parse_week_phrases(normalized: str, reference: date, mode: DateParseMode) -> DateResolution | None:
    for phrase in _PAST_WEEK_PHRASES:
        if phrase in normalized:
            if mode == DateParseMode.BOOKING:
                return None
            target = _monday_of_week(reference, week_offset=-1)
            return _resolved(target.isoformat(), "week_past", phrase, -7)

    for phrase in _NEXT_WEEK_PHRASES:
        if phrase in normalized:
            if not _has_plain_weekday(normalized):
                return _clarification("week_without_weekday", phrase)
            target = _monday_of_week(reference, week_offset=1)
            return _resolved(target.isoformat(), "week_future", phrase, 7)
    return None


def _parse_weekend_phrases(normalized: str, reference: date) -> DateResolution | None:
    for phrase in _WEEKEND_THIS_PHRASES:
        if phrase in normalized:
            return _resolved(_saturday_of_week(reference).isoformat(), "weekend", phrase)

    for phrase in _WEEKEND_NEXT_PHRASES + _WEEKEND_GENERIC_PHRASES:
        if phrase in normalized:
            saturday = _saturday_of_week(reference)
            if saturday < reference:
                saturday = _saturday_of_week(reference, week_offset=1)
            elif phrase in _WEEKEND_NEXT_PHRASES and saturday == reference:
                saturday = _saturday_of_week(reference, week_offset=1)
            return _resolved(saturday.isoformat(), "weekend", phrase)

    if re.search(r"\bproxim[oa]\s+sabado\b", normalized):
        target = _next_weekday_strict(5, reference)
        return _resolved(target.isoformat(), "weekend", "proximo sabado")
    return None


def _plain_weekday_matches(normalized: str) -> list[tuple[int, str, int]]:
    matches: list[tuple[int, str, int]] = []
    for alias, weekday in _WEEKDAY_ALIASES:
        for match in re.finditer(rf"\b{re.escape(alias)}\b", normalized):
            matches.append((match.start(), alias, weekday))
    return matches


def _parse_weekday_compound(
    normalized: str,
    reference: date,
    mode: DateParseMode,
) -> DateResolution | None:
    for alias, weekday in _WEEKDAY_ALIASES:
        past_patterns = (
            rf"\b{re.escape(alias)}\s+passad[oa]\b",
            rf"\bpassad[oa]\s+{re.escape(alias)}\b",
        )
        for pattern in past_patterns:
            if re.search(pattern, normalized):
                if mode == DateParseMode.BOOKING:
                    return None
                target = _last_weekday_occurrence(weekday, reference)
                return _resolved(target.isoformat(), "weekday_past", alias)

        next_patterns = (
            rf"\bproxim[oa]\s+{re.escape(alias)}\b",
            rf"\b{re.escape(alias)}\s+que vem\b",
        )
        for pattern in next_patterns:
            if re.search(pattern, normalized):
                target = _next_weekday_strict(weekday, reference)
                return _resolved(target.isoformat(), "weekday_future", alias)

        this_patterns = (
            rf"\bess[ae]\s+{re.escape(alias)}\b",
            rf"\best[ae]\s+{re.escape(alias)}\b",
        )
        for pattern in this_patterns:
            if re.search(pattern, normalized):
                target = _weekday_in_current_week(weekday, reference)
                clarify = _maybe_past_this_week_clarification(
                    target, weekday, alias, reference=reference, mode=mode
                )
                if clarify:
                    return clarify
                return _resolved(target.isoformat(), "weekday_this_week", alias)

    plain_matches = _plain_weekday_matches(normalized)
    if len(plain_matches) >= 2:
        unique: dict[int, str] = {}
        for _, alias, weekday in sorted(plain_matches, key=lambda item: item[0]):
            unique.setdefault(weekday, alias)
        if len(unique) >= 2:
            options = " ou ".join(unique.values())
            return _clarification("multiple_weekdays", options, options=options)

    if plain_matches:
        _, alias, weekday = min(plain_matches, key=lambda item: item[0])
        target = _next_occurrence_of_weekday(weekday, reference)
        return _resolved(target.isoformat(), "weekday", alias)

    return None
