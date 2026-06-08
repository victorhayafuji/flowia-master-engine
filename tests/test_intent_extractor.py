"""Tests for intent extractor field resolution."""
from datetime import date

from packages.engine.intent_extractor import BookingExtract, _resolve_extracted_fields


class _FixedToday(date):
    @classmethod
    def today(cls):
        return date(2026, 6, 7)


def test_resolve_extracted_fields_parses_weekday_date_hint(mocker):
    mocker.patch(
        "packages.scheduling.guardrails.list_catalog_services",
        return_value=[
            {"id": "1", "name": "Coloração Completa", "duration_minutes": 120, "price": 200},
        ],
    )
    mocker.patch("packages.engine.intent_extractor.date", _FixedToday)
    raw = BookingExtract(
        service_hint="mechas",
        date_hint="sexta",
        user_acknowledgment="Você quer agendar mechas para sexta-feira.",
        confidence=0.9,
    )
    enriched = _resolve_extracted_fields(raw, "22222222-2222-2222-2222-222222222222")
    assert enriched.resolved_date == "2026-06-12"
    assert enriched.resolved_service == "Coloração Completa"


def test_resolve_extracted_fields_drops_invalid_date_hint():
    raw = BookingExtract(date_hint="algum dia", confidence=0.2)
    enriched = _resolve_extracted_fields(raw, "22222222-2222-2222-2222-222222222222")
    assert enriched.resolved_date is None
