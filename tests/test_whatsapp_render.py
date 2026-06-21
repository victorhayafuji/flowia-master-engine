"""StructuredStep → WhatsApp interactive rendering (no network).

Reply buttons cap at 3 (Meta limit); a step with more options must fall back to a
list instead of silently dropping the extras.
"""
from __future__ import annotations

import asyncio

from packages.integrations.webhook.whatsapp import WhatsAppService


def _opts(n: int):
    return [{"id": str(i), "title": f"Opção {i}"} for i in range(n)]


def _wire(monkeypatch):
    svc = WhatsAppService()
    calls: dict[str, object] = {}

    async def fake_buttons(to, body, options):
        calls["buttons"] = options
        return True

    async def fake_list(to, body, label, rows):
        calls["list"] = rows
        return True

    async def fake_text(to, body):
        calls["text"] = body
        return True

    monkeypatch.setattr(svc, "send_interactive_buttons", fake_buttons)
    monkeypatch.setattr(svc, "send_interactive_list", fake_list)
    monkeypatch.setattr(svc, "send_text_message", fake_text)
    return svc, calls


def test_buttons_step_with_more_than_three_options_uses_list(monkeypatch):
    svc, calls = _wire(monkeypatch)
    step = {"kind": "buttons", "text": "x", "options": _opts(4)}
    asyncio.run(svc.send_structured_step("5511", step))
    assert "list" in calls and "buttons" not in calls


def test_three_options_use_buttons(monkeypatch):
    svc, calls = _wire(monkeypatch)
    step = {"kind": "buttons", "text": "x", "options": _opts(3)}
    asyncio.run(svc.send_structured_step("5511", step))
    assert "buttons" in calls and "list" not in calls


def test_empty_options_fall_back_to_text(monkeypatch):
    svc, calls = _wire(monkeypatch)
    step = {"kind": "list", "text": "olá", "options": []}
    asyncio.run(svc.send_structured_step("5511", step))
    assert calls.get("text") == "olá"
    assert "buttons" not in calls and "list" not in calls
