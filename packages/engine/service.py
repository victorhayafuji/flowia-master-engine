import logging
import traceback
import uuid
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from packages.auth_core.config import settings
from packages.auth_core.tenant import get_current_org_id
from packages.engine.checkpointer import master_engine
from packages.engine.input_guard import MessageVerdict, assess_user_message, format_user_message_for_agent
from packages.engine.metrics.service import calculate_cost, save_conversation_metric
from packages.engine.metrics.telemetry import extract_turn_tools_called
from packages.engine.token_tracking import TurnTokenTracker, resolve_turn_tokens

logger = logging.getLogger(__name__)

async def dispatch_chat_test(
    message: str,
    thread_id: str | None = None,
    org_id: str | None = None,
) -> dict[str, Any]:
    """
    Orchestrates the chat test invocation to the master engine,
    extracts the response, calculates tokens, and saves metrics.
    """
    thread_id = thread_id or str(uuid.uuid4())

    try:
        verdict = assess_user_message(message)
        formatted_message = format_user_message_for_agent(message)

        token_tracker = TurnTokenTracker()
        config = {
            "configurable": {"thread_id": thread_id, "channel": "chat_test"},
            "callbacks": [token_tracker],
        }

        input_data: dict[str, Any] = {
            "messages": [HumanMessage(content=formatted_message)],
            "sender_id": thread_id,
        }
        if verdict == MessageVerdict.SUSPICIOUS:
            input_data["audit_flag"] = "suspicious"

        effective_org = org_id or get_current_org_id()
        if not effective_org or effective_org == "ALL":
            raise ValueError("org_id é obrigatório para chat test.")
        config["configurable"]["org_id"] = effective_org

        logger.info(f"🚀 Dispatching to Master Engine (Async) | Thread: {thread_id}")

        final_state = await master_engine.ainvoke(input_data, config=config)

        # Extract AI response
        messages = final_state.get("messages", [])
        logger.info(f"📊 State keys returned: {list(final_state.keys())}")

        if not messages:
            raise ValueError("O motor de IA não gerou nenhuma mensagem no histórico.")

        ai_msg_obj = messages[-1]
        ai_msg = getattr(ai_msg_obj, "content", str(ai_msg_obj))

        if isinstance(ai_msg, list):
            ai_msg = " ".join([b.get("text", "") for b in ai_msg if isinstance(b, dict) and "text" in b])

        # Find the last AIMessage with actual text content
        # LIMIT: Do not look further back than the last HumanMessage
        if not ai_msg or not ai_msg.strip():
            for m in reversed(messages):
                if isinstance(m, HumanMessage):
                    break # Stop searching when we reach the user's input
                if isinstance(m, AIMessage):
                    content = getattr(m, "content", "")
                    if isinstance(content, list):
                        content = " ".join([b.get("text", "") for b in content if isinstance(b, dict) and "text" in b])
                    if content and content.strip():
                        ai_msg_obj = m
                        ai_msg = content
                        break

        t_in, t_out, t_total = resolve_turn_tokens(messages, token_tracker)
        cost_brl = round(calculate_cost(t_in, t_out, settings.MODEL_NAME), 4)
        logger.info(
            "Token breakdown | callback=%s+%s (%s calls) | messages=%s+%s | total=%s | ~R$ %s",
            token_tracker.input_tokens,
            token_tracker.output_tokens,
            token_tracker.llm_calls,
            t_in,
            t_out,
            t_total,
            cost_brl,
        )

        save_conversation_metric(
            thread_id=thread_id,
            sender_id=thread_id,
            agent_type=final_state.get("active_agent", "unknown"),
            messages_count=len(messages),
            tokens_in=t_in,
            tokens_out=t_out,
            tokens_total=t_total,
            handoff_requested=final_state.get("handoff_requested", False),
            qualified=final_state.get("qualified", False),
            model_name=settings.MODEL_NAME,
            organization_id=effective_org,
            scheduling_path=final_state.get("scheduling_path"),
            triage_source=final_state.get("triage_source"),
            channel=(config.get("configurable") or {}).get("channel") or "chat_test",
            tools_called=extract_turn_tools_called(messages),
        )

        return {
            "response": ai_msg or "O agente processou a mensagem mas não retornou texto.",
            "agent": final_state.get("active_agent", "unknown"),
            "tokens_used": t_total,
            "tokens_in": t_in,
            "tokens_out": t_out,
            "estimated_cost_brl": cost_brl,
            "thread_id": thread_id,
            "lead_name": final_state.get("lead_name"),
            "company_name": final_state.get("company_name"),
            "email": final_state.get("email"),
            "handoff": final_state.get("handoff_requested", False),
            "messages_count": len(messages),
            "scheduling_path": final_state.get("scheduling_path"),
            "triage_source": final_state.get("triage_source"),
        }

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"❌ Critical failure in dispatch_chat_test:\n{tb}")
        return {
            "response": f"Erro no Motor de IA: {str(e)}",
            "agent": "error",
            "tokens_used": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "estimated_cost_brl": 0.0,
            "thread_id": thread_id,
            "handoff": False,
            "messages_count": 0,
        }
