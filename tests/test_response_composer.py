"""Tests for scheduling response composer."""
from datetime import date

import pytest

from packages.engine.response_composer import (
    build_template_acknowledgment,
    compose_scheduling_reply,
    factual_guard,
    format_availability_blocks,
    format_time_grid,
    humanize_scheduling_factual,
)

# Hardcoded 2026-06-12 fixtures assume "today" is before that date (CI-safe on any clock).
_FROZEN_TODAY = date(2026, 6, 10)


@pytest.fixture(autouse=True)
def _freeze_today(mocker):
    class _FixedToday(date):
        @classmethod
        def today(cls):
            return cls(_FROZEN_TODAY.year, _FROZEN_TODAY.month, _FROZEN_TODAY.day)

    mocker.patch("packages.engine.response_composer.date", _FixedToday)
    mocker.patch("packages.scheduling.guardrails.date", _FixedToday)


def test_format_time_grid_wraps_in_rows():
    grid = format_time_grid(["13:00", "13:15", "13:30", "14:00", "14:15"])
    assert "  • 13:00" in grid
    assert grid.count("\n") == 1
    assert "14:15" in grid


def test_format_availability_blocks_structured():
    out = format_availability_blocks(
        ["Ana Costa: 13:00, 13:15, 13:30, 14:00, 14:15, 15:00"]
    )
    assert "Com Ana Costa" in out
    assert "13:00" in out
    assert "15:00" in out
    assert "Qual horário funciona melhor" in out
    assert ", 13:15, 13:30" not in out


def test_humanize_anotei_includes_quase_la():
    out = humanize_scheduling_factual(
        "Anotei Corte Masculino no dia 2026-06-11 às 09:00. "
        "Para confirmar, me informe seu nome completo e telefone com DDD."
    )
    assert out.startswith("Quase lá!")
    assert "WhatsApp" in out


def test_humanize_success_includes_professional():
    out = humanize_scheduling_factual(
        "SUCESSO! Agendamento confirmado para Henrique de Souza: "
        "'Corte Masculino' com Maria Silva em 11/06/2026 09:00 (America/Sao_Paulo)."
    )
    assert "com Maria Silva" in out
    assert "Henrique de Souza" in out


def test_compose_skips_ack_on_nao_sei_during_date_clarify():
    factual = (
        "Qual dia você prefere: amanhã (quarta-feira, 10/06) "
        "ou sexta (sexta-feira, 12/06)?"
    )
    out = compose_scheduling_reply(
        factual,
        "Entendi que você deseja agendar para amanhã ou sexta.",
        booking_service="Corte Masculino",
        user_message="Não sei",
    )
    assert "Entendi que você deseja" not in out
    assert "qual dia você prefere" in out.lower()


def test_compose_no_duplicate_service_intro():
    factual = "Para sexta-feira, 12/06, qual serviço você prefere? Temos: Corte Masculino."
    out = compose_scheduling_reply(
        factual,
        None,
        booking_date="2026-06-12",
        user_message="Pode ser para sexta",
    )
    assert out.count("qual serviço") == 1
    assert "Certo!" not in out


def test_humanize_success_uses_full_name():
    out = humanize_scheduling_factual(
        "SUCESSO! Agendamento confirmado para Victor da Silva: "
        "'Corte Masculino' em 12/06/2026 08:00 (America/Sao_Paulo)."
    )
    assert "Victor da Silva" in out
    assert "confirmado para da Silva" not in out


def test_compose_skips_stale_ack_on_date_followup():
    out = compose_scheduling_reply(
        "Para 'Coloração Completa' em sexta-feira, 12/06 não há horários livres. Quer tentar outra data?",
        "Entendi que você está perguntando sobre coloração e preços.",
        booking_service="Coloração Completa",
        booking_date="2026-06-12",
        user_message="Quero agendar para dia 12 de junho",
    )
    assert "Entendi que você está perguntando" not in out
    assert "Perfeito! Separei" not in out
    assert "12/06" in out or "horários" in out.lower()


def test_compose_no_positive_ack_on_availability_question_without_slots():
    factual = (
        "Para 'Coloração Completa' em sexta-feira, 12/06 não há horários livres. "
        "Quer tentar outra data?"
    )
    out = compose_scheduling_reply(
        factual,
        None,
        salon_name="Beauty Express",
        booking_service="Coloração Completa",
        booking_date="2026-06-12",
        user_message="Sim, tem horário para 12 de junho?",
    )
    assert "Perfeito! Separei" not in out
    assert "Poxa, não encontrei horários livres" in out
    assert "sexta-feira, 12/06" in out


def test_compose_with_acknowledgment():
    out = compose_scheduling_reply(
        "Horários: 14:00, 15:00",
        "Entendi, você quer mechas na sexta!",
        user_message="Quero mechas na sexta",
    )
    assert "mechas" in out
    assert "14:00" in out


