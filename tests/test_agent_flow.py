"""Testes de fluxo multi-turno pelo motor real (como Chat Test).

Rode quando estiver iterando no agente:

    py -3.12 -m pytest tests/test_agent_flow.py -v
    py -3.12 -m pytest -m agent_flow -v
    py -3.12 -m pytest tests/test_agent_flow.py -k receptionist -v
"""
from __future__ import annotations

import pytest

from tests.support.agent_flow import NO_AVAILABILITY

# ---------------------------------------------------------------------------
# Recepcionista — preços e informações (determinístico, catálogo fallback)
# ---------------------------------------------------------------------------


@pytest.mark.agent_flow
class TestAgentFlowReceptionist:
    @pytest.mark.asyncio
    async def test_coloracao_price_deterministic(self, agent_flow):
        turn = await agent_flow().say("Vocês fazem coloração? Qual o preço?")

        assert turn.agent == "receptionist"
        assert turn.receptionist_path == "deterministic"
        assert turn.tokens_used == 0
        assert "R$ 250" in turn.message
        assert "confirmar com a equipe" not in turn.message.lower()

    @pytest.mark.asyncio
    async def test_corte_masculino_price(self, agent_flow):
        turn = await agent_flow().say("Quanto custa o corte masculino?")

        assert turn.agent == "receptionist"
        assert "R$ 80" in turn.message

    @pytest.mark.asyncio
    async def test_generic_prices_lists_catalog(self, agent_flow):
        turn = await agent_flow().say("Quais são os preços?")

        assert turn.agent == "receptionist"
        assert "R$" in turn.message
        assert turn.tokens_used == 0

    @pytest.mark.asyncio
    async def test_mechas_service_inquiry(self, agent_flow):
        turn = await agent_flow().say("Vocês fazem mechas?")

        assert turn.agent == "receptionist"
        assert "R$ 250" in turn.message or "Coloração" in turn.message

    @pytest.mark.asyncio
    async def test_unknown_service_honest_reply(self, agent_flow):
        turn = await agent_flow().say("Quanto custa podologia?")

        assert turn.agent == "receptionist"
        lower = turn.message.lower()
        assert "confirmar com a equipe" not in lower
        assert "nenhuma informação" in lower or "não encontrei" in lower or "catálogo" in lower


# ---------------------------------------------------------------------------
# Coloração → agendamento (fluxo principal do MVP)
# ---------------------------------------------------------------------------


@pytest.mark.agent_flow
class TestAgentFlowColoracao:
    @pytest.mark.asyncio
    async def test_price_then_june12_availability(self, agent_flow):
        flow = agent_flow()
        t1, t2 = await flow.say_many(
            "Vocês fazem coloração? Qual o preço?",
            "Sim, tem horário para 12 de junho?",
        )

        assert t1.agent == "receptionist"
        assert "R$ 250" in t1.message

        assert t2.agent == "scheduling"
        assert t2.scheduling_path == "deterministic"
        assert t2.tokens_used == 0
        assert "14:00" in t2.message
        assert "Perfeito! Separei" not in t2.message

    @pytest.mark.asyncio
    async def test_price_then_june12_no_slots_honest_reply(self, agent_flow):
        flow = agent_flow(availability_response=NO_AVAILABILITY)
        t1, t2 = await flow.say_many(
            "Vocês fazem coloração? Qual o preço?",
            "Sim, tem horário para 12 de junho?",
        )

        assert "R$ 250" in t1.message
        assert t2.agent == "scheduling"
        assert "Perfeito! Separei" not in t2.message
        assert "horários livres" in t2.message.lower()
        assert "sexta-feira, 12/06" in t2.message or "12/06" in t2.message

    @pytest.mark.asyncio
    async def test_same_thread_preserves_service_context(self, agent_flow):
        flow = agent_flow()
        await flow.say("Vocês fazem coloração? Qual o preço?")
        t2 = await flow.say("Sim, tem horário para 12 de junho?")

        assert t2.agent == "scheduling"
        assert t2.scheduling_path == "deterministic"
        assert "14:00" in t2.message

    @pytest.mark.asyncio
    async def test_no_slots_then_another_day(self, agent_flow):
        flow = agent_flow(availability_response=NO_AVAILABILITY)
        await flow.say("Vocês fazem coloração? Qual o preço?")
        await flow.say("Sim, tem horário para 12 de junho?")
        t3 = await flow.say("E para dia 10 de junho, tem vaga?")

        assert t3.agent == "scheduling"
        assert "Perfeito! Separei" not in t3.message
        assert "10:00" in t3.message or "11:00" in t3.message or "13:00" in t3.message or "horário" in t3.message.lower()


