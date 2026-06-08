"""Tests for conversation metrics telemetry."""
from langchain_core.messages import AIMessage, HumanMessage

from packages.engine.metrics.telemetry import extract_turn_tools_called


def test_extract_turn_tools_called_since_last_human():
    messages = [
        HumanMessage(content="old"),
        AIMessage(content="x", tool_calls=[{"name": "search_kb", "args": {}, "id": "1"}]),
        HumanMessage(content="quero agendar"),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "check_availability", "args": {}, "id": "2"},
                {"name": "book_time", "args": {}, "id": "3"},
            ],
        ),
    ]
    assert extract_turn_tools_called(messages) == ["check_availability", "book_time"]


def test_extract_turn_tools_called_empty_when_no_tools():
    messages = [
        HumanMessage(content="oi"),
        AIMessage(content="Olá!"),
    ]
    assert extract_turn_tools_called(messages) == []
