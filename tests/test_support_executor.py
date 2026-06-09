"""Unit tests for deterministic support executor."""
from datetime import date
from unittest.mock import patch

from langchain_core.messages import HumanMessage

from packages.engine.routing import has_support_with_date_intent, resolve_triage_agent
from packages.engine.support_executor import (
    run_support_turn,
    should_run_deterministic_support,
)


class TestSupportRouting:
    def test_cancel_anteontem_routes_support(self):
        messages = [HumanMessage(content="Preciso cancelar o horário de anteontem")]
        assert has_support_with_date_intent("Preciso cancelar o horário de anteontem")
        assert resolve_triage_agent(messages, None) == "support"

    def test_cancel_horario_stays_support(self):
        messages = [HumanMessage(content="Preciso cancelar meu horário")]
        assert resolve_triage_agent(messages, None) == "support"


class TestSupportExecutor:
    def test_should_run_on_faltei_ontem(self):
        messages = [HumanMessage(content="Faltei ontem")]
        assert should_run_deterministic_support(messages)

    @patch("packages.engine.support_executor.search_kb")
    def test_compose_reply_cites_date(self, mock_kb):
        mock_kb.invoke.return_value = "[DADOS OFICIAIS DA BASE]\nCancelamento até 24h antes."
        messages = [HumanMessage(content="Faltei ontem")]
        result = run_support_turn(messages, "22222222-2222-2222-2222-222222222222")
        assert result is not None
        assert "06/06" in result.message or "ontem" in result.message.lower() or "ausência" in result.message.lower()
        assert result.reference_date == (date.today().fromordinal(date.today().toordinal() - 1)).isoformat()

    @patch("packages.engine.support_executor.search_kb")
    def test_ambiguous_week_runs_with_clarification(self, mock_kb):
        mock_kb.invoke.return_value = "[DADOS OFICIAIS DA BASE]\nCancelamento até 24h antes."
        messages = [HumanMessage(content="Quero cancelar semana que vem")]
        assert should_run_deterministic_support(messages)
        result = run_support_turn(messages, "22222222-2222-2222-2222-222222222222")
        assert result is not None
        assert "qual dia" in result.message.lower() or "semana" in result.message.lower()

    def test_cancel_reschedule_handoff(self):
        messages = [HumanMessage(content="Preciso cancelar sexta e remarcar domingo")]
        assert should_run_deterministic_support(messages)
        result = run_support_turn(messages, "22222222-2222-2222-2222-222222222222")
        assert result is not None
        assert "equipe" in result.message.lower()
