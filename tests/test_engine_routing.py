"""Tests for salon agent routing intent detection."""
from langchain_core.messages import AIMessage, HumanMessage

from packages.engine.routing import (
    has_implicit_scheduling_intent,
    has_price_and_scheduling_intent,
    has_scheduling_intent,
    has_temporal_scheduling_intent,
    is_booking_conversation,
    is_price_only_question,
    resolve_triage_agent,
    should_force_scheduling_route,
    triage_source_for,
)


class TestSchedulingIntent:
    def test_detects_agendar_phrase(self):
        assert has_scheduling_intent("Quero agendar coloração na sexta")

    def test_ignores_price_only(self):
        assert not has_scheduling_intent("Quanto custa o corte feminino?")

    def test_implicit_service_and_day(self):
        assert has_implicit_scheduling_intent("Coloração na sexta")

    def test_temporal_week_and_service(self):
        assert has_temporal_scheduling_intent("Preciso ir semana que vem pra fazer um corte")

    def test_price_plus_schedule_not_price_only(self):
        assert has_price_and_scheduling_intent("Quanto fica o corte e tem horário sexta?")
        assert not is_price_only_question("Quanto fica o corte e tem horário sexta?")

    def test_price_only_stays_receptionist(self):
        assert is_price_only_question("Quanto custa o corte feminino?")
        assert resolve_triage_agent([HumanMessage(content="Quanto custa o corte feminino?")], None) == "receptionist"


class TestBookingConversation:
    def test_followup_after_agendar_request(self):
        messages = [
            HumanMessage(content="Quero agendar coloração na sexta."),
            AIMessage(content="Qual tipo de coloração?"),
            HumanMessage(content="Vou querer fazer mechas."),
        ]
        assert is_booking_conversation(messages)

    def test_unrelated_greeting_not_booking(self):
        messages = [HumanMessage(content="Bom dia, tudo bem?")]
        assert not is_booking_conversation(messages)

    def test_phone_reply_after_receptionist_collects_data(self):
        messages = [
            HumanMessage(content="Coloração na sexta"),
            AIMessage(
                content="Para agendar sua coloração na sexta-feira, preciso do seu nome completo e telefone."
            ),
            HumanMessage(content="Sou Victor, 11987654320"),
        ]
        assert is_booking_conversation(messages)

    def test_executor_slot_prompt_counts_as_booking(self):
        messages = [
            HumanMessage(content="Quero corte masculino dia 10 de junho"),
            AIMessage(
                content=(
                    "Horários para 'Corte Masculino' em 2026-06-10:\n"
                    "- Maria: 14:00\n\nQual horário você prefere?"
                )
            ),
            HumanMessage(content="14:00"),
        ]
        assert is_booking_conversation(messages)
        assert should_force_scheduling_route(messages)
        assert triage_source_for(messages) == "conversation"


class TestResolveTriageAgent:
    def test_first_message_agendar_goes_scheduling(self):
        messages = [HumanMessage(content="Quero agendar coloração na sexta")]
        assert resolve_triage_agent(messages, None) == "scheduling"

    def test_service_and_day_goes_scheduling(self):
        messages = [HumanMessage(content="Coloração na sexta")]
        assert resolve_triage_agent(messages, None) == "scheduling"

    def test_mechas_followup_escapes_receptionist(self):
        messages = [
            HumanMessage(content="Quero agendar coloração na sexta."),
            AIMessage(content="Qual tipo?"),
            HumanMessage(content="Vou querer fazer mechas."),
        ]
        assert resolve_triage_agent(messages, "receptionist") == "scheduling"

    def test_cancel_goes_support(self):
        messages = [HumanMessage(content="Preciso cancelar meu horário")]
        assert resolve_triage_agent(messages, "receptionist") == "support"

    def test_chat_test_reproduction_flow(self):
        messages = [
            HumanMessage(content="Quero agendar coloração na sexta"),
            AIMessage(content="Preciso do seu nome completo e telefone para agendar."),
            HumanMessage(content="Sou Victor, 11987654320"),
            AIMessage(content="Qual horário prefere?"),
            HumanMessage(content="Tem agendamento para às 11:00?"),
        ]
        assert resolve_triage_agent(messages, "receptionist", booking_active=True) == "scheduling"

    def test_booking_active_keeps_scheduling_on_short_reply(self):
        messages = [
            HumanMessage(content="Quero agendar coloração na sexta"),
            AIMessage(content="Preciso do telefone."),
            HumanMessage(content="11987654320"),
        ]
        assert resolve_triage_agent(messages, "receptionist", booking_active=True) == "scheduling"
