import logging
from collections.abc import Sequence
from functools import lru_cache
from typing import Any, Literal, TypedDict

try:
    from typing import Annotated
except ImportError:
    from typing import Annotated

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from packages.auth_core.config import settings
from packages.engine.context import get_salon_name
from packages.engine.prompts import (
    build_lakehouse_prompt,
    build_receptionist_prompt,
    build_scheduling_prompt,
    build_support_prompt,
)
from packages.engine.tools import get_lakehouse_schema, query_lakehouse, request_human_handoff, search_kb
from packages.scheduling.tools import book_time, check_availability

logger = logging.getLogger(__name__)

# ==========================================
# 1. ESTADO DO GRAFO
# ==========================================
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    sender_id: str
    handoff_requested: bool
    company_name: str | None
    lead_name: str | None
    email: str | None
    bant_status: dict[str, Any]
    active_agent: str | None
    last_node: str | None
    audit_flag: str | None
    lgpd_shown: bool
    first_contact_at: float
    messages_count: int

# ==========================================
# 2. FERRAMENTAS POR AGENTE
# ==========================================
receptionist_tools = [search_kb, request_human_handoff]
support_tools = [search_kb, request_human_handoff]
scheduling_tools = [search_kb, check_availability, book_time, request_human_handoff]
lakehouse_tools = [get_lakehouse_schema, query_lakehouse]

llm_base = ChatGoogleGenerativeAI(
    model=settings.MODEL_NAME,
    temperature=0.0,
    google_api_key=settings.GOOGLE_API_KEY,
)


@lru_cache(maxsize=32)
def _build_agent_llm(salon_name: str, agent: str):
    prompts = {
        "receptionist": build_receptionist_prompt(salon_name),
        "support": build_support_prompt(salon_name),
        "scheduling": build_scheduling_prompt(salon_name),
        "lakehouse_query": build_lakehouse_prompt(salon_name),
    }
    tool_sets = {
        "receptionist": receptionist_tools,
        "support": support_tools,
        "scheduling": scheduling_tools,
        "lakehouse_query": lakehouse_tools,
    }
    system = prompts[agent]
    tools = tool_sets[agent]
    prompt = ChatPromptTemplate.from_messages(
        [("system", system), MessagesPlaceholder(variable_name="messages")]
    )
    return prompt | llm_base.bind_tools(tools)


def _org_id_from_config(config: RunnableConfig | None) -> str | None:
    if not config:
        return None
    configurable = config.get("configurable") or {}
    return configurable.get("org_id")


def _normalize_agent(agent: str | None) -> str:
    if agent in ("sdr", "receptionist", None):
        return "receptionist"
    if agent == "lakehouse_query":
        return "receptionist"
    return agent or "receptionist"


def get_safe_context(messages: list, max_messages: int = 50) -> list:
    """Sanitizador Minimalista para Gemini."""
    if not messages:
        return []
    processed = []
    for i, m in enumerate(messages):
        if m.type == "ai" and hasattr(m, "tool_calls") and m.tool_calls:
            if i + 1 >= len(messages) or messages[i + 1].type != "tool":
                processed.append(AIMessage(content=str(m.content) or "Processando..."))
                continue
        processed.append(m)

    safe_history = []
    for msg in processed:
        role = "user" if msg.type in ["human", "tool"] else "model"
        if not safe_history:
            if role == "user":
                safe_history.append(msg)
            continue

        last_role = "user" if safe_history[-1].type in ["human", "tool"] else "model"
        if role == last_role:
            new_content = f"{str(safe_history[-1].content)}\n{str(msg.content)}"
            if role == "user":
                safe_history[-1] = HumanMessage(content=new_content)
            else:
                safe_history[-1] = AIMessage(content=new_content)
        else:
            safe_history.append(msg)

    sequence_log = " -> ".join([("U" if (m.type in ["human", "tool"]) else "M") for m in safe_history])
    logger.info(f"AUDIT SEQ: {sequence_log}")

    final_history = safe_history[-max_messages:]
    while final_history and final_history[0].type not in ["human", "tool"]:
        final_history.pop(0)

    return final_history


# ==========================================
# 4. NOS DO GRAFO (AGENTES)
# ==========================================
class RouteOutput(BaseModel):
    destination: Literal["receptionist", "support", "scheduling"] = Field(
        description="receptionist for prices/services info, support for policies, scheduling for booking"
    )


