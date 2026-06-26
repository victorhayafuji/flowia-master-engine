"""scheduling_node roteia intenção de reagendar direto ao LLM (tool reschedule_time),
sem deixar o executor determinístico tratar como novo booking."""
import pytest
from langchain_core.messages import AIMessage, HumanMessage

import packages.engine.graph.nodes as nodes


def _patch_llm_only(monkeypatch):
    """Faz o nó ir ao LLM sem tocar DB; falha se o executor determinístico rodar."""
    monkeypatch.setattr(nodes, "get_salon_name", lambda org_id: "Salão X")
    called = {}

    def fake_invoke(state, config, agent):
        called["agent"] = agent
        return {"messages": [], "active_agent": agent}

    monkeypatch.setattr(nodes, "_invoke_agent", fake_invoke)

    async def boom(*a, **k):
        raise AssertionError("run_scheduling_turn não deveria ser chamado para reagendar")

    monkeypatch.setattr(nodes, "run_scheduling_turn", boom)
    return called


@pytest.mark.asyncio
async def test_reschedule_intent_bypasses_deterministic_to_llm(monkeypatch):
    called = _patch_llm_only(monkeypatch)
    state = {"messages": [HumanMessage(content="quero remarcar para sexta às 14h")]}
    result = await nodes.scheduling_node(state, {"configurable": {"org_id": "org-1"}})
    assert called["agent"] == "scheduling"
    assert result["scheduling_path"] == "llm"


@pytest.mark.asyncio
async def test_reschedule_multiturn_stays_in_llm(monkeypatch):
    """2ª mensagem ("sexta às 14h") sem verbo de ação, mas 'remarcar' está na janela
    recente → continua no LLM (não cai no executor de novo booking)."""
    called = _patch_llm_only(monkeypatch)
    state = {
        "messages": [
            HumanMessage(content="quero remarcar"),
            AIMessage(content="Claro! Para qual data e horário?"),
            HumanMessage(content="sexta às 14h"),
        ]
    }
    result = await nodes.scheduling_node(state, {"configurable": {"org_id": "org-1"}})
    assert called["agent"] == "scheduling"
    assert result["scheduling_path"] == "llm"
