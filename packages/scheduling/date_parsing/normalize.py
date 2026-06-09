import re
import unicodedata
from datetime import date

from packages.scheduling.date_parsing.types import (
    _CURRENCY_DMY_RE,
    _NEXT_WEEK_PHRASES,
    _PAST_WEEK_PHRASES,
    _RELATIVE_OFFSETS,
    _TEMPORAL_ALIAS_REPLACEMENTS,
    _WEEK_HINT_ONLY_PHRASES,
    _WEEKDAY_ALIASES,
    _WEEKDAY_PT,
    _WEEKEND_GENERIC_PHRASES,
    _WEEKEND_NEXT_PHRASES,
    _WEEKEND_THIS_PHRASES,
)


def expand_temporal_aliases(text: str) -> str:
    expanded = text
    for pattern, replacement in _TEMPORAL_ALIAS_REPLACEMENTS:
        expanded = re.sub(pattern, replacement, expanded, flags=re.I)
    return expanded


def normalize_key(text: str) -> str:
    folded = unicodedata.normalize("NFKD", expand_temporal_aliases(text))
    ascii_text = "".join(c for c in folded if not unicodedata.combining(c))
    return " ".join(ascii_text.lower().split())


def phrase_in_text(phrase: str, normalized: str) -> bool:
    return bool(re.search(rf"\b{re.escape(phrase)}\b", normalized))


def _is_currency_dmy_match(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - 4) : end + 2].lower()
    return bool(_CURRENCY_DMY_RE.search(window) or re.search(r"r\$\s*\d", window))


def format_date_label_pt(iso: str) -> str:
    parsed = date.fromisoformat(iso)
    weekday = _WEEKDAY_PT[parsed.weekday()]
    return f"{weekday}, {parsed.day:02d}/{parsed.month:02d}"


def get_temporal_hint_phrases() -> frozenset[str]:
    hints: set[str] = set()
    for phrase, _ in _RELATIVE_OFFSETS:
        hints.add(phrase)
    for phrase in _NEXT_WEEK_PHRASES + _PAST_WEEK_PHRASES + _WEEK_HINT_ONLY_PHRASES:
        hints.add(phrase)
    for phrase in _WEEKEND_THIS_PHRASES + _WEEKEND_NEXT_PHRASES + _WEEKEND_GENERIC_PHRASES:
        hints.add(phrase)
    for alias, _ in _WEEKDAY_ALIASES:
        hints.add(alias)
        hints.add(f"proxima {alias}")
        hints.add(f"proximo {alias}")
        hints.add(f"{alias} que vem")
        hints.add(f"essa {alias}")
        hints.add(f"esta {alias}")
        hints.add(f"{alias} passada")
        hints.add(f"{alias} passado")
    return frozenset(hints)


def has_temporal_date_hint(text: str) -> bool:
    if not text or not text.strip():
        return False
    from packages.scheduling.date_parsing.resolve import resolve_date_detailed
    from packages.scheduling.date_parsing.types import DateParseMode

    detailed = resolve_date_detailed(text, reference=date.today(), mode=DateParseMode.REFERENCE)
    if detailed and (detailed.iso or detailed.needs_clarification):
        return True
    normalized = normalize_key(text)
    if _CURRENCY_DMY_RE.search(normalized):
        return False
    if re.search(r"\b\d{1,2}/\d{1,2}\b", normalized):
        return True
    if re.search(r"\b\d{4}-\d{2}-\d{2}\b", normalized):
        return True
    return any(phrase_in_text(hint, normalized) for hint in get_temporal_hint_phrases())