# ---------------------------------------------------------------------------
# Roteamento — saudação, welcome, support
# ---------------------------------------------------------------------------


@pytest.mark.agent_flow
class TestAgentFlowRouting:
    @pytest.mark.asyncio
    async def test_greeting_not_scheduling(self, agent_flow):
        turn = await agent_flow().say("Bom dia, tudo bem?")

        assert turn.agent == "receptionist"
        assert turn.agent != "scheduling"

    @pytest.mark.asyncio
    async def test_cancel_policy_goes_support(self, agent_flow):
        turn = await agent_flow().say("Qual a política de cancelamento?")

        assert turn.agent == "support"
        assert turn.handoff is False

    @pytest.mark.asyncio
    async def test_cancel_with_horario_routes_support(self, agent_flow):
        turn = await agent_flow().say("Preciso cancelar meu horário")

        assert turn.agent == "support"

    @pytest.mark.asyncio
    async def test_faltei_ontem_support_deterministic(self, agent_flow):
        turn = await agent_flow().say("Faltei ontem")

        assert turn.agent == "support"
        assert "06/" in turn.message or "ausência" in turn.message.lower() or "refer" in turn.message.lower()

    @pytest.mark.asyncio
    async def test_cancel_anteontem_support(self, agent_flow):
        turn = await agent_flow().say("Preciso cancelar o horário de anteontem")

        assert turn.agent == "support"

    @pytest.mark.asyncio
    async def test_agendar_ontem_no_slots(self, agent_flow):
        turn = await agent_flow().say("Quero agendar manicure ontem")

        assert turn.agent == "scheduling"
        assert "a partir de hoje" in turn.message.lower() or "qual dia" in turn.message.lower()
        assert "14:00" not in turn.message

    @pytest.mark.asyncio
    async def test_welcome_then_coloracao_price_stays_receptionist(self, agent_flow):
        flow = agent_flow()
        await flow.say("Sim, concordo")
        t2 = await flow.say("Vocês fazem coloração? Qual o preço?")

        assert t2.agent == "receptionist"
        assert "R$ 250" in t2.message

    @pytest.mark.asyncio
    async def test_price_plus_schedule_same_turn(self, agent_flow):
        turn = await agent_flow().say("Quanto fica o corte e tem horário na sexta?")

        assert turn.agent == "scheduling"
        assert turn.scheduling_path == "deterministic"


# ---------------------------------------------------------------------------
# Agendamento — datas, horários, confirmação
# ---------------------------------------------------------------------------


