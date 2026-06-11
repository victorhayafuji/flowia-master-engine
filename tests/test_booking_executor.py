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


@pytest.fixture(autouse=True)
def _freeze_today(mocker):
    """Freeze date.today to a fixed workday so colloquial/partial dates (ex: "dia 10
    de junho") resolve deterministically on any clock (CI-safe). Tests needing a
    specific "today" re-patch booking_executor.date in the test body, overriding this."""
    class _FixedToday(__import__("datetime").date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 7)

    mocker.patch("packages.scheduling.booking_executor.date", _FixedToday)


def test_extract_patient_name_with_particle_and_phone():
    from packages.scheduling.booking_executor import extract_patient_name

    name = extract_patient_name("Victor da silva, 11988765432")
    assert name == "Victor da silva"


def test_extract_patient_name_prefers_full_name_over_particle_tail():
    from packages.scheduling.booking_executor import extract_patient_name

    combined = (
        "Quero corte amanha pode marcar 08:00, gostei das 11:00, "
        "Victor da Silva, 11989876543"
    )
    assert extract_patient_name("Victor da Silva, 11989876543") == "Victor da Silva"
    assert extract_patient_name(combined) != "da Silva"


def test_collect_intent_uses_checkpoint_date_not_stale_amanha(mocker):
    class _FixedToday(__import__("datetime").date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 22)

    mocker.patch("packages.scheduling.booking_executor.date", _FixedToday)
    messages = [
        HumanMessage(content="Quero corte masculino amanhã"),
        HumanMessage(content="pode marcar para 08:00"),
        HumanMessage(content="Victor da Silva, 11989876543"),
    ]
    intent = collect_booking_intent(
        messages,
        "22222222-2222-2222-2222-222222222222",
        booking_date="2026-06-11",
        booking_service="Corte Masculino",
        booking_time="08:00",
    )
    assert intent is not None
    assert intent.date_iso == "2026-06-11"
    assert intent.time_hhmm == "08:00"
    assert intent.patient_name == "Victor da Silva"
    assert intent.patient_phone == "11989876543"


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
    assert result.booking_time == "14:00"


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


@pytest.mark.asyncio
async def test_coloracao_june12_followup_after_receptionist(mocker):
    mocker.patch(
        "packages.scheduling.booking_executor.fetch_availability_summary",
        new_callable=mocker.AsyncMock,
        return_value="Horários para 'Coloração Completa' em 2026-06-12:\n- Ana Costa: 14:00, 15:00",
    )
    mocker.patch("packages.scheduling.booking_executor.set_tenant_context")
    mocker.patch(
        "packages.scheduling.booking_executor.list_catalog_services",
        return_value=[
            {"id": "1", "name": "Coloração Completa", "duration_minutes": 120, "price": 250},
        ],
    )
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}

    class _FixedToday(__import__("datetime").date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 7)

    mocker.patch("packages.scheduling.booking_executor.date", _FixedToday)
    messages = [
        HumanMessage(content="Vocês fazem coloração? Qual o preço?"),
        AIMessage(
            content="Sim! Fazemos coloração. Coloração Completa: 120 min, R$ 250,00 Quer agendar um horário?"
        ),
        HumanMessage(content="Sim, tem horário para 12 de junho?"),
    ]
    result = await run_scheduling_turn(messages, config)
    assert result is not None
    assert result.booking_date == "2026-06-12"
    assert result.booking_service == "Coloração Completa"
    assert "14:00" in result.message


def test_availability_followup_sim_without_time():
    assert is_availability_followup("sim")


def test_availability_followup_sim_with_date_question():
    assert is_availability_followup("Sim, tem horário para 12 de junho?")


def test_availability_followup_sim_with_time_is_not_bare_ack():
    assert not is_availability_followup("14:00", has_time_in_message=True)
    assert not is_availability_followup("sim", has_time_in_message=True)


def test_availability_followup_phrase_with_time():
    assert is_availability_followup("tem outro horario?", has_time_in_message=True)


@pytest.mark.asyncio
async def test_manicure_amanha_lists_slots(mocker):
    mocker.patch(
        "packages.scheduling.booking_executor.fetch_availability_summary",
        new_callable=mocker.AsyncMock,
        return_value="Horários para 'Manicure' em 2026-06-08:\n- Maria: 09:00, 10:00",
    )
    mocker.patch("packages.scheduling.booking_executor.set_tenant_context")
    mocker.patch(
        "packages.scheduling.booking_executor.list_catalog_services",
        return_value=[
            {"id": "1", "name": "Manicure", "duration_minutes": 40, "price": 45},
        ],
    )
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}

    class _FixedToday(__import__("datetime").date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 7)

    mocker.patch("packages.scheduling.booking_executor.date", _FixedToday)
    result = await run_scheduling_turn(
        [HumanMessage(content="Quero agendar manicure amanhã")],
        config,
    )
    assert result is not None
    assert result.booking_date == "2026-06-08"
    assert result.booking_service == "Manicure"
    assert "09:00" in result.message
    assert "Para qual data" not in result.message


