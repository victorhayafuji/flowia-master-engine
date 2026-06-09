"""PT-BR date parsing — calendar."""
from __future__ import annotations

from datetime import date, timedelta


def _monday_of_week(reference: date, *, week_offset: int = 0) -> date:
    monday = reference - timedelta(days=reference.weekday())
    return monday + timedelta(weeks=week_offset)


def _saturday_of_week(reference: date, *, week_offset: int = 0) -> date:
    return _monday_of_week(reference, week_offset=week_offset) + timedelta(days=5)


def _next_occurrence_of_weekday(weekday: int, reference: date) -> date:
    days_ahead = (weekday - reference.weekday()) % 7
    return reference + timedelta(days=days_ahead)


def _next_weekday_strict(weekday: int, reference: date) -> date:
    candidate = _next_occurrence_of_weekday(weekday, reference)
    if candidate <= reference:
        return candidate + timedelta(days=7)
    return candidate


def _weekday_in_current_week(weekday: int, reference: date) -> date:
    return _monday_of_week(reference) + timedelta(days=weekday)


def _last_weekday_occurrence(weekday: int, reference: date) -> date:
    days_back = (reference.weekday() - weekday) % 7
    return reference - timedelta(days=days_back)


def _add_business_days(reference: date, days: int) -> date:
    current = reference
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def _infer_year(day: int, month: int, reference: date) -> int:
    candidate = date(reference.year, month, day)
    if candidate >= reference:
        return reference.year
    return reference.year + 1
