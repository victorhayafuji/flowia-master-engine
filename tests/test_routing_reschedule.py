"""Roteamento: reagendar (ação) → scheduling; cancelar → suporte (onde mora a tool)."""
from langchain_core.messages import HumanMessage

from packages.engine.routing import (
    has_reschedule_intent,
    is_reschedule_or_cancel_intent,
    resolve_triage_agent,
)


def _agent(text: str) -> str:
    return resolve_triage_agent([HumanMessage(content=text)], None)


def test_reschedule_action_routes_scheduling():
    assert _agent("quero remarcar meu horário") == "scheduling"
    assert _agent("preciso reagendar minha consulta") == "scheduling"
    assert _agent("pode desmarcar e marcar outro dia?") == "scheduling"


def test_cancel_stays_support():
    # Decisão de produto: "cancelar" roteia para suporte (que agora tem a tool de cancelar).
    assert _agent("preciso cancelar meu horário") == "support"


def test_cancellation_policy_not_scheduling():
    assert _agent("qual a política de cancelamento?") != "scheduling"


def test_helper_matches_only_reschedule_verbs():
    assert has_reschedule_intent("quero remarcar")
    assert has_reschedule_intent("reagendar")
    assert has_reschedule_intent("desmarcar")
    assert not has_reschedule_intent("cancelar meu agendamento")
    assert not has_reschedule_intent("qual a política de cancelamento")


def test_guided_guard_lets_reschedule_cancel_reach_agent():
    # Estas frases NÃO devem abrir um novo booking guiado (vão para o agente).
    assert is_reschedule_or_cancel_intent("quero remarcar meu horário")
    assert is_reschedule_or_cancel_intent("cancelar meu horário")
    assert is_reschedule_or_cancel_intent("preciso reagendar")
    # Um novo agendamento NÃO deve ser desviado do guiado.
    assert not is_reschedule_or_cancel_intent("quero agendar corte")
    assert not is_reschedule_or_cancel_intent("tem horário amanhã?")
