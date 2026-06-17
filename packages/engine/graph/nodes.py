"""LangGraph agent nodes and tool runner."""
from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date
from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from packages.auth_core.config import settings
from packages.auth_core.tenant import set_tenant_context
from packages.engine.context import get_salon_name
from packages.engine.graph.state import (
    AGENT_ALLOWED_TOOLS,
    TRIAGE_SYSTEM_INSTRUCTION,
    AgentState,
    _build_agent_llm,
    _normalize_agent,
    _org_id_from_config,
    get_safe_context,
    llm_base,
)
from packages.engine.intent_extractor import extract_booking_intent, should_run_intent_extractor
from packages.engine.receptionist_executor import run_receptionist_turn, should_run_deterministic_receptionist
from packages.engine.response_composer import (
    compose_scheduling_reply,
    polish_scheduling_reply,
    should_skip_stored_acknowledgment,
)
from packages.engine.routing import (
    has_support_intent,
    is_booking_confirmed_in_thread,
    is_booking_conversation,
    is_post_booking_closing,
    message_text,
    resolve_triage_agent,
    should_force_scheduling_route,
    triage_source_for,
)
from packages.engine.scheduling_fallback import needs_scheduling_llm_fallback
from packages.engine.support_executor import run_support_turn, should_run_deterministic_support
from packages.engine.tools import get_lakehouse_schema, query_lakehouse, request_human_handoff, search_kb
from packages.scheduling.booking_executor import run_scheduling_turn
from packages.scheduling.booking_state_sync import (
    BookingStateSnapshot,
    clear_booking_state,
    has_open_date_clarification,
    snapshot_to_state_patch,
    sync_booking_state,
)
from packages.scheduling.date_parsing import DateParseMode, format_date_label_pt, resolve_date_detailed
from packages.scheduling.guardrails import extract_booking_date_from_text, extract_reference_date_from_text
from packages.scheduling.tools import book_time, check_availability, list_catalog_services

logger = logging.getLogger(__name__)

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

    if should_force_scheduling_route(state["messages"], booking_active=booking_active) and resolved != "support":
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
        detailed = resolve_date_detailed(text, reference=today, mode=DateParseMode.BOOKING)
        if detailed and detailed.needs_clarification:
            return SystemMessage(
                content=(
                    f"[DATA AMBÍGUA] {detailed.clarification_prompt} "
                    "Pergunte o dia ao cliente antes de chamar check_availability."
                )
            )
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


def _require_org_id(config: RunnableConfig) -> str:
    """Fail-closed tenant guard: never build an agent reply without a concrete org.

    Without this, a missing/``ALL`` org_id would fall back to the generic salon
    name and answer anyway. We abort instead so the agent never speaks with a
    cross-tenant or anonymous identity. In production org_id is always present
    (webhook and /chat/test require it); this only trips on a broken config.
    """
    org_id = _org_id_from_config(config)
    if not org_id or org_id == "ALL":
        raise ValueError("org_id ausente ou inválido no caminho do agente (tenant guard).")
    return org_id


def _invoke_agent(state: AgentState, config: RunnableConfig, agent: str):
    org_id = _require_org_id(config)
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

    org_id = _org_id_from_config(config)
    if org_id and should_run_deterministic_receptionist(
        state["messages"],
        booking_active=state.get("booking_active", False),
    ):
        turn = run_receptionist_turn(state["messages"], org_id)
        if turn:
            salon_name = get_salon_name(org_id)
            logger.info("Receptionist path=deterministic")
            return {
                "messages": [AIMessage(content=turn.message)],
                "active_agent": "receptionist",
                "company_name": salon_name,
                "receptionist_path": "deterministic",
            }

    return _invoke_agent(state, config, "receptionist")


def _booking_slots_from_state(state: AgentState) -> dict[str, str | None]:
    return {
        "booking_date": state.get("booking_date"),
        "booking_service": state.get("booking_service"),
        "booking_time": state.get("booking_time"),
        "booking_patient_name": state.get("booking_patient_name"),
        "booking_patient_phone": state.get("booking_patient_phone"),
    }


