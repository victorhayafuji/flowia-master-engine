"""Tests for LangGraph engine triage and context helpers."""
from langchain_core.messages import AIMessage, HumanMessage

from packages.engine.engine import (
    _normalize_agent,
    get_safe_context,
    route_start,
    triage_node,
)


class TestNormalizeAgent:
    def test_sdr_maps_to_receptionist(self):
        assert _normalize_agent("sdr") == "receptionist"

    def test_lakehouse_query_maps_to_receptionist(self):
        assert _normalize_agent("lakehouse_query") == "receptionist"

    def test_scheduling_preserved(self):
        assert _normalize_agent("scheduling") == "scheduling"


class TestGetSafeContext:
    def test_empty_messages_returns_empty(self):
        assert get_safe_context([]) == []

    def test_merges_consecutive_same_role(self):
        msgs = [
            HumanMessage(content="oi"),
            HumanMessage(content="quero agendar"),
        ]
        result = get_safe_context(msgs)
        assert len(result) == 1
        assert "oi" in result[0].content
        assert "agendar" in result[0].content

    def test_orphan_tool_call_replaced(self):
        msgs = [
            HumanMessage(content="preco"),
            AIMessage(content="", tool_calls=[{"id": "1", "name": "search_kb", "args": {}}]),
        ]
        result = get_safe_context(msgs)
        assert result[-1].type == "ai"
        assert not getattr(result[-1], "tool_calls", None)

    def test_strips_leading_ai_messages(self):
        msgs = [
            AIMessage(content="ola"),
            HumanMessage(content="preco corte"),
        ]
        result = get_safe_context(msgs)
        assert result[0].type == "human"


class TestTriageNode:
    def test_keyword_routes_to_scheduling(self):
        state = {
            "messages": [HumanMessage(content="1")],
            "active_agent": "receptionist",
        }
        result = triage_node(state, {})
        assert result["active_agent"] == "scheduling"

    def test_keyword_routes_to_support(self):
        state = {
            "messages": [HumanMessage(content="cancelar")],
            "active_agent": "receptionist",
        }
        result = triage_node(state, {})
        assert result["active_agent"] == "support"

    def test_ambiguous_message_keeps_current_agent(self):
        state = {
            "messages": [HumanMessage(content="bom dia, tudo bem?")],
            "active_agent": "receptionist",
        }
        result = triage_node(state, {})
        assert result["active_agent"] == "receptionist"

    def test_agendar_phrase_routes_to_scheduling_on_first_message(self):
        state = {
            "messages": [HumanMessage(content="Quero agendar coloração na sexta")],
        }
        result = triage_node(state, {})
        assert result["active_agent"] == "scheduling"

    def test_booking_followup_escapes_receptionist(self):
        state = {
            "messages": [
                HumanMessage(content="Quero agendar coloração na sexta."),
                AIMessage(content="Qual tipo de coloração?"),
                HumanMessage(content="Vou querer fazer mechas."),
            ],
            "active_agent": "receptionist",
        }
        result = triage_node(state, {})
        assert result["active_agent"] == "scheduling"

    def test_keyword_routes_to_receptionist(self):
        state = {
            "messages": [HumanMessage(content="2")],
            "active_agent": "support",
        }
        result = triage_node(state, {})
        assert result["active_agent"] == "receptionist"


class TestRouteStart:
    def test_scheduling_agent_routes_to_scheduling_node(self):
        assert route_start({"active_agent": "scheduling"}) == "scheduling_node"

    def test_default_routes_to_receptionist(self):
        assert route_start({"active_agent": "receptionist"}) == "receptionist_node"
