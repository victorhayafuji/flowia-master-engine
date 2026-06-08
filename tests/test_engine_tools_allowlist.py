"""Tests for run_tools agent allowlist."""

import pytest
from langchain_core.messages import AIMessage

from packages.engine.engine import run_tools


@pytest.mark.asyncio
async def test_scheduling_blocks_query_lakehouse():
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "query_lakehouse",
                        "args": {"query": "SELECT 1"},
                        "id": "call_1",
                    }
                ],
            )
        ],
        "active_agent": "scheduling",
        "booking_active": True,
        "sender_id": "test-sender",
    }
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}

    result = await run_tools(state, config)
    assert result["messages"][0].content == "Ferramenta não permitida."
    assert result.get("handoff_requested") is False


@pytest.mark.asyncio
async def test_scheduling_blocks_handoff_during_booking():
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "request_human_handoff",
                        "args": {"reason": "test"},
                        "id": "call_2",
                    }
                ],
            )
        ],
        "active_agent": "scheduling",
        "booking_active": True,
        "sender_id": "test-sender",
    }
    config = {"configurable": {"org_id": "22222222-2222-2222-2222-222222222222"}}

    result = await run_tools(state, config)
    assert "não permitida" in result["messages"][0].content.lower()
    assert result.get("handoff_requested") is False