@pytest.mark.agent_flow
class TestAgentFlowScheduling:
    @pytest.mark.asyncio
    async def test_direct_booking_lists_slots(self, agent_flow):
        turn = await agent_flow().say("Quero agendar corte masculino dia 10 de junho")

        assert turn.agent == "scheduling"
        assert turn.scheduling_path == "deterministic"
        assert "13:00" in turn.message or "14:00" in turn.message

    @pytest.mark.asyncio
    async def test_mechas_sexta_lists_slots(self, agent_flow):
        turn = await agent_flow().say("Quero mechas sexta")

        assert turn.agent == "scheduling"
        assert turn.scheduling_path == "deterministic"
        assert "14:00" in turn.message or "15:00" in turn.message

    @pytest.mark.asyncio
    async def test_pick_time_asks_contact(self, agent_flow):
        flow = agent_flow()
        await flow.say("Quero corte masculino dia 10 de junho")
        turn = await flow.say("13:00")

        assert turn.agent == "scheduling"
        assert "nome" in turn.message.lower()
        assert "whatsapp" in turn.message.lower() or "telefone" in turn.message.lower()

    @pytest.mark.asyncio
    async def test_sim_after_slots_lists_again(self, agent_flow):
        flow = agent_flow()
        await flow.say("Quero corte masculino dia 10 de junho")
        turn = await flow.say("Sim, tem algum outro horário?")

        assert turn.agent == "scheduling"
        assert "13:00" in turn.message or "14:00" in turn.message

    @pytest.mark.asyncio
    async def test_full_booking_message_confirms(self, agent_flow):
        flow = agent_flow(mock_booking_success=True)
        turn = await flow.say(
            "Quero agendar um corte masculino para quarta dia 10 de junho as 11:00, "
            "meu nome e Joao Silva, telefone 11987654323"
        )

        assert turn.agent in ("scheduling", "receptionist")
        assert turn.scheduling_path == "deterministic"
        assert "confirmado" in turn.message.lower() or "SUCESSO" in turn.message

    @pytest.mark.asyncio
    async def test_time_with_contact_in_history_books(self, agent_flow):
        flow = agent_flow(mock_booking_success=True)
        await flow.say("Quero corte masculino dia 10 de junho")
        await flow.say("Meu nome e Pedro Silva, telefone 11987654353")
        turn = await flow.say("13:00")

        assert turn.agent in ("scheduling", "receptionist")
        assert "confirmado" in turn.message.lower() or "SUCESSO" in turn.message

    @pytest.mark.asyncio
    async def test_thanks_after_booking_returns_to_receptionist(self, agent_flow):
        flow = agent_flow(mock_booking_success=True)
        await flow.say("Quero corte masculino dia 10 de junho")
        await flow.say("Meu nome e Joao Silva, telefone 11987654323")
        confirm = await flow.say("11:00")
        assert confirm.agent in ("scheduling", "receptionist")
        assert "confirmado" in confirm.message.lower() or "SUCESSO" in confirm.message

        thanks = await flow.say("Otimo, obrigado!")
        assert thanks.agent == "receptionist"
        assert "Por nada" in thanks.message or "obrigad" in thanks.message.lower()
        assert "Qual horário funciona melhor" not in thanks.message

    @pytest.mark.asyncio
    async def test_vague_agendar_lists_catalog(self, agent_flow):
        turn = await agent_flow().say("Quero agendar")

        assert turn.agent == "scheduling"
        assert "Corte Masculino" in turn.message or "Coloração" in turn.message

    @pytest.mark.asyncio
    async def test_date_only_asks_service(self, agent_flow):
        turn = await agent_flow().say("Quero agendar para dia 12 de junho")

        assert turn.agent == "scheduling"
        assert "serviço" in turn.message.lower() or "Corte" in turn.message

    @pytest.mark.asyncio
    async def test_semana_que_vem_asks_day_not_slots(self, agent_flow):
        turn = await agent_flow().say("Quero coloração semana que vem")

        assert turn.agent == "scheduling"
        assert "qual dia" in turn.message.lower() or "semana que vem" in turn.message.lower()
        assert "14:00" not in turn.message and "09:00" not in turn.message

    @pytest.mark.asyncio
    async def test_sexta_ou_sabado_asks_preference(self, agent_flow):
        turn = await agent_flow().say("Quero manicure sexta ou sabado")

        assert turn.agent == "scheduling"
        assert "sexta" in turn.message.lower() and "sabado" in turn.message.lower()


# ---------------------------------------------------------------------------
# LGPD — aviso no primeiro contato
# ---------------------------------------------------------------------------


@pytest.mark.agent_flow
class TestAgentFlowLGPD:
    @pytest.mark.asyncio
    async def test_first_message_sends_notice(self, agent_flow):
        turn = await agent_flow(consent_mode="lgpd_two_step").say("Olá")

        assert turn.agent == "compliance"
        assert turn.raw.get("lgpd_notice") is True
        assert "LGPD" in turn.message or "dados" in turn.message.lower()

    @pytest.mark.asyncio
    async def test_second_message_after_notice_runs_agent(self, agent_flow):
        flow = agent_flow(consent_mode="lgpd_two_step")
        await flow.say("Olá")
        turn = await flow.say("Quanto custa coloração?")

        assert turn.agent == "receptionist"
        assert "R$ 250" in turn.message


# ---------------------------------------------------------------------------
# RAG — quando a base tem hit, catálogo não é necessário
# ---------------------------------------------------------------------------


@pytest.mark.agent_flow
class TestAgentFlowRAG:
    @pytest.mark.asyncio
    async def test_rag_hit_used_for_price(self, agent_flow):
        turn = await agent_flow(
            rag_results=[{"content": "Coloração premium: R$ 999 (120 min)", "similarity": 0.9}]
        ).say("Quanto custa coloração premium?")

        assert turn.agent == "receptionist"
        assert "999" in turn.message or "R$" in turn.message
