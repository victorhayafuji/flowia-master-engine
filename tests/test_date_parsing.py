"""Parametric tests for PT-BR colloquial date parsing."""
from datetime import date

import pytest

from packages.scheduling.date_parsing import (
    DateParseMode,
    extract_booking_date_from_text,
    extract_reference_date_from_text,
    format_date_label_pt,
    has_temporal_date_hint,
    normalize_booking_date,
    resolve_date_detailed,
    resolve_date_from_text,
)
from packages.scheduling.guardrails import validate_booking_date, validate_reference_date
from tests.fixtures.temporal_date_matrix import (
    HINT_ONLY_CASES,
    LLM_BEHAVIOR_TEMPORAL_CASES,
    TEMPORAL_MATRIX,
    TemporalCase,
)


@pytest.mark.parametrize("case", TEMPORAL_MATRIX, ids=lambda c: c.id)
def test_resolve_date_matrix(case: TemporalCase):
    detailed = resolve_date_detailed(case.text, reference=case.reference, mode=case.mode)
    if case.expected_clarification_reason:
        assert detailed is not None, f"expected clarification {case.expected_clarification_reason}"
        assert detailed.needs_clarification
        assert detailed.clarification_reason == case.expected_clarification_reason
        assert detailed.iso is None
        assert detailed.clarification_prompt
        return

    result = resolve_date_from_text(case.text, reference=case.reference, mode=case.mode)
    if case.expected_iso is None:
        assert result is None, f"expected None ({case.expected_none_reason}), got {result}"
    else:
        assert result is not None, f"expected {case.expected_iso}, got None"
        assert result.iso == case.expected_iso


class TestExtractWrappers:
    def test_booking_rejects_past_via_guardrails(self):
        ref = date(2026, 6, 7)
        assert extract_booking_date_from_text("Faltei ontem", reference=ref) is None
        assert extract_reference_date_from_text("Faltei ontem", reference=ref) == "2026-06-06"

    def test_format_date_label(self):
        assert "06/06" in format_date_label_pt("2026-06-06")

    def test_clarification_not_in_booking_extract(self):
        ref = date(2026, 6, 7)
        assert extract_booking_date_from_text("semana que vem", reference=ref) is None
        assert extract_booking_date_from_text("sexta ou sabado", reference=ref) is None


class TestHasTemporalHint:
    def test_detects_amanha(self):
        assert has_temporal_date_hint("Quero agendar amanhã")

    def test_rejects_onde_salon(self):
        assert not has_temporal_date_hint("Onde fica o salão?")

    def test_de_tarde_not_date_hint(self):
        assert not has_temporal_date_hint("prefiro de tarde")

    @pytest.mark.parametrize(("text", "expected"), HINT_ONLY_CASES)
    def test_hint_only_matrix(self, text: str, expected: bool):
        assert has_temporal_date_hint(text) is expected


class TestValidateModes:
    def test_reference_accepts_yesterday(self):
        ref = date(2026, 6, 7)
        parsed, err = validate_reference_date("2026-06-06", reference=ref)
        assert err is None
        assert parsed == date(2026, 6, 6)

    def test_booking_rejects_yesterday(self):
        ref = date(2026, 6, 7)
        _, err = validate_booking_date("2026-06-06", reference=ref)
        assert err == "past_date"


class TestNormalizeBookingDate:
    def test_delegates_weekday(self):
        ref = date(2026, 6, 7)
        assert normalize_booking_date("sexta", reference=ref) == "2026-06-12"


@pytest.mark.llm_behavior
@pytest.mark.parametrize(("text", "expected_iso"), LLM_BEHAVIOR_TEMPORAL_CASES)
def test_llm_behavior_temporal_tier_d(text: str, expected_iso: str | None):
    ref = date(2026, 6, 7)
    detailed = resolve_date_detailed(text, reference=ref, mode=DateParseMode.BOOKING)
    if expected_iso is None:
        assert detailed is None or detailed.needs_clarification or detailed.iso is None
    else:
        assert detailed is not None and detailed.iso == expected_iso
