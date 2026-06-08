"""Graph-level routing: booking intents must reach scheduling without receptionist LLM."""
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from packages.engine.engine import triage_node
from packages.engine.routing import resolve_triage_agent, should_force_scheduling_route


class TestTriageNodeScheduling:
    def test_agendar_routes_scheduling_without_llm_path(self):
        state = {"messages": [HumanMessage(content="Quero agendar corte masculino dia 10 de junho")]}
        result = triage_node(state, {})
        assert result["active_agent"] == "scheduling"
        assert result["booking_active"] is True
        assert result["triage_source"] in ("keyword", "conversation")

    def test_temporal_colloquial_routes_scheduling(self):
        state = {"messages": [HumanMessage(content="Preciso ir semana que vem pra fazer um corte")]}
        result = triage_node(state, {})
        assert result["active_agent"] == "scheduling"
        assert result["booking_active"] is True

    def test_price_plus_schedule_routes_scheduling(self):
        state = {"messages": [HumanMessage(content="Quanto fica o corte e tem horário na sexta?")]}
        result = triage_node(state, {})
        assert result["active_agent"] == "scheduling"

    def test_greeting_does_not_force_scheduling(self):
        messages = [HumanMessage(content="Bom dia, tudo bem?")]
        assert not should_force_scheduling_route(messages)
        assert resolve_triage_agent(messages, None) == "receptionist"

    def test_booking_thread_sticky_scheduling(self):
        messages = [
            HumanMessage(content="Quero agendar coloração na sexta"),
            AIMessage(content="Qual horário prefere?"),
            HumanMessage(content="11987654320"),
        ]
        state = {
            "messages": messages,
            "active_agent": "scheduling",
            "booking_active": True,
        }
        result = triage_node(state, {})
        assert result["active_agent"] == "scheduling"
        assert result["triage_source"] == "sticky"


@pytest.mark.asyncio
async def test_receptionist_escape_delegates_to_scheduling(mocker):
    from packages.engine.engine import receptionist_node

    mock_sched = mocker.patch(
        "packages.engine.engine.scheduling_node",
        new_callable=mocker.AsyncMock,
        return_value={
            "messages": [AIMessage(content="Slots: 14:00")],
            "active_agent": "scheduling",
            "booking_active": True,
        },
    )
    mocker.patch("packages.engine.engine._invoke_agent")

    state = {"messages": [HumanMessage(content="Quero agendar corte na sexta")]}
    result = await receptionist_node(state, {})
    mock_sched.assert_awaited_once()
    assert result["active_agent"] == "scheduling"
