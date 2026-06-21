"""Financial categorization of appointments — single source of truth.

Maps each appointment status to one of three business categories and sums the
service price per category. Centralized here so the dashboard (and any future
channel) never duplicates the status→category rule.

Categories:
- ``billed``  (Faturado)   — concluded services (revenue earned).
- ``to_bill`` (A Faturar)  — open/future/in-progress services (pipeline).
- ``loss``    (Perda)      — no-shows (lost revenue).

``cancelled`` and ``rescheduled`` are intentionally excluded (no category).
"""
from __future__ import annotations

from typing import Any

from packages.models.enums import AppointmentStatus

BILLED = "billed"
TO_BILL = "to_bill"
LOSS = "loss"

# Status → financial category. Statuses absent from this map are excluded.
FINANCIAL_CATEGORY: dict[str, str] = {
    AppointmentStatus.COMPLETED.value: BILLED,
    AppointmentStatus.PENDING.value: TO_BILL,
    AppointmentStatus.CONFIRMED.value: TO_BILL,
    AppointmentStatus.ARRIVED.value: TO_BILL,
    AppointmentStatus.IN_PROGRESS.value: TO_BILL,
    AppointmentStatus.NO_SHOW.value: LOSS,
    # AppointmentStatus.CANCELLED / RESCHEDULED → excluded by design.
}


def categorize_status(status: str | None) -> str | None:
    """Return the financial category for a status, or None when excluded."""
    if not status:
        return None
    return FINANCIAL_CATEGORY.get(status)


def _price_of(appointment: dict[str, Any]) -> float:
    """Service price for an appointment row (joined as ``service``). Null → 0."""
    service = appointment.get("service")
    if isinstance(service, list):  # Supabase may embed a to-one as a 1-item list.
        service = service[0] if service else None
    price = service.get("price") if isinstance(service, dict) else None
    try:
        return float(price or 0)
    except (TypeError, ValueError):
        return 0.0


def empty_summary() -> dict[str, dict[str, float | int]]:
    return {
        BILLED: {"amount": 0.0, "count": 0},
        TO_BILL: {"amount": 0.0, "count": 0},
        LOSS: {"amount": 0.0, "count": 0},
    }


def summarize(appointments: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    """Aggregate appointments into {billed, to_bill, loss} with amount + count.

    Each appointment is a dict with ``status`` and an embedded ``service`` carrying
    ``price`` (e.g. ``select("status, service:service_catalog(price)")``).
    """
    buckets = empty_summary()
    for appt in appointments:
        category = categorize_status(appt.get("status"))
        if category is None:
            continue
        buckets[category]["amount"] += _price_of(appt)
        buckets[category]["count"] += 1
    for bucket in buckets.values():
        bucket["amount"] = round(bucket["amount"], 2)
    return buckets