@pytest.mark.asyncio
async def test_service_only_reply_lists_slots_with_saved_date(mocker):
    """Regression: user picks catalog name after date was saved (Chat Test screenshot)."""
    mocker.patch(
        "packages.scheduling.booking_executor.fetch_availability_summary",
        new_callable=mocker.AsyncMock,
        return_value="Horários para 'Corte Masculino' em 2026-06-08:\n- Maria: 09:00, 10:00",
    )
    mocker.patch("packages.scheduling.booking_executor.set_tenant_context")
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}

    class _FixedToday(__import__("datetime").date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 7)

    mocker.patch("packages.scheduling.booking_executor.date", _FixedToday)
    messages = [
        HumanMessage(content="Quero agendar amanhã"),
        AIMessage(content="Qual serviço deseja agendar? Temos: Corte Masculino."),
        HumanMessage(content="Corte masculino"),
    ]
    result = await run_scheduling_turn(
        messages,
        config,
        booking_date="2026-06-08",
    )
    assert result is not None
    assert result.booking_service == "Corte Masculino"
    assert "09:00" in result.message
    assert "informe serviço" not in result.message.lower()


@pytest.mark.asyncio
async def test_date_clarification_question_relists_slots_with_saved_context(mocker):
    mocker.patch(
        "packages.scheduling.booking_executor.fetch_availability_summary",
        new_callable=mocker.AsyncMock,
        return_value="Horários para 'Corte Masculino' em 2026-06-11:\n- Maria Silva: 09:00, 10:00",
    )
    mocker.patch("packages.scheduling.booking_executor.set_tenant_context")
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}
    messages = [
        HumanMessage(content="Quero marcar um corte masculino para amanhã"),
        AIMessage(content="Com Maria Silva, estes horários estão livres:\n- 09:00\n- 10:00"),
        HumanMessage(content="Mas para qual dia?"),
    ]
    result = await run_scheduling_turn(
        messages,
        config,
        booking_date="2026-06-11",
        booking_service="Corte Masculino",
    )
    assert result is not None
    assert "09:00" in result.message
    assert "informe serviço" not in result.message.lower()


@pytest.mark.asyncio
async def test_dual_relative_date_asks_which_day(mocker):
    mocker.patch("packages.scheduling.booking_executor.set_tenant_context")
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}

    class _FixedToday(__import__("datetime").date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 10)

    mocker.patch("packages.scheduling.booking_executor.date", _FixedToday)
    result = await run_scheduling_turn(
        [HumanMessage(content="Quero marcar um corte masculino para amanhã ou depois de amanhã")],
        config,
    )
    assert result is not None
    assert result.booking_service == "Corte Masculino"
    assert result.booking_date is None
    assert "qual dia você prefere" in result.message.lower()
    assert "amanhã" in result.message.lower() or "amanha" in result.message.lower()


@pytest.mark.asyncio
async def test_amanha_ou_sexta_asks_which_day_not_slots(mocker):
    mocker.patch("packages.scheduling.booking_executor.set_tenant_context")
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}

    class _FixedToday(__import__("datetime").date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 10)

    mocker.patch("packages.scheduling.booking_executor.date", _FixedToday)
    result = await run_scheduling_turn(
        [HumanMessage(content="Gostaria de agendar um corte masculino para amanhã ou sexta")],
        config,
    )
    assert result is not None
    assert result.booking_service == "Corte Masculino"
    assert result.booking_date is None
    assert "qual dia você prefere" in result.message.lower()
    assert "08:00" not in result.message


@pytest.mark.asyncio
async def test_recommendation_digression_recovers_mid_flow(mocker):
    mocker.patch(
        "packages.scheduling.booking_executor.fetch_availability_summary",
        new_callable=mocker.AsyncMock,
        return_value="Horários para 'Corte Masculino' em 2026-06-10:\n- Maria Silva: 08:00, 17:15",
    )
    mocker.patch("packages.scheduling.booking_executor.set_tenant_context")
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}
    messages = [
        HumanMessage(content="Quero marcar corte masculino para amanhã"),
        AIMessage(
            content=(
                "Para quarta-feira, 10/06, Com Maria Silva, estes horários estão livres:\n"
                "  • 08:00   • 17:15\n\nQual horário funciona melhor para você?"
            )
        ),
        HumanMessage(content="Não sei, qual você me recomenda mais?"),
    ]
    result = await run_scheduling_turn(
        messages,
        config,
        booking_date="2026-06-10",
        booking_service="Corte Masculino",
    )
    assert result is not None
    assert "sugiro" in result.message.lower()
    assert "08:00" in result.message
    assert "informe serviço" not in result.message.lower()


