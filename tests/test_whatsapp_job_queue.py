"""Tests for WhatsApp inbound job queue dispatch."""

from packages.integrations.webhook.job_queue import dispatch_whatsapp_payload
from packages.integrations.webhook.schemas import WhatsAppWebhookPayload
from tests.conftest import ORG_A


def _payload(message_id: str = "wamid.queue-1") -> WhatsAppWebhookPayload:
    return WhatsAppWebhookPayload(
        object="whatsapp_business_account",
        entry=[
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "123456789"},
                            "messages": [
                                {
                                    "id": message_id,
                                    "type": "text",
                                    "from": "5511999999999",
                                    "text": {"body": "Olá"},
                                }
                            ],
                        }
                    }
                ]
            }
        ],
    )


def test_dispatch_enqueues_and_processes_inline(mocker):
    mocker.patch("packages.integrations.webhook.job_queue.try_claim_message", return_value=True)
    mocker.patch(
        "packages.integrations.webhook.job_queue.resolve_org_id_from_webhook_value",
        return_value=ORG_A,
    )
    mocker.patch("packages.integrations.webhook.job_queue.enqueue_job", return_value="job-abc")
    mock_process = mocker.patch("packages.integrations.webhook.job_queue.process_job_by_id")

    dispatch_whatsapp_payload(_payload())

    mock_process.assert_called_once_with("job-abc")


def test_dispatch_skips_duplicate_message_id(mocker):
    mocker.patch("packages.integrations.webhook.job_queue.try_claim_message", return_value=False)
    mock_enqueue = mocker.patch("packages.integrations.webhook.job_queue.enqueue_job")

    dispatch_whatsapp_payload(_payload())

    mock_enqueue.assert_not_called()
