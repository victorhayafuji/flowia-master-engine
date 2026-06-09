"""Tests for org-scoped thread_id in WhatsApp webhook processing."""
from unittest.mock import AsyncMock, MagicMock

from langchain_core.messages import AIMessage

from packages.compliance.consent import ConsentAction
from packages.integrations.webhook.processor import process_inbound_text_message
from tests.conftest import ORG_A


def test_whatsapp_uses_org_scoped_thread_id(mocker):
    mocker.patch(
        "packages.integrations.webhook.processor.try_claim_message",
        return_value=True,
    )
    mocker.patch(
        "packages.integrations.webhook.processor.evaluate_consent_gate",
        return_value=(ConsentAction.PROCEED, None, True),
    )

    mock_engine = mocker.patch("packages.integrations.webhook.processor.master_engine")
    mock_engine.get_state.return_value = MagicMock(values={})
    mock_engine.ainvoke = AsyncMock(
        return_value={
            "messages": [AIMessage(content="Oi!")],
            "active_agent": "receptionist",
            "handoff_requested": False,
        }
    )

    mock_wa = mocker.patch("packages.integrations.webhook.processor.WhatsAppService")
    wa_instance = MagicMock()
    wa_instance.send_text_message = AsyncMock(return_value=True)
    mock_wa.return_value = wa_instance

    mock_metrics = mocker.patch("packages.integrations.webhook.processor.save_conversation_metric")

    process_inbound_text_message(
        org_id=ORG_A,
        sender_id="5511999999999",
        text_body="Olá",
        message_id="wamid.test-thread",
    )

    invoke_config = mock_engine.ainvoke.await_args.kwargs["config"]
    expected_thread = f"{ORG_A}:5511999999999"
    assert invoke_config["configurable"]["thread_id"] == expected_thread
    mock_metrics.assert_called_once()
    assert mock_metrics.call_args.kwargs["thread_id"] == expected_thread
    assert mock_metrics.call_args.kwargs["sender_id"] == "5511999999999"