@pytest.mark.asyncio
async def test_amanha_ou_sexta_opinion_question_reasks_day(mocker):
    mocker.patch("packages.scheduling.booking_executor.set_tenant_context")
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}

    class _FixedToday(__import__("datetime").date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 9)

    mocker.patch("packages.scheduling.booking_executor.date", _FixedToday)
    messages = [
        HumanMessage(content="Gostaria de agendar um corte masculino para amanhã ou sexta"),
        AIMessage(
            content=(
                "Qual dia você prefere: amanhã (quarta-feira, 10/06) "
                "ou sexta (sexta-feira, 12/06)?"
            )
        ),
        HumanMessage(content="Qual você acha melhor?"),
    ]
    result = await run_scheduling_turn(
        messages,
        config,
        booking_service="Corte Masculino",
    )
    assert result is not None
    assert result.booking_date is None
    assert result.booking_service == "Corte Masculino"
    assert "escolha" in result.message.lower() or "prefere" in result.message.lower()
    assert "10/06" in result.message
    assert "12/06" in result.message
    assert "08:00" not in result.message
    assert "vamos continuar" not in result.message.lower()


@pytest.mark.asyncio
async def test_service_after_date_pick_does_not_reask_day(mocker):
    """Regression: explicit date pick must survive a later service-only reply."""
    mocker.patch(
        "packages.scheduling.booking_executor.fetch_availability_summary",
        new_callable=mocker.AsyncMock,
        return_value="Horários para 'Corte Masculino' em 2026-06-10:\n- Maria Silva: 08:00, 17:15",
    )
    mocker.patch("packages.scheduling.booking_executor.set_tenant_context")
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}

    class _FixedToday(__import__("datetime").date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 9)

    mocker.patch("packages.scheduling.booking_executor.date", _FixedToday)
    messages = [
        HumanMessage(content="Gostaria de agendar um corte masculino para amanhã ou sexta"),
        AIMessage(
            content=(
                "Qual dia você prefere: amanhã (quarta-feira, 10/06) "
                "ou sexta (sexta-feira, 12/06)?"
            )
        ),
        HumanMessage(content="Qual você acha melhor?"),
        AIMessage(content="Os dois dias funcionam! A escolha fica com você — qual prefere?"),
        HumanMessage(content="Pode ser amanhã"),
        AIMessage(content="Certo! Para quarta-feira, 10/06, qual serviço você gostaria de fazer?"),
        HumanMessage(content="Corte Masculino"),
    ]
    result = await run_scheduling_turn(
        messages,
        config,
        booking_date="2026-06-10",
        booking_service="Corte Masculino",
    )
    assert result is not None
    assert result.booking_date == "2026-06-10"
    assert result.booking_service == "Corte Masculino"
    assert "08:00" in result.message
    assert "qual dia você prefere" not in result.message.lower()


@pytest.mark.asyncio
async def test_thanks_after_confirm_does_not_list_slots(mocker):
    mocker.patch("packages.scheduling.booking_executor.set_tenant_context")
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}
    messages = [
        HumanMessage(content="Quero corte masculino dia 12 de junho"),
        AIMessage(
            content=(
                "Pronto! Seu horário está confirmado para João: "
                "'Corte Masculino' em 12/06/2026 11:00."
            )
        ),
        HumanMessage(content="Otimo, obrigado!"),
    ]
    result = await run_scheduling_turn(messages, config, booking_date="2026-06-12", booking_service="Corte Masculino")
    assert result is not None
    assert "Por nada" in result.message
    assert "11:00" not in result.message or "horários" not in result.message.lower()


@pytest.mark.asyncio
async def test_date_confirmation_after_slots_uses_short_prompt(mocker):
    fetch = mocker.patch(
        "packages.scheduling.booking_executor.fetch_availability_summary",
        new_callable=mocker.AsyncMock,
    )
    mocker.patch("packages.scheduling.booking_executor.set_tenant_context")
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}

    class _FixedToday(__import__("datetime").date):
        @classmethod
        def today(cls):
            return cls(2026, 6, 9)

    mocker.patch("packages.scheduling.booking_executor.date", _FixedToday)
    mocker.patch("packages.scheduling.booking_flow_memory.date", _FixedToday)

    messages = [
        HumanMessage(content="Quero corte masculino essa quinta ou quinta da semana que vem"),
        AIMessage(
            content=(
                "Qual dia você prefere: essa quinta (quinta-feira, 11/06) "
                "ou quinta da semana que vem (quinta-feira, 18/06)?"
            )
        ),
        HumanMessage(content="Certo, podemos marcar para essa quinta então"),
        AIMessage(
            content=(
                "Para quinta-feira, 11/06, Com Maria Silva, estes horários estão livres:\n"
                "  • 08:00   • 11:00   • 14:00\n\nQual horário funciona melhor para você?"
            )
        ),
        HumanMessage(content="Certo, podemos marcar para essa quinta então"),
    ]
    result = await run_scheduling_turn(
        messages,
        config,
        booking_date="2026-06-11",
        booking_service="Corte Masculino",
    )
    assert result is not None
    assert "Perfeito!" in result.message
    assert "Qual horário" in result.message
    assert "08:00" not in result.message
    fetch.assert_not_called()
