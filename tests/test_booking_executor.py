"""Tests for deterministic booking executor."""
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from packages.scheduling.booking_executor import (
    collect_booking_intent,
    is_availability_followup,
    run_scheduling_turn,
)


@pytest.fixture(autouse=True)
def _mock_catalog(mocker):
    mocker.patch(
        "packages.scheduling.booking_executor.list_catalog_services",
        return_value=[
            {"id": "1", "name": "Corte Masculino", "duration_minutes": 45, "price": 80},
            {"id": "2", "name": "Corte Feminino", "duration_minutes": 60, "price": 120},
        ],
    )


def test_collect_intent_from_full_message():
    msg = (
        "Quero agendar um corte masculino para quarta dia 10 de junho as 11:00, "
        "meu nome e Joao Silva, telefone 11987654323"
    )
    intent = collect_booking_intent(
        [HumanMessage(content=msg)],
        "22222222-2222-2222-2222-222222222222",
    )
    assert intent is not None
    assert intent.date_iso == "2026-06-10"
    assert intent.time_hhmm == "11:00"
    assert intent.patient_name == "Joao Silva"
    assert intent.patient_phone == "11987654323"
    assert "Corte Masculino" in intent.service_query


def test_collect_intent_missing_time_returns_none():
    msg = "Quero agendar corte masculino dia 10 de junho, Joao Silva, 11987654323"
    intent = collect_booking_intent(
        [HumanMessage(content=msg)],
        "22222222-2222-2222-2222-222222222222",
    )
    assert intent is None


@pytest.mark.asyncio
async def test_run_scheduling_turn_lists_slots_without_time(mocker):
    mocker.patch(
        "packages.scheduling.booking_executor.fetch_availability_summary",
        new_callable=mocker.AsyncMock,
        return_value="Horários para 'Corte Masculino' em 2026-06-10:\n- Maria: 13:00",
    )
    mocker.patch("packages.scheduling.booking_executor.set_tenant_context")
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}
    msg = "Quero corte masculino dia 10 de junho"
    result = await run_scheduling_turn([HumanMessage(content=msg)], config)
    assert result is not None
    assert "13:00" in result.message
    assert "Qual horário" in result.message


@pytest.mark.asyncio
async def test_followup_outro_horario_lists_slots(mocker):
    mocker.patch(
        "packages.scheduling.booking_executor.fetch_availability_summary",
        new_callable=mocker.AsyncMock,
        return_value="Horários para 'Corte Masculino' em 2026-06-10:\n- Maria: 13:00, 14:00",
    )
    mocker.patch("packages.scheduling.booking_executor.set_tenant_context")
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}
    messages = [
        HumanMessage(content="Quero corte masculino dia 10 de junho as 11:00"),
        AIMessage(content="Não há horários disponíveis para 'Corte Masculino' no dia 10 de junho."),
        HumanMessage(content="Sim, tem algum outro horario?"),
    ]
    result = await run_scheduling_turn(messages, config)
    assert result is not None
    assert "13:00" in result.message
    assert result.booking_service == "Corte Masculino"


@pytest.mark.asyncio
async def test_time_only_turn_with_contact_in_history(mocker):
    mocker.patch(
        "packages.scheduling.booking_executor.fetch_availability_summary",
        new_callable=mocker.AsyncMock,
    )
    mocker.patch(
        "packages.scheduling.booking_executor.execute_booking",
        new_callable=mocker.AsyncMock,
        return_value="SUCESSO! Agendamento confirmado.",
    )
    mocker.patch("packages.scheduling.booking_executor.set_tenant_context")
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}
    messages = [
        HumanMessage(content="Quero corte masculino dia 10 de junho"),
        AIMessage(content="Horarios: 14:00"),
        HumanMessage(content="Meu nome e Pedro Silva, telefone 11987654353"),
        AIMessage(content="Qual horario?"),
        HumanMessage(content="14:00"),
    ]
    result = await run_scheduling_turn(
        messages,
        config,
        booking_date="2026-06-10",
        booking_service="Corte Masculino",
    )
    assert result is not None
    assert "SUCESSO" in result.message
    assert result.booking_service == "Corte Masculino"


@pytest.mark.asyncio
async def test_time_only_turn_asks_contact_when_missing(mocker):
    mocker.patch("packages.scheduling.booking_executor.set_tenant_context")
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}
    messages = [
        HumanMessage(content="Quero corte masculino dia 10 de junho"),
        HumanMessage(content="14:00"),
    ]
    result = await run_scheduling_turn(
        messages,
        config,
        booking_date="2026-06-10",
        booking_service="Corte Masculino",
    )
    assert result is not None
    assert "nome" in result.message.lower()
    assert "telefone" in result.message.lower()


@pytest.mark.asyncio
async def test_missing_service_lists_catalog(mocker):
    mocker.patch("packages.scheduling.booking_executor.set_tenant_context")
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}
    result = await run_scheduling_turn(
        [HumanMessage(content="Quero agendar")],
        config,
    )
    assert result is not None
    assert "Corte Masculino" in result.message


@pytest.mark.asyncio
async def test_mechas_sexta_lists_slots(mocker):
    mocker.patch(
        "packages.scheduling.booking_executor.fetch_availability_summary",
        new_callable=mocker.AsyncMock,
        return_value="Horários para 'Coloração Completa' em 2026-06-12:\n- Maria: 14:00, 15:00",
    )
    mocker.patch("packages.scheduling.booking_executor.set_tenant_context")
    mocker.patch(
        "packages.scheduling.booking_executor.list_catalog_services",
        return_value=[
            {"id": "1", "name": "Coloração Completa", "duration_minutes": 120, "price": 200},
        ],
    )
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}

    class _FixedToday(__import__("datetime").date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 7)

    mocker.patch("packages.scheduling.booking_executor.date", _FixedToday)
    result = await run_scheduling_turn(
        [HumanMessage(content="Quero mechas sexta")],
        config,
    )
    assert result is not None
    assert "14:00" in result.message
    assert result.booking_date == "2026-06-12"


def test_availability_followup_sim_without_time():
    assert is_availability_followup("sim")


def test_availability_followup_sim_with_time_is_not_bare_ack():
    assert not is_availability_followup("14:00", has_time_in_message=True)
    assert not is_availability_followup("sim", has_time_in_message=True)


def test_availability_followup_phrase_with_time():
    assert is_availability_followup("tem outro horario?", has_time_in_message=True)
