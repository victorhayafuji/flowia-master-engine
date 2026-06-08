import logging
from collections.abc import Sequence
from datetime import date
from functools import lru_cache
from typing import Any, Literal, TypedDict

try:
    from typing import Annotated
except ImportError:
    from typing import Annotated

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from packages.auth_core.config import settings
from packages.auth_core.tenant import set_tenant_context
from packages.engine.context import get_salon_name
from packages.engine.intent_extractor import (
    extract_booking_intent,
    should_run_intent_extractor,
)
from packages.engine.prompts import (
    build_lakehouse_prompt,
    build_receptionist_prompt,
    build_scheduling_prompt,
    build_support_prompt,
)
from packages.engine.response_composer import compose_scheduling_reply, polish_scheduling_reply
from packages.engine.routing import (
    has_support_intent,
    is_booking_conversation,
    message_text,
    resolve_triage_agent,
    should_force_scheduling_route,
    triage_source_for,
)
from packages.engine.scheduling_fallback import needs_scheduling_llm_fallback
from packages.engine.tools import get_lakehouse_schema, query_lakehouse, request_human_handoff, search_kb
from packages.scheduling.booking_executor import run_scheduling_turn
from packages.scheduling.guardrails import extract_booking_date_from_text
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
    triage_source: str | None
    scheduling_path: str | None
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
    human_msgs = [m for m in state["messages"] if m.type == "human"]

    if not human_msgs:
        return {
            "active_agent": current_agent or "receptionist",
            "booking_active": state.get("booking_active", False),
            "triage_source": state.get("triage_source"),
        }

    booking_active = bool(state.get("booking_active"))
    last_human = message_text(human_msgs[-1])
    was_booking_active = booking_active

    resolved = resolve_triage_agent(
        state["messages"],
        state.get("active_agent"),
        booking_active=booking_active,
    )

    if should_force_scheduling_route(state["messages"], booking_active=booking_active):
        resolved = "scheduling"
        booking_active = True
        triage_source = triage_source_for(
            state["messages"],
            was_booking_active=was_booking_active,
        )
    elif resolved == "support":
        booking_active = False
        triage_source = "keyword"
    elif resolved == "scheduling" or is_booking_conversation(state["messages"]):
        booking_active = True
        triage_source = triage_source_for(
            state["messages"],
            was_booking_active=was_booking_active,
        )
    elif has_support_intent(last_human):
        booking_active = False
        triage_source = "keyword"
    else:
        triage_source = None

    if resolved != "receptionist" or state.get("active_agent"):
        logger.info(
            "Triage Node: roteando para → %s (booking_active=%s, triage_source=%s)",
            resolved,
            booking_active,
            triage_source,
        )
        return {
            "active_agent": resolved,
            "booking_active": booking_active,
            "triage_source": triage_source,
        }

    logger.info("Triage Node: Analisando intenção do primeiro contato...")

    context = get_safe_context(state["messages"])
    if not context:
        return {"active_agent": "receptionist", "booking_active": booking_active, "triage_source": "llm"}

    router_llm = llm_base.with_structured_output(RouteOutput)
    router_context = list(context)
    if router_context and router_context[-1].type == "human":
        router_context = [SystemMessage(content=TRIAGE_SYSTEM_INSTRUCTION), *router_context]

    try:
        decision = router_llm.invoke(router_context)
        agent = decision.destination
        logger.info(f"Triage Node: LLM decidiu rotear para → {agent}")
    except Exception as e:
        logger.error(f"Triage Node: Erro no LLM, fallback para receptionist: {e}")
        agent = "receptionist"

    if should_force_scheduling_route(state["messages"], booking_active=was_booking_active):
        agent = "scheduling"
        triage_source = triage_source_for(
            state["messages"],
            was_booking_active=was_booking_active,
        )
    else:
        triage_source = "llm"

    booking_active = agent == "scheduling" or is_booking_conversation(state["messages"])
    return {"active_agent": agent, "booking_active": booking_active, "triage_source": triage_source}


def _scheduling_date_context() -> SystemMessage:
    today = date.today()
    return SystemMessage(
        content=(
            f"[CONTEXTO AGENDA] Hoje: {today.isoformat()} ({today.strftime('%d/%m/%Y')}). "
            f"Ano corrente: {today.year}. Fuso do salao: America/Sao_Paulo (Brasilia, UTC-3). "
            f"Horarios de check_availability e book_time sao SEMPRE horario local de Brasilia. "
            f"Nunca use Z/UTC em book_time. Nunca use anos anteriores a {today.year}."
        )
    )


