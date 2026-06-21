"""Explicit LGPD consent buttons in the guided dev chat (dispatch_chat_test)."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

from packages.compliance.consent import ConsentAction
from packages.engine.service import dispatch_chat_test
from packages.scheduling import guided_booking as gb

ORG = "00000000-0000-0000-0000-0000000000aa"


def test_consent_notice_renders_buttons():
    with patch(
        "packages.engine.service.evaluate_consent_gate",
        return_value=(ConsentAction.SEND_NOTICE, "Aviso LGPD — tratamos seus dados...", False),
    ):
        res = asyncio.run(
            dispatch_chat_test("oi", thread_id="t-consent", org_id=ORG, guided_enabled=True)
        )

    assert res["agent"] == "compliance"
    assert res["step"]["step"] == "consent"
    ids = {o["id"] for o in res["step"]["options"]}
    assert ids == {gb.CONSENT_ACCEPT_ID, gb.CONSENT_DECLINE_ID}


def test_consent_accept_records_and_shows_menu():
    with patch("packages.engine.service.record_consent") as rec:
        res = asyncio.run(
            dispatch_chat_test(gb.CONSENT_ACCEPT_ID, thread_id="t-consent", org_id=ORG, guided_enabled=True)
        )
    rec.assert_called_once()
    assert res["step"]["step"] == "menu"


def test_consent_decline_ends_without_recording():
    with patch("packages.engine.service.record_consent") as rec:
        res = asyncio.run(
            dispatch_chat_test(gb.CONSENT_DECLINE_ID, thread_id="t-consent", org_id=ORG, guided_enabled=True)
        )
    rec.assert_not_called()
    assert res["step"] is None
    assert "encerrando" in res["response"].lower()


def test_non_guided_keeps_text_notice():
    """Without guided_enabled (tests / plain callers), the notice stays plain text."""
    with patch(
        "packages.engine.service.evaluate_consent_gate",
        return_value=(ConsentAction.SEND_NOTICE, "Aviso LGPD...", False),
    ):
        res = asyncio.run(
            dispatch_chat_test("oi", thread_id="t-plain", org_id=ORG, guided_enabled=False)
        )
    assert res["agent"] == "compliance"
    assert res.get("step") is None
    assert res.get("lgpd_notice") is True
