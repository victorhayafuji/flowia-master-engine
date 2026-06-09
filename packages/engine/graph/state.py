"""LangGraph state, tool allowlists and LLM helpers."""
import logging
from collections.abc import Sequence
from functools import lru_cache
from typing import Any, TypedDict

try:
    from typing import Annotated
except ImportError:
    from typing import Annotated

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import add_messages

from packages.engine.llm import get_chat_llm
from packages.engine.prompts import (
    build_lakehouse_prompt,
    build_receptionist_prompt,
    build_scheduling_prompt,
    build_support_prompt,
)
from packages.engine.tools import get_lakehouse_schema, query_lakehouse, request_human_handoff, search_kb
from packages.scheduling.tools import book_time, check_availability, list_catalog_services

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
    booking_active: bool
    booking_date: str | None
    booking_service: str | None
    booking_step: str | None
    booking_time: str | None
    booking_patient_name: str | None
    booking_patient_phone: str | None
    booking_pending_clarification: str | None
    booking_missing_fields: list[str] | None
    triage_source: str | None
    scheduling_path: str | None
    receptionist_path: str | None
    user_acknowledgment: str | None
    last_node: str | None
    audit_flag: str | None
    lgpd_shown: bool
    first_contact_at: float
    messages_count: int

# ==========================================
# 2. FERRAMENTAS POR AGENTE
# ==========================================
receptionist_tools = [search_kb]
support_tools = [search_kb, request_human_handoff]
scheduling_tools = [search_kb, list_catalog_services, check_availability, book_time]
lakehouse_tools = [get_lakehouse_schema, query_lakehouse]

AGENT_ALLOWED_TOOLS: dict[str, frozenset[str]] = {
    "receptionist": frozenset({"search_kb"}),
    "support": frozenset({"search_kb", "request_human_handoff"}),
    "scheduling": frozenset({"search_kb", "list_catalog_services", "check_availability", "book_time"}),
    "lakehouse_query": frozenset({"get_lakehouse_schema", "query_lakehouse"}),
}

TRIAGE_SYSTEM_INSTRUCTION = """Analise a mensagem do cliente e roteie com PRIORIDADE:
- 'scheduling' se o cliente quer AGENDAR, MARCAR horario, ver DISPONIBILIDADE ou continuar um agendamento.
- 'receptionist' APENAS para precos/informacoes SEM intencao de marcar horario agora.
- 'support' para cancelamento, atraso, pagamento, alergias, estacionamento.
Se for apenas "oi" ou ambiguo sem agendamento, use 'receptionist'."""

llm_base = get_chat_llm(temperature=0.0)


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
    """Sanitizador minimalista de histórico para o LLM."""
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