def test_compose_without_acknowledgment():
    out = compose_scheduling_reply("Qual horário prefere?", None)
    assert out == "Qual horário prefere?"


def test_template_ack_for_mechas_sexta():
    ack = build_template_acknowledgment(
        salon_name="Beauty Express",
        booking_service="Coloração Completa",
        booking_date="2026-06-12",
        user_message="Quero mechas sexta",
    )
    assert ack is not None
    assert "mechas" in ack.lower()


def test_humanize_availability_slots():
    factual = (
        "Horários para 'Coloração Completa' em 2026-06-12 (Brasília / America/Sao_Paulo):\n"
        "- Ana Costa: 14:00, 14:30, 15:00\n\n"
        "Qual horário você prefere? (horário de Brasília)"
    )
    out = humanize_scheduling_factual(
        factual,
        booking_service="Coloração Completa",
        booking_date="2026-06-12",
    )
    assert "14:00" in out
    assert "14:30" in out
    assert "Com Ana Costa" in out
    assert "funciona melhor" in out.lower()
    assert "Horários para" not in out
    assert "12/06" in out or "sexta-feira" in out.lower()


def test_compose_no_seperei_on_generic_miss():
    factual = (
        "Para continuar o agendamento, informe serviço, data, horário, "
        "nome completo e telefone com DDD."
    )
    out = compose_scheduling_reply(
        factual,
        None,
        salon_name="Beauty Express",
        booking_service="Corte Masculino",
        booking_date="2026-06-11",
        user_message="Mas para qual dia?",
    )
    assert "Perfeito! Separei" not in out
    assert "informe serviço" in out.lower()


def test_compose_mechas_flow_end_to_end():
    factual = (
        "Horários para 'Coloração Completa' em 2026-06-12 (Brasília / America/Sao_Paulo):\n"
        "- Ana Costa: 14:00, 15:00\n\n"
        "Qual horário você prefere? (horário de Brasília)"
    )
    out = compose_scheduling_reply(
        factual,
        None,
        salon_name="Beauty Express",
        booking_service="Coloração Completa",
        booking_date="2026-06-12",
        user_message="Quero mechas sexta",
    )
    assert "mechas" in out.lower()
    assert "14:00" in out
    assert "15:00" in out
    assert "Com Ana Costa" in out
    assert "\n  • " in out


def test_humanize_success_message():
    out = humanize_scheduling_factual(
        "SUCESSO! Agendamento confirmado para Maria: 'Coloração' em 12/06/2026 14:00."
    )
    assert out.startswith("Pronto!")
    assert "confirmado" in out.lower()
    assert "14:00" not in out or "14:00" in out


def test_factual_guard_preserves_times():
    factual = "Horários em 2026-06-10: 14:00, 15:30"
    assert factual_guard(factual, factual)


def test_factual_guard_rejects_missing_time():
    factual = "Horários em 2026-06-10: 14:00"
    polished = "Temos vaga em 2026-06-10 às 15:00"
    assert not factual_guard(polished, factual)


def test_compose_no_seperei_ack_on_success():
    factual = "SUCESSO! Agendamento confirmado para João: 'Corte Masculino' em 12/06/2026 11:00."
    out = compose_scheduling_reply(
        factual,
        None,
        salon_name="Beauty Express",
        booking_service="Corte Masculino",
        booking_date="2026-06-12",
        user_message="João da Silva, 11987654444",
    )
    assert "Perfeito! Separei" not in out
    assert "confirmado" in out.lower()


def test_compose_skips_stale_ack_on_catalog_service_reply(mocker):
    mocker.patch(
        "packages.scheduling.booking_executor._is_catalog_service_reply",
        return_value=True,
    )
    out = compose_scheduling_reply(
        "Horários para 'Corte Masculino' em 2026-06-08:\n- Maria: 09:00",
        "Entendi, você deseja agendar um corte de cabelo masculino para amanhã.",
        org_id="22222222-2222-2222-2222-222222222222",
        user_message="Corte masculino",
    )
    assert "Entendi" not in out
    assert "09:00" in out


def test_compose_no_seperei_ack_on_slot_list():
    factual = (
        "Horários para 'Corte Masculino' em 2026-06-12 (Brasília / America/Sao_Paulo):\n"
        "- Maria Silva: 11:00, 11:15\n\n"
        "Qual horário você prefere? (horário de Brasília)"
    )
    out = compose_scheduling_reply(
        factual,
        None,
        salon_name="Beauty Express",
        booking_service="Corte Masculino",
        booking_date="2026-06-12",
        user_message="Quero corte masculino dia 12 de junho",
    )
    assert "Perfeito! Separei" not in out
    assert "11:00" in out
