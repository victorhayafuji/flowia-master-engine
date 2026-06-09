"""Booking intent models and small helpers."""
from __future__ import annotations

import re
from dataclasses import dataclass

_NAME_PATTERNS = (
    re.compile(
        r"(?:meu nome(?:\s+e|\s+é)|me chamo|sou(?:\s+o|\s+a)?)\s+"
        r"([A-Za-zÀ-ú'\s]{2,60}?)(?:,|\s+telefone|\s+tel|\s+phone|\d{10,}|$)",
        re.I,
    ),
    re.compile(
        r"^([A-Za-zÀ-ú]+(?:\s+(?:da|de|do|dos|das|e)\s+[A-Za-zÀ-ú]+)+)\s*,\s*(\d{10,13})\s*$",
        re.I,
    ),
    re.compile(
        r"^([A-Za-zÀ-ú][A-Za-zÀ-ú'\s-]{1,59}?)\s*,\s*(\d{10,13})\s*$",
    ),
)


@dataclass
class BookingIntent:
    service_query: str
    date_iso: str
    time_hhmm: str
    patient_name: str
    patient_phone: str
    professional_name: str | None = None


@dataclass
class SchedulingTurnResult:
    message: str
    booking_date: str | None = None
    booking_service: str | None = None
    booking_time: str | None = None
    booking_patient_name: str | None = None
    booking_patient_phone: str | None = None


_AVAILABILITY_FOLLOWUP_PHRASES = (
    "outro hor",
    "outra hor",
    "tem hor",
    "tem vaga",
    "algum hor",
    "disponib",
    "horarios",
    "horários",
    "qual hor",
    "pode ser",
    "prefiro",
)


def is_availability_followup(text: str, *, has_time_in_message: bool = False) -> bool:
    t = text.lower().strip()
    if has_time_in_message:
        return any(phrase in t for phrase in _AVAILABILITY_FOLLOWUP_PHRASES)
    if t in {"sim", "s", "ok", "pode", "claro", "quero"}:
        return True
    return any(phrase in t for phrase in _AVAILABILITY_FOLLOWUP_PHRASES)
