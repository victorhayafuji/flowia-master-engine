"""Operational edge-case regressions for PT-BR date parsing in production flows."""
from datetime import date

import pytest
from langchain_core.messages import HumanMessage

from packages.engine.routing import (
    has_implicit_scheduling_intent,
    has_support_intent,
    has_time_or_slot_question,
    is_booking_conversation,
    resolve_triage_agent,
)
from packages.engine.support_executor import has_cancel_and_reschedule_intent, run_support_turn
from packages.scheduling.booking_executor import (
    _past_booking_date_message,
    _resolve_booking_date_turn,
    resolve_booking_context,
    run_scheduling_turn,
)
from packages.scheduling.date_parsing import (
    DateParseMode,
    has_temporal_date_hint,
    phrase_in_text,
    resolve_date_detailed,
    resolve_date_from_text,
)

REF = date(2026, 6, 7)


@pytest.fixture(autouse=True)
def _freeze_today(mocker):
    """Freeze date.today to REF so flows that resolve dates without an explicit
    reference (ex: resolve_booking_context) stay deterministic on any clock (CI-safe)."""
    class _FixedToday(date):
        @classmethod
        def today(cls):
            return cls(REF.year, REF.month, REF.day)

    mocker.patch("packages.scheduling.booking_executor.date", _FixedToday)
    mocker.patch("packages.scheduling.booking_flow_memory.date", _FixedToday)


class TestSubstringFalsePositives:
    def test_contemporaneo_not_ontem(self):
        assert not phrase_in_text("ontem", "contemporaneo")
        assert not has_temporal_date_hint("Quero corte contemporaneo")

    def test_momento_not_temporal(self):
        assert not has_temporal_date_hint("No momento não posso ir")


class TestOperationalBookingMessages:
    @pytest.mark.parametrize(
        ("text", "expected_iso"),
        [
            ("Quero agendar manicure amanhã", "2026-06-08"),
            ("Corte daqui 3 dias", "2026-06-10"),
            ("Coloração semana que vem na sexta", "2026-06-12"),
        ],
    )
    def test_booking_phrases(self, text: str, expected_iso: str):
        result = resolve_date_from_text(text, reference=REF, mode=DateParseMode.BOOKING)
        assert result is not None
        assert result.iso == expected_iso

    def test_past_booking_message_for_ontem(self):
        msg = _past_booking_date_message("Quero agendar manicure ontem", reference=REF)
        assert msg is not None
        assert "a partir de hoje" in msg.lower()

    def test_past_booking_none_for_amanha(self):
        assert _past_booking_date_message("Quero agendar amanhã", reference=REF) is None

    def test_amanha_ou_depois_de_amanha_needs_clarification(self):
        result = resolve_date_detailed(
            "Quero marcar corte masculino para amanhã ou depois de amanhã",
            reference=date(2026, 6, 10),
            mode=DateParseMode.BOOKING,
        )
        assert result is not None
        assert result.needs_clarification
        assert result.clarification_reason == "multiple_dates"
        assert "qual dia você prefere" in (result.clarification_prompt or "").lower()

    def test_amanha_ou_sexta_different_days_needs_clarification(self):
        result = resolve_date_detailed(
            "Gostaria de agendar um corte masculino para amanhã ou sexta",
            reference=date(2026, 6, 10),
            mode=DateParseMode.BOOKING,
        )
        assert result is not None
        assert result.needs_clarification
        assert result.clarification_reason == "multiple_dates"
        assert "amanh" in (result.clarification_prompt or "").lower()
        assert "sexta" in (result.clarification_prompt or "").lower()

    def test_amanha_ou_sexta_same_day_resolves(self):
        result = resolve_date_detailed(
            "Gostaria de agendar um corte masculino para amanhã ou sexta",
            reference=date(2026, 6, 11),
            mode=DateParseMode.BOOKING,
        )
        assert result is not None
        assert not result.needs_clarification
        assert result.iso == "2026-06-12"


class TestOperationalRouting:
    def test_contemporaneo_not_implicit_schedule(self):
        assert not has_implicit_scheduling_intent("Vocês fazem corte contemporaneo?")

    def test_cancel_horario_not_booking_conversation(self):
        messages = [HumanMessage(content="Preciso cancelar meu horário")]
        assert has_support_intent("Preciso cancelar meu horário")
        assert not is_booking_conversation(messages)
        assert resolve_triage_agent(messages, None) == "support"

    def test_atrasei_hoje_support(self):
        text = "Me atrasei hoje, posso chegar mais tarde?"
        assert has_support_intent(text)
        assert resolve_triage_agent([HumanMessage(content=text)], None) == "support"

    def test_faltei_ontem_support_with_date(self):
        text = "Faltei ontem no horário"
        assert has_support_intent(text)
        assert has_temporal_date_hint(text)
        assert resolve_triage_agent([HumanMessage(content=text)], None) == "support"

    def test_de_tarde_is_time_not_date(self):
        assert has_time_or_slot_question("prefiro de tarde")
        assert not has_temporal_date_hint("prefiro de tarde")