def _persist_booking_state(
    messages: Sequence[BaseMessage],
    org_id: str,
    *,
    booking_date: str | None = None,
    booking_service: str | None = None,
    booking_time: str | None = None,
    booking_patient_name: str | None = None,
    booking_patient_phone: str | None = None,
) -> BookingStateSnapshot:
    """Merge LangGraph state with thread re-parse so slots survive mid-flow turns."""
    return sync_booking_state(
        messages,
        org_id,
        booking_date=booking_date,
        booking_service=booking_service,
        booking_time=booking_time,
        booking_patient_name=booking_patient_name,
        booking_patient_phone=booking_patient_phone,
    )


def _merge_turn_into_snapshot(
    messages: Sequence[BaseMessage],
    org_id: str,
    turn: Any,
    base: BookingStateSnapshot,
) -> BookingStateSnapshot:
    return sync_booking_state(
        messages,
        org_id,
        booking_date=turn.booking_date or base.booking_date,
        booking_service=turn.booking_service or base.booking_service,
        booking_time=getattr(turn, "booking_time", None) or base.booking_time,
        booking_patient_name=getattr(turn, "booking_patient_name", None) or base.booking_patient_name,
        booking_patient_phone=getattr(turn, "booking_patient_phone", None) or base.booking_patient_phone,
    )


def _snapshot_to_state_patch(snapshot: BookingStateSnapshot) -> dict[str, str | None | list[str]]:
    return snapshot_to_state_patch(snapshot)


async def _finalize_scheduling_reply(
    factual: str,
    *,
    messages: Sequence[BaseMessage],
    salon_name: str,
    user_acknowledgment: str | None,
    booking: BookingStateSnapshot,
    scheduling_path: str,
    org_id: str | None = None,
) -> dict[str, Any]:
    last_user = ""
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "human":
            last_user = message_text(msg)
            break

    if should_skip_stored_acknowledgment(last_user, user_acknowledgment, org_id=org_id):
        user_acknowledgment = None

    composed = compose_scheduling_reply(
        factual,
        user_acknowledgment,
        salon_name=salon_name,
        booking_service=booking.booking_service,
        booking_date=booking.booking_date,
        user_message=last_user,
        org_id=org_id,
    )
    message = await polish_scheduling_reply(
        composed,
        factual_source=factual,
        salon_name=salon_name,
    )

    is_booking_success = factual.strip().upper().startswith("SUCESSO")
    is_thanks_after_booking = (
        is_booking_confirmed_in_thread(list(messages)) and is_post_booking_closing(last_user)
    )
    handoff_to_receptionist = is_booking_success or is_thanks_after_booking
    booking_patch = clear_booking_state() if handoff_to_receptionist else _snapshot_to_state_patch(booking)

    return {
        "messages": [AIMessage(content=message)],
        "active_agent": "receptionist" if handoff_to_receptionist else "scheduling",
        "company_name": salon_name,
        "booking_active": False if handoff_to_receptionist else True,
        "scheduling_path": scheduling_path,
        "user_acknowledgment": None if handoff_to_receptionist else user_acknowledgment,
        **booking_patch,
    }


