"""Tests for mid-flow booking memory recovery."""
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from packages.scheduling.booking_flow_memory import (
    BookingFlowStep,
    build_date_confirmed_prompt,
    infer_booking_flow_step,
    is_date_confirmation_without_new_time,
    is_flow_digression,
    pick_recommended_time,
    try_flow_recovery_turn,
)

ORG = "22222222-2222-2222-2222-222222222222"


def test_infer_awaiting_time_when_date_and_service_saved():
    messages = [
        HumanMessage(content="Quero corte masculino amanhã"),
        AIMessage(content="Para quarta-feira, 10/06, Com Maria, estes horários estão livres:\n  • 08:00"),
    ]
    step = infer_booking_flow_step(
        messages,
        booking_date="2026-06-10",
        booking_service="Corte Masculino",
    )
    assert step == BookingFlowStep.AWAITING_TIME


def test_recommendation_question_is_digression():
    assert is_flow_digression(
        "Não sei, qual você me recomenda mais?",
        BookingFlowStep.AWAITING_TIME,
    )


def test_explicit_time_is_not_digression():
    assert not is_flow_digression("08:00", BookingFlowStep.AWAITING_TIME)


def test_pick_recommended_time_prefers_mid_morning():
    assert pick_recommended_time(["08:00", "11:00", "14:00", "17:00"]) == "11:00"
    assert pick_recommended_time(["08:00", "17:15"]) == "08:00"


def test_date_confirmation_without_new_time_after_slots(mocker):
    # Freeze today to a Wednesday so "essa quinta" resolves to the next-day
    # Thursday deterministically on any clock (CI-safe). Both booking_flow_memory
    # and booking_executor read date.today() in this path (is_date_reaffirmation).
    class _FixedToday(__import__("datetime").date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 10)  # Wednesday

    mocker.patch("packages.scheduling.booking_flow_memory.date", _FixedToday)
    mocker.patch("packages.scheduling.booking_executor.date", _FixedToday)

    date_iso = "2026-06-11"  # Thursday == "essa quinta" relative to frozen today
    assert is_date_confirmation_without_new_time(
        "Certo, podemos marcar para essa quinta então",
        date_iso,
    )
    assert not is_date_confirmation_without_new_time("08:00", date_iso)


def test_build_date_confirmed_prompt_is_short():
    msg = build_date_confirmed_prompt("2026-06-11", "Corte Masculino")
    assert "Perfeito!" in msg
    assert "Qual horário" in msg
    assert "08:00" not in msg


def test_infer_uses_explicit_booking_step_when_provided():
    step = infer_booking_flow_step(
        [],
        booking_date="2026-06-10",
        booking_service="Corte Masculino",
        booking_step="awaiting_patient",
    )
    assert step == BookingFlowStep.AWAITING_PATIENT


def test_date_choice_opinion_is_digression_at_need_date():
    assert is_flow_digression(
        "Qual você acha melhor?",
        BookingFlowStep.NEED_DATE,
    )


def test_date_choice_opinion_question_detected():
    from packages.scheduling.booking_flow_memory import is_date_choice_opinion_question

    assert is_date_choice_opinion_question("Qual você acha melhor?")
    assert not is_date_choice_opinion_question("Qual horário você prefere?")


@pytest.mark.asyncio
async def test_flow_recovery_relists_with_recommendation(mocker):
    mocker.patch(
        "packages.scheduling.booking_executor.fetch_availability_summary",
        new_callable=mocker.AsyncMock,
        return_value="Horários para 'Corte Masculino' em 2026-06-10:\n- Maria Silva: 08:00, 17:15",
    )

    messages = [
        HumanMessage(content="Pode ser amanhã"),
        AIMessage(
            content=(
                "Para quarta-feira, 10/06, Com Maria Silva, estes horários estão livres:\n"
                "  • 08:00   • 17:15\n\nQual horário funciona melhor para você?"
            )
        ),
        HumanMessage(content="Não sei, qual você me recomenda mais?"),
    ]
    config = {"configurable": {"org_id": ORG}}
    result = await try_flow_recovery_turn(
        messages,
        config,
        booking_date="2026-06-10",
        booking_service="Corte Masculino",
    )
    assert result is not None
    assert "sugiro" in result.message.lower()
    assert "08:00" in result.message
    assert "10/06" in result.message
    assert "informe serviço" not in result.message.lower()
