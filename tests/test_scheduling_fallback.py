"""Tests for smart LLM fallback heuristics."""
from langchain_core.messages import HumanMessage

from packages.engine.scheduling_fallback import needs_scheduling_llm_fallback

ORG = "22222222-2222-2222-2222-222222222222"


def test_no_fallback_when_service_and_date_resolved(mocker):
    mocker.patch(
        "packages.engine.scheduling_fallback.resolve_booking_context",
        return_value=("2026-06-10", "Coloração"),
    )
    mocker.patch(
        "packages.engine.scheduling_fallback._guess_service_query",
        return_value="Coloração",
    )
    msgs = [HumanMessage(content="Quero coloração dia 10 de junho")]
    assert not needs_scheduling_llm_fallback(msgs, ORG, booking_active=True)


def test_fallback_for_colloquial_service_without_match(mocker):
    mocker.patch(
        "packages.engine.scheduling_fallback.resolve_booking_context",
        return_value=("2026-06-10", None),
    )
    mocker.patch(
        "packages.engine.scheduling_fallback._guess_service_query",
        return_value=None,
    )
    msgs = [HumanMessage(content="Quero fazer mechas na sexta dia 10")]
    assert needs_scheduling_llm_fallback(msgs, ORG, booking_active=True)
