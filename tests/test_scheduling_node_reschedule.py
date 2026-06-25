"""scheduling_node roteia intenção de reagendar direto ao LLM (tool reschedule_time),
sem deixar o executor determinístico tratar como novo booking."""
import pytest
from langchain_core.messages import HumanMessage

import packages.engine.graph.nodes as nodes


@pytest.mark.asyncio
async def test_reschedule_intent_bypasses_deterministic_to_llm(monkeypatch):
    monkeypatch.setattr(nodes, "get_salon_name", lambda org_id: "Salão X")

    called = {}

    def fake_invoke(state, config, agent):
        called["agent"] = agent
        return {"messages": [], "active_agent": agent}

    monkeypatch.setattr(nodes, "_invoke_agent", fake_invoke)

    async def boom(*a, **k):  # executor determinístico não deve rodar para reagendar
        raise AssertionError("run_scheduling_turn não deveria ser chamado")

    monkeypatch.setattr(nodes, "run_scheduling_turn", boom)

    state = {"messages": [HumanMessage(content="quero remarcar para sexta às 14h")]}
    config = {"configurable": {"org_id": "org-1"}}

    result = await nodes.scheduling_node(state, config)

    assert called["agent"] == "scheduling"
    assert result["scheduling_path"] == "llm"
