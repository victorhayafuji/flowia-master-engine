"""Tests for white-label salon prompts."""
from packages.engine.prompts import (
    build_guardrails,
    build_receptionist_prompt,
    build_scheduling_prompt,
    build_support_prompt,
    register_salon_prompts,
)


class TestSalonPrompts:
    @classmethod
    def setup_class(cls):
        register_salon_prompts()
    def test_prompts_do_not_mention_flowia(self):
        salon = "Salão Beauty Express"
        for builder in (
            build_guardrails,
            build_receptionist_prompt,
            build_support_prompt,
            build_scheduling_prompt,
        ):
            text = builder(salon).lower()
            assert "flowia" not in text

    def test_guardrails_use_salon_name(self):
        text = build_guardrails("Studio Cabelo & Arte")
        assert "Studio Cabelo & Arte" in text

    def test_scheduling_uses_cliente_not_paciente(self):
        text = build_scheduling_prompt("Beauty Express").lower()
        assert "cliente" in text
        assert "paciente" not in text
        assert "clínica" not in text and "clinica" not in text

    def test_scheduling_includes_date_context(self):
        text = build_scheduling_prompt("Beauty Express")
        assert "CONTEXTO DE DATA" in text
        assert "check_availability" in text

    def test_receptionist_mentions_search_kb(self):
        text = build_receptionist_prompt("Beauty Express")
        assert "search_kb" in text
