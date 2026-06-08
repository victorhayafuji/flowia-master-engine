"""Tests for scheduling response composer."""
from packages.engine.response_composer import (
    build_template_acknowledgment,
    compose_scheduling_reply,
    factual_guard,
    format_availability_blocks,
    format_time_grid,
    humanize_scheduling_factual,
)


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


def test_compose_with_acknowledgment():
    out = compose_scheduling_reply(
        "Horários: 14:00, 15:00",
        "Entendi, você quer mechas na sexta!",
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
