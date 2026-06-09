"""PT-BR date parsing — types."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

REFERENCE_PAST_LIMIT_DAYS = 365

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
_DIA_N_RE = re.compile(r"\bdia\s+(\d{1,2})(?:\s+de\s+(\w+))?(?:\s+de\s+(\d{4}))?\b", re.I)
_ISO_DATE_IN_TEXT_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_DMY_IN_TEXT_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?\b")

_OFFSET_DAYS_RE = re.compile(
    r"\b(?:daqui\s+(?:a\s+)?|em|depois\s+de)\s*(\d+)\s+dias?(?!\s+(?:uteis|util))\b",
)
_OFFSET_WEEKS_RE = re.compile(
    r"\b(?:daqui\s+(?:a\s+)?|em)\s*(\d+)\s+semanas?\b",
)
_OFFSET_BUSINESS_DAYS_RE = re.compile(
    r"\b(?:daqui\s+(?:a\s+)?|em|depois\s+de)\s*(\d+)\s+dias?\s+(?:uteis|util)\b",
)
_CURRENCY_DMY_RE = re.compile(r"r\$\s*\d{1,2}[/-]\d{1,2}", re.I)

# Pre-normalize colloquial typos/abbreviations (longest first).
_TEMPORAL_ALIAS_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\bprox\s+", "proxima "),
    (r"\b6f\b", "sexta"),
    (r"\b5f\b", "sexta"),
    (r"\b4f\b", "quinta"),
    (r"\b3f\b", "quarta"),
    (r"\b2f\b", "terca"),
    (r"\bter\b", "terca"),
    (r"\bqta\b", "quarta"),
    (r"\bqna\b", "quinta"),
    (r"\bsab\b", "sabado"),
    (r"\bdom\b", "domingo"),
)

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

_RELATIVE_OFFSETS: tuple[tuple[str, int], ...] = (
    ("depois de amanha", 2),
    ("antes de ontem", -2),
    ("anteontem", -2),
    ("depois de ontem", -2),
    ("amanha", 1),
    ("ontem", -1),
    ("hoje", 0),
)

_NEXT_WEEK_PHRASES: tuple[str, ...] = (
    "semana que vem",
    "proxima semana",
    "semana proxima",
    "na proxima semana",
    "na semana que vem",
)

_PAST_WEEK_PHRASES: tuple[str, ...] = (
    "semana passada",
    "semana anterior",
    "na semana passada",
)

_WEEKEND_THIS_PHRASES: tuple[str, ...] = (
    "neste fim de semana",
    "nesse fim de semana",
    "esse fim de semana",
    "este fim de semana",
)

_WEEKEND_NEXT_PHRASES: tuple[str, ...] = (
    "proximo fim de semana",
    "proxima fim de semana",
    "no proximo fim de semana",
)

_WEEKEND_GENERIC_PHRASES: tuple[str, ...] = (
    "fim de semana",
    "final de semana",
)

_WEEK_HINT_ONLY_PHRASES: tuple[str, ...] = (
    "essa semana",
    "esta semana",
)

_WEEKDAY_PT = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)

CLARIFICATION_PROMPTS: dict[str, str] = {
    "week_without_weekday": "Semana que vem — qual dia prefere? (ex: sexta ou 12/06)",
    "multiple_weekdays": "Qual dia você prefere: {options}?",
    "past_this_week": "Essa data já passou. Quer o próximo {weekday} ou outro dia?",
    "week_hint_only": "Qual dia dessa semana funciona melhor?",
    "day_without_month": "Dia {day} de qual mês?",
    "multiple_dates": "Qual dia você prefere: {options}?",
}


class DateParseMode(str, Enum):
    BOOKING = "booking"
    REFERENCE = "reference"


@dataclass(frozen=True)
class DateResolution:
    iso: str | None
    kind: str
    phrase: str
    offset_days: int | None = None
    needs_clarification: bool = False
    clarification_reason: str | None = None
    clarification_prompt: str | None = None