def triage_node(state: AgentState, config: RunnableConfig):
    """Nó inicial (Triagem). Analisa a intenção do cliente do salão."""
    current_agent = _normalize_agent(state.get("active_agent"))

    if current_agent:
        human_msgs = [m for m in state["messages"] if m.type == "human"]
        if not human_msgs:
            return {"active_agent": current_agent}

        last_human = str(human_msgs[-1].content).lower().strip()

        if last_human in ["1", "agendar", "marcar", "agendamento", "horario", "horário"]:
            return {"active_agent": "scheduling"}
        if last_human in ["2", "duvida", "dúvida", "preco", "preço", "valor", "servico", "serviço"]:
            return {"active_agent": "receptionist"}
        if last_human in ["3", "politica", "política", "cancelar", "atraso", "pagamento"]:
            return {"active_agent": "support"}

        return {"active_agent": current_agent}

    logger.info("Triage Node: Analisando intenção do primeiro contato...")

    context = get_safe_context(state["messages"])
    if not context:
        return {"active_agent": "receptionist"}

    router_llm = llm_base.with_structured_output(RouteOutput)
    router_context = list(context)
    if router_context and router_context[-1].type == "human":
        instruction = """\n\n[SISTEMA: Analise a mensagem e roteie:
- 'scheduling' para agendar servico, marcar horario, ver disponibilidade.
- 'receptionist' para precos, servicos, combos, horario de funcionamento.
- 'support' para cancelamento, atraso, pagamento, alergias, estacionamento.
Se for apenas "oi" ou ambiguo, use 'receptionist'.]"""
        router_context[-1] = HumanMessage(content=str(router_context[-1].content) + instruction)

    try:
        decision = router_llm.invoke(router_context)
        agent = decision.destination
        logger.info(f"Triage Node: LLM decidiu rotear para → {agent}")
    except Exception as e:
        logger.error(f"Triage Node: Erro no LLM, fallback para receptionist: {e}")
        agent = "receptionist"

    return {"active_agent": agent}


def _invoke_agent(state: AgentState, config: RunnableConfig, agent: str):
    org_id = _org_id_from_config(config)
    salon_name = get_salon_name(org_id)
    llm = _build_agent_llm(salon_name, agent)
    response = llm.invoke({"messages": state["messages"]})
    return {"messages": [response], "active_agent": agent, "company_name": salon_name}


def receptionist_node(state: AgentState, config: RunnableConfig):
    return _invoke_agent(state, config, "receptionist")


def scheduling_node(state: AgentState, config: RunnableConfig):
    return _invoke_agent(state, config, "scheduling")


def support_node(state: AgentState, config: RunnableConfig):
    return _invoke_agent(state, config, "support")


# ==========================================
# 5. ROTEAMENTO DE FERRAMENTAS
# ==========================================
async def run_tools(state: AgentState, config: RunnableConfig):
    """Executa as ferramentas chamadas pelo LLM."""
    last_msg = state["messages"][-1]
    tool_responses = []
    handoff_requested = False

    for tool_call in last_msg.tool_calls:
        logger.info(f"Executando tool: {tool_call['name']}")

        args = tool_call["args"].copy()
        res = "Ferramenta desconhecida."

        if tool_call["name"] == "search_kb":
            res = search_kb.invoke(args)
        elif tool_call["name"] == "request_human_handoff":
            args["sender_id"] = state.get("sender_id", "unknown")
            res = request_human_handoff.invoke(args)
            handoff_requested = True
        elif tool_call["name"] == "get_lakehouse_schema":
            res = get_lakehouse_schema.invoke(args)
        elif tool_call["name"] == "query_lakehouse":
            res = query_lakehouse.invoke(args)
        elif tool_call["name"] == "check_availability":
            res = await check_availability.ainvoke(args, config=config)
        elif tool_call["name"] == "book_time":
            res = await book_time.ainvoke(args, config=config)

        tool_responses.append(ToolMessage(content=res, tool_call_id=tool_call["id"]))

    return {"messages": tool_responses, "handoff_requested": handoff_requested}


# ==========================================
# 6. LÓGICA DE TRANSIÇÃO (EDGES)
# ==========================================
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


# ==========================================
# 7. CONSTRUÇÃO DO GRAFO
# ==========================================
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
