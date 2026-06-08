"""Tests for booking guardrails."""
from datetime import date, datetime, timedelta

from packages.scheduling.guardrails import (
    GENERIC_INVALID_MSG,
    check_rate_limit,
    extract_booking_date_from_text,
    normalize_booking_date,
    parse_booking_date,
    reject_sqlish_patterns,
    reset_rate_limits_for_tests,
    resolve_service_from_catalog,
    sanitize_text_field,
    validate_date,
    validate_phone,
    validate_professional_name,
)
from packages.scheduling.timezone_utils import extract_booking_time_from_text, parse_booking_datetime

CATALOG = [
    {"id": "1", "name": "Coloração Completa", "duration_minutes": 120, "price": 200},
    {"id": "2", "name": "Corte Feminino", "duration_minutes": 60, "price": 120},
]


class TestSanitizeText:
    def test_rejects_sql_injection(self):
        _, err = sanitize_text_field("'; DROP TABLE patients; --", 100)
        assert err == "delimiter"

    def test_rejects_where_1_equals_1(self):
        assert reject_sqlish_patterns("WHERE 1=1") == "sql"

    def test_rejects_wildcards(self):
        assert reject_sqlish_patterns("color%") == "wildcard"


class TestValidatePhone:
    def test_valid_br_phone(self):
        phone, err = validate_phone("11987654320")
        assert err is None
        assert phone == "11987654320"

    def test_rejects_short(self):
        _, err = validate_phone("123")
        assert err == "phone_length"

    def test_rejects_trivial(self):
        _, err = validate_phone("11111111111")
        assert err == "phone_trivial"


class TestValidateDate:
    def test_valid_today(self):
        today = date.today().isoformat()
        parsed, err = validate_date(today)
        assert err is None
        assert parsed == date.today()

    def test_rejects_past(self):
        past = (date.today() - timedelta(days=1)).isoformat()
        _, err = validate_date(past)
        assert err == "past_date"

    def test_rejects_too_far(self):
        far = (date.today() + timedelta(days=120)).isoformat()
        _, err = validate_date(far)
        assert err == "too_far"


class TestNormalizeBookingDate:
    def test_iso_passthrough(self):
        assert normalize_booking_date("2026-06-10") == "2026-06-10"

    def test_brazilian_slash_format(self):
        assert normalize_booking_date("10/06/2026") == "2026-06-10"

    def test_portuguese_month_without_year(self):
        ref = date(2026, 6, 7)
        assert normalize_booking_date("10 de junho", reference=ref) == "2026-06-10"

    def test_portuguese_month_with_year(self):
        assert normalize_booking_date("10 de junho de 2026") == "2026-06-10"

    def test_infers_next_year_when_day_passed(self):
        ref = date(2026, 6, 11)
        assert normalize_booking_date("10 de junho", reference=ref) == "2027-06-10"

    def test_parse_booking_date_rejects_past(self):
        ref = date(2026, 6, 7)
        _, err = parse_booking_date("10 de junho de 2025", reference=ref)
        assert err == "past_date"

    def test_coerces_stale_llm_year(self):
        ref = date(2026, 6, 7)
        parsed, err = parse_booking_date("2024-06-10", reference=ref)
        assert err is None
        assert parsed == date(2026, 6, 10)


class TestExtractBookingDateFromText:
    def test_quarta_dia_10_de_junho(self):
        ref = date(2026, 6, 7)
        assert (
            extract_booking_date_from_text(
                "Quero agendar corte masculino para quarta dia 10 de junho",
                reference=ref,
            )
            == "2026-06-10"
        )

    def test_ignores_stale_year_in_text_when_coercible(self):
        ref = date(2026, 6, 7)
        assert (
            extract_booking_date_from_text("10 de junho de 2024", reference=ref)
            == "2026-06-10"
        )

    def test_weekday_sexta_in_message(self):
        ref = date(2026, 6, 7)  # Sunday
        assert (
            extract_booking_date_from_text("Quero mechas sexta", reference=ref)
            == "2026-06-12"
        )

    def test_weekday_standalone(self):
        ref = date(2026, 6, 5)  # Friday
        assert normalize_booking_date("sexta", reference=ref) == "2026-06-05"
        assert normalize_booking_date("sexta", reference=date(2026, 6, 6)) == "2026-06-12"


class TestTimezoneParsing:
    def test_z_suffix_treated_as_local_wall_clock(self):
        local, utc, err = parse_booking_datetime(
            "2026-06-10T11:00:00Z",
            "America/Sao_Paulo",
            assume_local_wall_clock=True,
        )
        assert err is None
        assert local == datetime(2026, 6, 10, 11, 0)
        assert utc.hour == 14 and utc.minute == 0

    def test_extract_time_as_prefix(self):
        assert extract_booking_time_from_text("prefiro as 11:30") == "11:30"


class TestResolveService:
    def test_exact_match(self):
        svc, err = resolve_service_from_catalog("org", "Coloração Completa", catalog=CATALOG)
        assert err is None
        assert svc["name"] == "Coloração Completa"

    def test_synonym_mechas(self):
        svc, err = resolve_service_from_catalog("org", "mechas", catalog=CATALOG)
        assert err is None
        assert "Coloração" in svc["name"]

    def test_ambiguous_partial(self):
        _, err = resolve_service_from_catalog("org", "o", catalog=CATALOG)
        assert err == "ambiguous"

    def test_not_found(self):
        _, err = resolve_service_from_catalog("org", "podologia", catalog=CATALOG)
        assert err == "not_found"

    def test_rejects_injection_in_query(self):
        _, err = resolve_service_from_catalog("org", "color'; WHERE 1=1--", catalog=CATALOG)
        assert err == "delimiter"


class TestProfessionalValidation:
    def test_filters_eligible(self):
        eligible = [{"id": "a", "name": "Maria Silva"}, {"id": "b", "name": "Ana Costa"}]
        matched, err = validate_professional_name("Maria", eligible)
        assert err is None
        assert len(matched) == 1
        assert matched[0]["name"] == "Maria Silva"


class TestRateLimit:
    def setup_method(self):
        reset_rate_limits_for_tests()

    def test_blocks_after_limit(self):
        for _ in range(20):
            ok, _ = check_rate_limit("sender1", "check_availability")
            assert ok
        ok, err = check_rate_limit("sender1", "check_availability")
        assert not ok
        assert err == "rate_limit"


class TestGenericMessage:
    def test_constant(self):
        assert "inválida" in GENERIC_INVALID_MSG.lower()
