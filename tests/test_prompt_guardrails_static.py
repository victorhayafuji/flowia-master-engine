"""Static checks on salon prompt guardrails."""
from apps.salon.prompts import build_guardrails


def test_build_guardrails_anti_hijack_and_tone():
    text = build_guardrails("Beauty Express")
    upper = text.upper()
    assert "RECUSA DE HIJACK" in upper
    assert "ANTI-TONE-HIJACK" in upper
    assert "confirmar com a equipe" not in text.lower()
