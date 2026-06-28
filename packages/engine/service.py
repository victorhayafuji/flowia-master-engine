import logging
import traceback
import uuid
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from packages.auth_core.config import settings
from packages.auth_core.conversation_thread import build_thread_id
from packages.auth_core.tenant import get_current_org_id, set_tenant_context
from packages.compliance.consent import ConsentAction, evaluate_consent_gate, record_consent
from packages.compliance.logging_utils import mask_thread_id
from packages.engine.checkpointer import master_engine
from packages.engine.input_guard import MessageVerdict, assess_user_message, format_user_message_for_agent
from packages.engine.metrics.service import calculate_cost, save_conversation_metric
from packages.engine.metrics.telemetry import extract_turn_tools_called
from packages.engine.token_tracking import TurnTokenTracker, resolve_turn_tokens

logger = logging.getLogger(__name__)


def _compliance_response(thread_id: str, message: str, step: dict | None = None) -> dict[str, Any]:
    """LGPD compliance turn (consent notice / decline) — deterministic, tokens=0."""
    return {
        "response": message,
        "agent": "compliance",
        "tokens_used": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "estimated_cost_brl": 0.0,
        "thread_id": thread_id,
        "handoff": False,
        "messages_count": 0,
        "lgpd_notice": True,
        "step": step,
    }


def _faq_followup_step() -> dict[str, Any]:
    from packages.scheduling.guided_booking import post_faq_step

    return post_faq_step().to_dict()


def _guided_response(thread_id: str, result: Any) -> dict[str, Any]:
    """Shape a guided StructuredStep/BookingOutcome as a chat response dict."""
    from packages.scheduling.guided_booking import StructuredStep

    is_step = isinstance(result, StructuredStep)
    return {
        "response": result.text if is_step else result.message,
        "agent": "scheduling",
        "tokens_used": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "estimated_cost_brl": 0.0,
        "thread_id": thread_id,
        "handoff": False,
        "messages_count": 0,
        "scheduling_path": "deterministic",
        "triage_source": "guided",
        "step": result.to_dict() if is_step else None,
    }


async def _maybe_guided_turn(
    thread_id: str, org_id: str, message: str, patient_id: str | None = None
) -> dict[str, Any] | None:
    """Hybrid agent: drive the selection-based guided booking inline in the chat.

    The client is resolved from the test page's selector (``patient_id``; None means
    "not registered" → onboarding). Returns a response dict when a guided session is
    active or the message shows scheduling intent; otherwise None (LLM engine).
    """
    from packages.engine.routing import (
        has_scheduling_intent,
        is_booking_data_reply,
        is_greeting,
        is_reschedule_or_cancel_intent,
    )
    from packages.scheduling import guided_booking
    from packages.scheduling.guided_session_store import STEP_PATIENT_CAPTURE, has_active_session

    selection = (message or "").strip()

    # Continue an in-progress booking.
    if has_active_session(thread_id):
        result = await guided_booking.advance(thread_id, selection)
        return _guided_response(thread_id, result)

    # Reagendar/cancelar vão para o agente (scheduling/support), não para um novo
    # booking guiado — evita que "remarcar"/"cancelar meu horário" virem novo agendamento.
    if is_reschedule_or_cancel_intent(message):
        return None

    # Entry routing (no active session).
    if selection == guided_booking.MENU_BOOK_ID or has_scheduling_intent(message):
        result = await guided_booking.start_session(
            thread_id, org_id=org_id, patient_id=patient_id, channel="chat_test"
        )
        return _guided_response(thread_id, result)
    if selection == guided_booking.MENU_FAQ_ID:
        return _guided_response(thread_id, guided_booking.faq_topics_step())
    if is_greeting(message):
        return _guided_response(thread_id, guided_booking.menu_step())

    # Recovery: a booking-data reply (name+phone) with no active session means the
    # guided session was dropped mid-onboarding (e.g. dev hot-reload). Restart the
    # guided flow and consume the reply instead of leaking to the free-text LLM.
    if is_booking_data_reply(message):
        step = await guided_booking.start_session(
            thread_id, org_id=org_id, patient_id=patient_id, channel="chat_test"
        )
        if isinstance(step, guided_booking.StructuredStep) and step.step == STEP_PATIENT_CAPTURE:
            result = await guided_booking.advance(thread_id, message)
            return _guided_response(thread_id, result)
        return _guided_response(thread_id, step)
    return None