def _scheduling_resolved_date_hint(messages: Sequence[BaseMessage]) -> SystemMessage | None:
    """Inject programmatically resolved booking date from client text."""
    today = date.today()
    for msg in reversed(messages):
        if msg.type != "human":
            continue
        text = message_text(msg)
        if not text.strip():
            continue
        resolved = extract_booking_date_from_text(text, reference=today)
        if not resolved:
            continue
        return SystemMessage(
            content=(
                f"[DATA RESOLVIDA] O cliente pediu agendamento para {resolved}. "
                f"Use check_availability com target_date={resolved} AGORA. "
                f"Nao pergunte o ano. Nao mencione 2024 ou 2025."
            )
        )
    return None


def _scheduling_context_messages(messages: Sequence[BaseMessage]) -> list[SystemMessage]:
    hints = [_scheduling_date_context()]
    resolved = _scheduling_resolved_date_hint(messages)
    if resolved:
        hints.append(resolved)
    return hints


def _invoke_agent(state: AgentState, config: RunnableConfig, agent: str):
    org_id = _org_id_from_config(config)
    salon_name = get_salon_name(org_id)
    llm = _build_agent_llm(salon_name, agent)
    messages: Sequence[BaseMessage] = state["messages"]
    if agent == "scheduling":
        messages = [*_scheduling_context_messages(state["messages"]), *messages]
    response = llm.invoke({"messages": messages})
    booking_active = agent == "scheduling" or bool(state.get("booking_active"))
    return {
        "messages": [response],
        "active_agent": agent,
        "company_name": salon_name,
        "booking_active": booking_active,
    }


async def receptionist_node(state: AgentState, config: RunnableConfig):
    if should_force_scheduling_route(
        state["messages"],
        booking_active=state.get("booking_active", False),
    ):
        logger.info("Receptionist escape → scheduling (same turn)")
        return await scheduling_node(state, config)
    return _invoke_agent(state, config, "receptionist")


async def _finalize_scheduling_reply(
    factual: str,
    *,
    messages: Sequence[BaseMessage],
    salon_name: str,
    user_acknowledgment: str | None,
    booking_date: str | None,
    booking_service: str | None,
    scheduling_path: str,
) -> dict[str, Any]:
    last_user = ""
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "human":
            last_user = message_text(msg)
            break

    composed = compose_scheduling_reply(
        factual,
        user_acknowledgment,
        salon_name=salon_name,
        booking_service=booking_service,
        booking_date=booking_date,
        user_message=last_user,
    )
    message = await polish_scheduling_reply(
        composed,
        factual_source=factual,
        salon_name=salon_name,
    )
    return {
        "messages": [AIMessage(content=message)],
        "active_agent": "scheduling",
        "company_name": salon_name,
        "booking_active": True,
        "booking_date": booking_date,
        "booking_service": booking_service,
        "scheduling_path": scheduling_path,
        "user_acknowledgment": user_acknowledgment,
    }


