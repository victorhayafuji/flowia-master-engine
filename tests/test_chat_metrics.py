"""Tests for chat token aggregation and cost estimation."""
from langchain_core.messages import AIMessage, HumanMessage

from packages.engine.metrics.service import calculate_cost
from packages.engine.token_tracking import TurnTokenTracker, aggregate_turn_tokens, resolve_turn_tokens


class TestAggregateTurnTokens:
    def test_sums_all_ai_messages_since_last_human(self):
        messages = [
            HumanMessage(content="old question"),
            AIMessage(
                content="old answer",
                usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            ),
            HumanMessage(content="new question"),
            AIMessage(
                content="",
                usage_metadata={"input_tokens": 200, "output_tokens": 0, "total_tokens": 200},
            ),
            AIMessage(
                content="final",
                usage_metadata={"input_tokens": 300, "output_tokens": 100, "total_tokens": 400},
            ),
        ]
        t_in, t_out, t_total = aggregate_turn_tokens(messages)
        assert t_in == 500
        assert t_out == 100
        assert t_total == 600

    def test_ignores_messages_before_last_human(self):
        messages = [
            HumanMessage(content="only turn"),
            AIMessage(
                content="reply",
                usage_metadata={"input_tokens": 80, "output_tokens": 20, "total_tokens": 100},
            ),
        ]
        t_in, t_out, t_total = aggregate_turn_tokens(messages)
        assert t_in == 80
        assert t_out == 20
        assert t_total == 100

    def test_handles_missing_usage_metadata(self):
        messages = [
            HumanMessage(content="q"),
            AIMessage(content="a"),
        ]
        t_in, t_out, t_total = aggregate_turn_tokens(messages)
        assert t_in == 0
        assert t_out == 0
        assert t_total == 0


class TestResolveTurnTokens:
    def test_prefers_callback_when_higher_than_messages(self):
        messages = [
            HumanMessage(content="q"),
            AIMessage(
                content="final",
                usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            ),
        ]
        tracker = TurnTokenTracker()
        tracker.input_tokens = 400
        tracker.output_tokens = 100
        tracker.llm_calls = 3
        t_in, t_out, t_total = resolve_turn_tokens(messages, tracker)
        assert t_in == 400
        assert t_out == 100
        assert t_total == 500

    def test_falls_back_to_messages_when_callback_empty(self):
        messages = [
            HumanMessage(content="q"),
            AIMessage(
                content="final",
                usage_metadata={"input_tokens": 200, "output_tokens": 80, "total_tokens": 280},
            ),
        ]
        tracker = TurnTokenTracker()
        t_in, t_out, t_total = resolve_turn_tokens(messages, tracker)
        assert t_total == 280


class TestCalculateCost:

    def test_calculate_cost_gpt4o_mini(self):
        cost = calculate_cost(1000, 500, "gpt-4o-mini", usd_to_brl=5.0)
        assert cost > 0

    def test_calculate_cost_gpt4o(self):
        cost = calculate_cost(1000, 500, "gpt-4o", usd_to_brl=5.0)
        assert cost > 0

    def test_calculate_cost_unknown_model_uses_default(self):
        cost = calculate_cost(1000, 500, "unknown-model", usd_to_brl=5.0)
        assert cost > 0

    def test_chat_response_includes_cost_fields(self, client, user_token, mocker):
        from unittest.mock import AsyncMock

        async def fake_dispatch(message, thread_id=None, org_id=None, **kwargs):
            return {
                "response": "R$ 299",
                "agent": "sdr",
                "tokens_used": 600,
                "tokens_in": 500,
                "tokens_out": 100,
                "estimated_cost_brl": 0.0123,
                "thread_id": "test-thread",
                "handoff": False,
                "messages_count": 4,
                "scheduling_path": None,
                "triage_source": "llm",
            }

        mocker.patch(
            "packages.engine.chat_router.dispatch_chat_test",
            new_callable=AsyncMock,
            side_effect=fake_dispatch,
        )

        response = client.post(
            "/api/v1/chat/test",
            json={"message": "precos"},
            cookies={"session_token": user_token},
            headers={"x-organization-id": "22222222-2222-2222-2222-222222222222"},
        )
        data = response.json()
        assert response.status_code == 200
        assert data["tokens_in"] == 500
        assert data["tokens_out"] == 100
        assert data["estimated_cost_brl"] == 0.0123