async def scheduling_node(state: AgentState, config: RunnableConfig):
    org_id = _org_id_from_config(config)
    salon_name = get_salon_name(org_id)
    user_ack = state.get("user_acknowledgment")
    slots = _booking_slots_from_state(state)

    if settings.SCHEDULING_DETERMINISTIC_ENABLED and org_id:
        snapshot = sync_booking_state(state["messages"], org_id, **slots)

        if should_run_intent_extractor(
            state["messages"],
            org_id,
            booking_date=snapshot.booking_date,
            booking_service=snapshot.booking_service,
            booking_active=state.get("booking_active", False),
        ):
            extracted = await extract_booking_intent(
                state["messages"],
                org_id,
                salon_name=salon_name,
            )
            if extracted:
                merged_date = snapshot.booking_date
                if extracted.resolved_date and not has_open_date_clarification(snapshot):
                    merged_date = extracted.resolved_date
                snapshot = sync_booking_state(
                    state["messages"],
                    org_id,
                    booking_date=merged_date,
                    booking_service=extracted.resolved_service or snapshot.booking_service,
                    booking_time=snapshot.booking_time,
                    booking_patient_name=snapshot.booking_patient_name,
                    booking_patient_phone=snapshot.booking_patient_phone,
                )
                if extracted.user_acknowledgment and (
                    not extracted.service_hint or extracted.resolved_service
                ):
                    last_user = ""
                    for msg in reversed(state["messages"]):
                        if getattr(msg, "type", None) == "human":
                            last_user = message_text(msg)
                            break
                    if not should_skip_stored_acknowledgment(
                        last_user, extracted.user_acknowledgment, org_id=org_id
                    ):
                        user_ack = extracted.user_acknowledgment

        with set_tenant_context(org_id):
            turn = await run_scheduling_turn(
                state["messages"],
                config,
                booking_date=snapshot.booking_date,
                booking_service=snapshot.booking_service,
                booking_time=snapshot.booking_time,
                booking_patient_name=snapshot.booking_patient_name,
                booking_patient_phone=snapshot.booking_patient_phone,
                booking_step=snapshot.booking_step,
                checkpoint=snapshot,
            )
        if not turn:
            retry_snapshot = _persist_booking_state(
                state["messages"],
                org_id,
                **slots,
            )
            if (
                retry_snapshot.booking_date
                and retry_snapshot.booking_service
                and (
                    retry_snapshot.booking_date != snapshot.booking_date
                    or retry_snapshot.booking_service != snapshot.booking_service
                )
            ):
                with set_tenant_context(org_id):
                    turn = await run_scheduling_turn(
                        state["messages"],
                        config,
                        booking_date=retry_snapshot.booking_date,
                        booking_service=retry_snapshot.booking_service,
                        booking_time=retry_snapshot.booking_time,
                        booking_patient_name=retry_snapshot.booking_patient_name,
                        booking_patient_phone=retry_snapshot.booking_patient_phone,
                        booking_step=retry_snapshot.booking_step,
                        checkpoint=retry_snapshot,
                    )
        if turn:
            logger.info(
                "Scheduling path=deterministic | service=%s date=%s step=%s pending=%s missing=%s",
                turn.booking_service,
                turn.booking_date,
                snapshot.booking_step,
                snapshot.pending_clarification,
                snapshot.missing_fields,
            )
            persisted = _merge_turn_into_snapshot(
                state["messages"],
                org_id,
                turn,
                snapshot,
            )
            return await _finalize_scheduling_reply(
                turn.message,
                messages=state["messages"],
                salon_name=salon_name,
                user_acknowledgment=user_ack,
                booking=persisted,
                scheduling_path="deterministic",
                org_id=org_id,
            )

        if snapshot.booking_date and snapshot.booking_service:
            with set_tenant_context(org_id):
                retry = await run_scheduling_turn(
                    state["messages"],
                    config,
                    booking_date=snapshot.booking_date,
                    booking_service=snapshot.booking_service,
                    booking_time=snapshot.booking_time,
                    booking_patient_name=snapshot.booking_patient_name,
                    booking_patient_phone=snapshot.booking_patient_phone,
                    booking_step=snapshot.booking_step,
                    checkpoint=snapshot,
                )
            if retry:
                logger.info("Scheduling path=deterministic(retry)")
                persisted = _merge_turn_into_snapshot(
                    state["messages"],
                    org_id,
                    retry,
                    snapshot,
                )
                return await _finalize_scheduling_reply(
                    retry.message,
                    messages=state["messages"],
                    salon_name=salon_name,
                    user_acknowledgment=user_ack,
                    booking=persisted,
                    scheduling_path="deterministic",
                    org_id=org_id,
                )

        snapshot = _persist_booking_state(state["messages"], org_id, **slots)

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
                booking=snapshot,
                scheduling_path="deterministic",
                org_id=org_id,
            )

        if settings.SCHEDULING_LLM_FALLBACK == "smart" and not needs_scheduling_llm_fallback(
            state["messages"],
            org_id,
            booking_date=snapshot.booking_date,
            booking_service=snapshot.booking_service,
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
                booking=snapshot,
                scheduling_path="deterministic",
                org_id=org_id,
            )

    logger.info("Scheduling path=llm | fallback=%s", settings.SCHEDULING_LLM_FALLBACK)
    result = _invoke_agent(state, config, "scheduling")
    result["scheduling_path"] = "llm"
    result["user_acknowledgment"] = user_ack
    return result


