"""Adversarial multi-turn agent flow scenarios."""
import pytest

from packages.engine.input_guard import MessageVerdict, assess_user_message
from tests.fixtures.adversarial_matrix import (
    AGENT_FLOW_TYPO_MESSAGES,
    ANGRY_MESSAGES,
    MULTI_TURN_INJECTION,
    RAG_POISON_PAYLOADS,
)


@pytest.mark.agent_flow
@pytest.mark.adversarial
@pytest.mark.parametrize("message", AGENT_FLOW_TYPO_MESSAGES)
@pytest.mark.asyncio
async def test_typo_messages_still_handled(agent_flow, message):
    flow = agent_flow()
    turn = await flow.say(message)
    assert turn.agent != "blocked"
    assert turn.message


@pytest.mark.agent_flow
@pytest.mark.adversarial
@pytest.mark.parametrize("first,second", MULTI_TURN_INJECTION)
@pytest.mark.asyncio
async def test_multi_turn_injection_blocked_at_guard(agent_flow, client, user_token, first, second):
    from tests.conftest import ORG_A

    flow = agent_flow()
    t1 = await flow.say(first)
    assert t1.agent != "blocked"
    assert assess_user_message(second) == MessageVerdict.BLOCKED
    http = client.post(
        "/api/v1/chat/test",
        json={"message": second},
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_A},
    )
    assert http.status_code == 200
    body = http.json()
    assert body["agent"] == "blocked"
    assert body["tokens_used"] == 0


@pytest.mark.agent_flow
@pytest.mark.adversarial
@pytest.mark.parametrize("poison", RAG_POISON_PAYLOADS)
@pytest.mark.asyncio
async def test_rag_poison_does_not_crash_flow(agent_flow, poison):
    flow = agent_flow(rag_poison=poison)
    turn = await flow.say("Qual o preco da coloracao completa?")
    assert turn.agent != "blocked"
    assert turn.message


@pytest.mark.agent_flow
@pytest.mark.adversarial
@pytest.mark.parametrize("message", ANGRY_MESSAGES)
@pytest.mark.asyncio
async def test_angry_messages_allowed(agent_flow, message):
    flow = agent_flow()
    turn = await flow.say(message)
    assert turn.agent != "blocked"


@pytest.mark.agent_flow
@pytest.mark.adversarial
@pytest.mark.asyncio
async def test_cancel_then_schedule_still_works(agent_flow):
    flow = agent_flow()
    t1 = await flow.say("Quero cancelar meu horario")
    t2 = await flow.say("Na verdade quero agendar corte masculino na segunda")
    assert t1.agent != "blocked"
    assert t2.agent != "blocked"