async def dispatch_chat_test(
    message: str,
    thread_id: str | None = None,
    org_id: str | None = None,
    guided_enabled: bool = False,
    patient_id: str | None = None,
) -> dict[str, Any]:
    """
    Orchestrates the chat test invocation to the master engine,
    extracts the response, calculates tokens, and saves metrics.
    """
    thread_id = thread_id or str(uuid.uuid4())

    try:
        verdict = assess_user_message(message)

        # FAQ topic shortcut → answer via the normal LLM+RAG engine (canonical question).
        is_faq_topic = False
        if guided_enabled:
            from packages.scheduling.guided_booking import FAQ_TOPIC_QUESTIONS

            faq_question = FAQ_TOPIC_QUESTIONS.get((message or "").strip())
            if faq_question:
                message = faq_question
                is_faq_topic = True

        formatted_message = format_user_message_for_agent(message)

        effective_org = org_id or get_current_org_id()
        if not effective_org or effective_org == "ALL":
            raise ValueError("org_id é obrigatório para chat test.")

        if not thread_id.startswith(f"{effective_org}:"):
            thread_id = build_thread_id(effective_org, thread_id)

        token_tracker = TurnTokenTracker()
        config = {
            "configurable": {
                "thread_id": thread_id,
                "channel": "chat_test",
                "org_id": effective_org,
                # Cliente simulado pelo seletor da tela de teste (espelha o sender do WhatsApp)
                # para tools que agem sobre o próprio agendamento (reschedule/cancel).
                "patient_id": patient_id,
            },
            "callbacks": [token_tracker],
        }

        input_data: dict[str, Any] = {
            "messages": [HumanMessage(content=formatted_message)],
            "sender_id": thread_id,
        }
        if verdict == MessageVerdict.SUSPICIOUS:
            input_data["audit_flag"] = "suspicious"

        # Explicit LGPD consent buttons (dev chat) — handled before the tácito gate.
        if guided_enabled:
            from packages.scheduling import guided_booking as _gb

            consent_sel = (message or "").strip()
            if consent_sel == _gb.CONSENT_DECLINE_ID:
                return _compliance_response(
                    thread_id,
                    "Tudo bem! Encerrando por aqui. Quando quiser, é só chamar. 👋",
                )
            if consent_sel == _gb.CONSENT_ACCEPT_ID:
                with set_tenant_context(effective_org):
                    record_consent(effective_org, thread_id, "chat_test")
                return _guided_response(thread_id, _gb.menu_step())

        with set_tenant_context(effective_org):
            consent_action, notice_msg, lgpd_shown = evaluate_consent_gate(
                effective_org, thread_id, "chat_test"
            )

        if consent_action == ConsentAction.SEND_NOTICE and notice_msg:
            if guided_enabled:
                from packages.scheduling import guided_booking as _gb

                return _compliance_response(
                    thread_id, notice_msg, step=_gb.consent_step(notice_msg).to_dict()
                )
            return {
                "response": notice_msg,
                "agent": "compliance",
                "tokens_used": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "estimated_cost_brl": 0.0,
                "thread_id": thread_id,
                "handoff": False,
                "messages_count": 0,
                "lgpd_notice": True,
            }

        input_data["lgpd_shown"] = lgpd_shown

        # Hybrid agent: guided (selection) booking inline before the LLM engine.
        # Opt-in (dev chat) so the free-text booking engine stays the default elsewhere.
        if guided_enabled:
            with set_tenant_context(effective_org):
                guided = await _maybe_guided_turn(thread_id, effective_org, message, patient_id)
            if guided is not None:
                return guided

        logger.info(f"🚀 Dispatching to Master Engine (Async) | Thread: {mask_thread_id(thread_id)}")

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
            "receptionist_path": final_state.get("receptionist_path"),
            "triage_source": final_state.get("triage_source"),
            # After a FAQ answer, offer a way back to the deterministic flow.
            "step": _faq_followup_step() if is_faq_topic else None,
        }

    except Exception:
        tb = traceback.format_exc()
        logger.error(f"❌ Critical failure in dispatch_chat_test:\n{tb}")
        return {
            "response": "Tive um problema técnico ao processar sua mensagem. Tente novamente em instantes.",
            "agent": "error",
            "tokens_used": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "estimated_cost_brl": 0.0,
            "thread_id": thread_id,
            "handoff": False,
            "messages_count": 0,
        }