def _support_reference_date_hint(messages: Sequence[BaseMessage]) -> SystemMessage | None:
    today = date.today()
    for msg in reversed(messages):
        if msg.type != "human":
            continue
        text = message_text(msg)
        if not text.strip():
            continue
        resolved = extract_reference_date_from_text(text, reference=today)
        if not resolved:
            continue
        label = format_date_label_pt(resolved)
        return SystemMessage(
            content=(
                f"[DATA REFERIDA PELO CLIENTE] {resolved} ({label}). "
                "Reconheça explicitamente esta data na resposta ao cliente."
            )
        )
    return None


def support_node(state: AgentState, config: RunnableConfig):
    org_id = _org_id_from_config(config)
    if org_id and should_run_deterministic_support(state["messages"]):
        turn = run_support_turn(state["messages"], org_id)
        if turn:
            salon_name = get_salon_name(org_id)
            logger.info("Support path=deterministic | date=%s", turn.reference_date)
            return {
                "messages": [AIMessage(content=turn.message)],
                "active_agent": "support",
                "company_name": salon_name,
                "support_path": "deterministic",
            }

    org_id = _org_id_from_config(config)
    salon_name = get_salon_name(org_id)
    llm = _build_agent_llm(salon_name, "support")
    messages: list[BaseMessage] = list(state["messages"])
    hint = _support_reference_date_hint(messages)
    if hint:
        messages = [hint, *messages]
    response = llm.invoke({"messages": messages})
    return {
        "messages": [response],
        "active_agent": "support",
        "company_name": salon_name,
        "booking_active": False,
    }


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
    org_id = _org_id_from_config(config)
    booking_date = state.get("booking_date")
    booking_service = state.get("booking_service")
    booking_time = state.get("booking_time")
    booking_patient_name = state.get("booking_patient_name")
    booking_patient_phone = state.get("booking_patient_phone")
    booking_active = bool(state.get("booking_active")) or active_agent == "scheduling"
    booking_success = False
    booking_slots_dirty = False

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
            booking_slots_dirty = True
        elif tool_name == "list_catalog_services":
            res = await list_catalog_services.ainvoke(args, config=config)
        elif tool_name == "book_time":
            res = await book_time.ainvoke(args, config=config)
            if isinstance(res, str) and res.upper().startswith("SUCESSO"):
                booking_active = False
                booking_success = True
            else:
                booking_slots_dirty = True
                time_arg = args.get("time") or args.get("time_hhmm")
                if time_arg:
                    booking_time = str(time_arg)
                if args.get("patient_name"):
                    booking_patient_name = str(args["patient_name"])
                if args.get("patient_phone"):
                    booking_patient_phone = str(args["patient_phone"])

        tool_responses.append(ToolMessage(content=res, tool_call_id=tool_call["id"]))

    booking_patch: dict[str, Any] = {
        "booking_date": booking_date,
        "booking_service": booking_service,
        "booking_time": booking_time,
        "booking_patient_name": booking_patient_name,
        "booking_patient_phone": booking_patient_phone,
        "booking_active": booking_active,
    }
    if booking_success:
        booking_patch.update(clear_booking_state())
        booking_patch["booking_active"] = False
    elif booking_slots_dirty and org_id and active_agent == "scheduling":
        snapshot = sync_booking_state(
            state["messages"],
            org_id,
            booking_date=booking_date,
            booking_service=booking_service,
            booking_time=booking_time,
            booking_patient_name=booking_patient_name,
            booking_patient_phone=booking_patient_phone,
        )
        booking_patch.update(_snapshot_to_state_patch(snapshot))
        booking_patch["booking_active"] = booking_active

    return {
        "messages": tool_responses,
        "handoff_requested": handoff_requested,
        **booking_patch,
    }