class TestAmbiguousWeekPhrases:
    def test_semana_que_vem_requires_clarification(self):
        detailed = resolve_date_detailed("semana que vem", reference=REF, mode=DateParseMode.BOOKING)
        assert detailed is not None
        assert detailed.needs_clarification
        assert detailed.clarification_reason == "week_without_weekday"
        assert resolve_date_from_text("semana que vem", reference=REF, mode=DateParseMode.BOOKING) is None

    def test_sexta_ou_sabado_requires_clarification(self):
        detailed = resolve_date_detailed("sexta ou sabado", reference=REF, mode=DateParseMode.BOOKING)
        assert detailed is not None
        assert detailed.clarification_reason == "multiple_weekdays"

    def test_essa_sexta_booking_clarifies_when_past(self):
        detailed = resolve_date_detailed("essa sexta", reference=REF, mode=DateParseMode.BOOKING)
        assert detailed is not None
        assert detailed.needs_clarification
        assert detailed.clarification_reason == "past_this_week"

    @pytest.mark.parametrize(
        "text",
        [
            "corte masculino para essa quinta ou quinta da semana que vem",
            "essa segunda ou segunda que vem",
            "sexta ou sexta da semana que vem",
            "essa quarta ou quarta da proxima semana",
            "essa quarta ou quarta da próxima semana",
        ],
    )
    def test_same_weekday_this_or_next_week_needs_clarification(self, text: str):
        ref = date(2026, 6, 9)
        detailed = resolve_date_detailed(text, reference=ref, mode=DateParseMode.BOOKING)
        assert detailed is not None
        assert detailed.needs_clarification
        assert detailed.clarification_reason == "multiple_dates"
        assert "qual dia você prefere" in (detailed.clarification_prompt or "").lower()
        assert resolve_date_from_text(text, reference=ref, mode=DateParseMode.BOOKING) is None


class TestThreadStaleBookingContext:
    def test_prefiro_sabado_overrides_stale_sexta(self, mocker):
        mocker.patch(
            "packages.scheduling.booking_executor.list_catalog_services",
            return_value=[{"id": "1", "name": "Coloração Completa", "duration_minutes": 120, "price": 200}],
        )
        messages = [
            HumanMessage(content="Quero mechas sexta"),
            HumanMessage(content="prefiro sabado"),
        ]
        date_iso, _, clarification = resolve_booking_context(
            messages,
            "22222222-2222-2222-2222-222222222222",
        )
        assert clarification is None
        assert date_iso == "2026-06-13"

    def test_time_only_keeps_booking_date_state(self):
        iso, clar = _resolve_booking_date_turn(
            "14:00",
            "Quero mechas sexta 14:00",
            reference=REF,
            booking_date="2026-06-12",
        )
        assert clar is None
        assert iso == "2026-06-12"

    def test_reset_phrase_clears_stale_combined(self):
        iso, clar = _resolve_booking_date_turn(
            "outro dia",
            "Quero mechas sexta",
            reference=REF,
            booking_date=None,
        )
        assert iso is None
        assert clar is not None


@pytest.mark.asyncio
async def test_semana_que_vem_does_not_list_slots(mocker):
    mocker.patch("packages.scheduling.booking_executor.set_tenant_context")
    mocker.patch(
        "packages.scheduling.booking_executor.list_catalog_services",
        return_value=[{"id": "1", "name": "Coloração Completa", "duration_minutes": 120, "price": 200}],
    )
    fetch = mocker.patch(
        "packages.scheduling.booking_executor.fetch_availability_summary",
        new_callable=mocker.AsyncMock,
    )
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}
    result = await run_scheduling_turn(
        [HumanMessage(content="Quero coloração semana que vem")],
        config,
    )
    assert result is not None
    assert "qual dia" in result.message.lower() or "semana que vem" in result.message.lower()
    fetch.assert_not_called()


class TestSupportMultiIntent:
    def test_cancel_and_reschedule_detected(self):
        text = "Quero cancelar sexta e remarcar domingo"
        assert has_cancel_and_reschedule_intent(text)

    def test_cancel_and_reschedule_handoff(self):
        result = run_support_turn(
            [HumanMessage(content="Preciso cancelar sexta e remarcar domingo")],
            "22222222-2222-2222-2222-222222222222",
        )
        assert result is not None
        assert "equipe" in result.message.lower()

    def test_ambiguous_support_still_runs(self, mocker):
        mocker.patch("packages.engine.support_executor.set_tenant_context")
        mocker.patch(
            "packages.engine.support_executor.search_kb",
        ).invoke.return_value = "[DADOS OFICIAIS DA BASE]\nCancelamento até 24h antes."
        result = run_support_turn(
            [HumanMessage(content="Quero cancelar semana que vem")],
            "22222222-2222-2222-2222-222222222222",
        )
        assert result is not None
        assert "qual dia" in result.message.lower() or "semana" in result.message.lower()
