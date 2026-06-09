"""LangGraph routing edges."""
from __future__ import annotations

# ==========================================
# 6. LÓGICA DE TRANSIÇÃO (EDGES)
# ==========================================
from langgraph.graph import END

from packages.engine.graph.state import AgentState, _normalize_agent


def route_start(state: AgentState):
    agent = _normalize_agent(state.get("active_agent"))
    if agent == "scheduling":
        return "scheduling_node"
    if agent == "support":
        return "support_node"
    return "receptionist_node"


def should_continue(state: AgentState):
    last_msg = state["messages"][-1]
    if getattr(last_msg, "tool_calls", None):
        return "tools"
    return END


def route_after_tools(state: AgentState):
    agent = _normalize_agent(state.get("active_agent"))
    if agent == "scheduling":
        return "scheduling_node"
    if agent == "support":
        return "support_node"
    return "receptionist_node"

