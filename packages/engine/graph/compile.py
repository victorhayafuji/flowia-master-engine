"""Build and compile master LangGraph workflow."""

from langgraph.graph import START, StateGraph

from packages.engine.graph.edges import route_after_tools, route_start, should_continue
from packages.engine.graph.nodes import (
    receptionist_node,
    run_tools,
    scheduling_node,
    support_node,
    triage_node,
)
from packages.engine.graph.state import AgentState

workflow = StateGraph(AgentState)

workflow.add_node("triage_node", triage_node)
workflow.add_node("receptionist_node", receptionist_node)
workflow.add_node("scheduling_node", scheduling_node)
workflow.add_node("support_node", support_node)
workflow.add_node("tools", run_tools)

workflow.add_edge(START, "triage_node")
workflow.add_conditional_edges("triage_node", route_start)

workflow.add_conditional_edges("receptionist_node", should_continue)
workflow.add_conditional_edges("scheduling_node", should_continue)
workflow.add_conditional_edges("support_node", should_continue)

workflow.add_conditional_edges("tools", route_after_tools)

def compile_master_engine(checkpointer):
    """Compile the LangGraph workflow with the given checkpointer."""
    return workflow.compile(checkpointer=checkpointer)
