"""Unit tests for the financial categorization helper (single source of truth)."""
from __future__ import annotations

from packages.scheduling import financial


def _appt(status: str, price):
    return {"status": status, "service": {"price": price}}


def test_category_mapping():
    assert financial.categorize_status("completed") == financial.BILLED
    for status in ("pending", "confirmed", "arrived", "in_progress"):
        assert financial.categorize_status(status) == financial.TO_BILL
    assert financial.categorize_status("no_show") == financial.LOSS


def test_excluded_statuses_have_no_category():
    assert financial.categorize_status("cancelled") is None
    assert financial.categorize_status("rescheduled") is None
    assert financial.categorize_status(None) is None
    assert financial.categorize_status("bogus") is None


def test_summarize_sums_price_per_category():
    appointments = [
        _appt("completed", 100.0),
        _appt("completed", 50.0),
        _appt("confirmed", 80.0),
        _appt("pending", 20.0),
        _appt("no_show", 120.0),
        _appt("cancelled", 999.0),  # excluded
        _appt("rescheduled", 999.0),  # excluded
    ]
    result = financial.summarize(appointments)

    assert result[financial.BILLED] == {"amount": 150.0, "count": 2}
    assert result[financial.TO_BILL] == {"amount": 100.0, "count": 2}
    assert result[financial.LOSS] == {"amount": 120.0, "count": 1}


def test_summarize_treats_null_price_as_zero():
    appointments = [
        _appt("completed", None),
        {"status": "completed"},  # no service key at all
        {"status": "completed", "service": None},
    ]
    result = financial.summarize(appointments)
    assert result[financial.BILLED] == {"amount": 0.0, "count": 3}


def test_summarize_handles_embedded_service_as_list():
    # Supabase may embed a to-one relation as a single-item list.
    appointments = [{"status": "completed", "service": [{"price": 75.0}]}]
    result = financial.summarize(appointments)
    assert result[financial.BILLED] == {"amount": 75.0, "count": 1}


def test_empty_input_returns_zeroed_buckets():
    result = financial.summarize([])
    assert result == financial.empty_summary()