async def scheduling_node(state: AgentState, config: RunnableConfig):
    org_id = _org_id_from_config(config)
    salon_name = get_salon_name(org_id)
    booking_date = state.get("booking_date")
    booking_service = state.get("booking_service")
    user_ack = state.get("user_acknowledgment")

    if settings.SCHEDULING_DETERMINISTIC_ENABLED and org_id:
        if should_run_intent_extractor(
            state["messages"],
            org_id,
            booking_date=booking_date,
            booking_service=booking_service,
            booking_active=state.get("booking_active", False),
        ):
            extracted = await extract_booking_intent(
                state["messages"],
                org_id,
                salon_name=salon_name,
            )
            if extracted:
                booking_date = extracted.resolved_date or booking_date
                booking_service = extracted.resolved_service or booking_service
                user_ack = extracted.user_acknowledgment or user_ack

        with set_tenant_context(org_id):
            turn = await run_scheduling_turn(
                state["messages"],
                config,
                booking_date=booking_date,
                booking_service=booking_service,
            )
        if turn:
            logger.info(
                "Scheduling path=deterministic | service=%s date=%s",
                turn.booking_service,
                turn.booking_date,
            )
            return await _finalize_scheduling_reply(
                turn.message,
                messages=state["messages"],
                salon_name=salon_name,
                user_acknowledgment=user_ack,
                booking_date=turn.booking_date or booking_date,
                booking_service=turn.booking_service or booking_service,
                scheduling_path="deterministic",
            )

        if booking_date and booking_service:
            with set_tenant_context(org_id):
                retry = await run_scheduling_turn(
                    state["messages"],
                    config,
                    booking_date=booking_date,
                    booking_service=booking_service,
                )
            if retry:
                logger.info("Scheduling path=deterministic(retry)")
                return await _finalize_scheduling_reply(
                    retry.message,
                    messages=state["messages"],
                    salon_name=salon_name,
                    user_acknowledgment=user_ack,
                    booking_date=retry.booking_date,
                    booking_service=retry.booking_service,
                    scheduling_path="deterministic",
                )

        if settings.SCHEDULING_LLM_FALLBACK == "never":
            logger.info("Scheduling path=deterministic(miss) | LLM blocked")
            return await _finalize_scheduling_reply(
                (
                    "Não consegui concluir só com os dados informados. "
                    "Informe serviço, data, horário, nome e telefone com DDD."
                ),
                messages=state["messages"],
                salon_name=salon_name,
                user_acknowledgment=user_ack,
                booking_date=booking_date,
                booking_service=booking_service,
                scheduling_path="deterministic",
            )

        if settings.SCHEDULING_LLM_FALLBACK == "smart" and not needs_scheduling_llm_fallback(
            state["messages"],
            org_id,
            booking_date=booking_date,
            booking_service=booking_service,
            booking_active=state.get("booking_active", False),
        ):
            logger.info("Scheduling path=deterministic(miss) | smart blocked LLM")
            return await _finalize_scheduling_reply(
                (
                    "Para continuar o agendamento, informe serviço, data, horário, "
                    "nome completo e telefone com DDD."
                ),
                messages=state["messages"],
                salon_name=salon_name,
                user_acknowledgment=user_ack,
                booking_date=booking_date,
                booking_service=booking_service,
                scheduling_path="deterministic",
            )

    logger.info("Scheduling path=llm | fallback=%s", settings.SCHEDULING_LLM_FALLBACK)
    result = _invoke_agent(state, config, "scheduling")
    result["scheduling_path"] = "llm"
    result["user_acknowledgment"] = user_ack
    return result


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
    active_agent = _normalize_agent(state.get("active_agent"))
    allowed = AGENT_ALLOWED_TOOLS.get(active_agent, AGENT_ALLOWED_TOOLS["receptionist"])
    booking_date = state.get("booking_date")
    booking_service = state.get("booking_service")
    booking_active = bool(state.get("booking_active")) or active_agent == "scheduling"

    for tool_call in last_msg.tool_calls:
        tool_name = tool_call["name"]
        logger.info("Executando tool: %s (agent=%s)", tool_name, active_agent)

        if tool_name not in allowed:
            logger.warning("Tool %s blocked for agent %s", tool_name, active_agent)
            tool_responses.append(
                ToolMessage(content="Ferramenta não permitida.", tool_call_id=tool_call["id"])
            )
            continue

        args = tool_call["args"].copy()
        res = "Ferramenta desconhecida."

        if tool_name == "search_kb":
            res = search_kb.invoke(args)
        elif tool_name == "request_human_handoff":
            if active_agent == "scheduling" and state.get("booking_active"):
                res = (
                    "Handoff indisponível durante agendamento. "
                    "Use check_availability e book_time."
                )
            else:
                args["sender_id"] = state.get("sender_id", "unknown")
                res = request_human_handoff.invoke(args)
                handoff_requested = True
        elif tool_name == "get_lakehouse_schema":
            res = get_lakehouse_schema.invoke(args)
        elif tool_name == "query_lakehouse":
            res = query_lakehouse.invoke(args)
        elif tool_name == "check_availability":
            res = await check_availability.ainvoke(args, config=config)
            target_date = args.get("target_date")
            service_name = args.get("service_name")
            if target_date:
                booking_date = str(target_date)
            if service_name:
                booking_service = str(service_name)
            booking_active = True
        elif tool_name == "list_catalog_services":
            res = await list_catalog_services.ainvoke(args, config=config)
        elif tool_name == "book_time":
            res = await book_time.ainvoke(args, config=config)
            if isinstance(res, str) and res.upper().startswith("SUCESSO"):
                booking_active = False

        tool_responses.append(ToolMessage(content=res, tool_call_id=tool_call["id"]))

    return {
        "messages": tool_responses,
        "handoff_requested": handoff_requested,
        "booking_date": booking_date,
        "booking_service": booking_service,
        "booking_active": booking_active,
    }


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
