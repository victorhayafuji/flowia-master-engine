"""Tests for the WhatsApp webhook routes."""
import hashlib
import hmac
import json

import pytest

from packages.auth_core.config import settings


def _make_signature(body: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _make_whatsapp_payload(message_id: str = "msg_001", text: str = "Olá") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry_1",
                "changes": [
                    {
                        "value": {
                            "metadata": {
                                "display_phone_number": "5511999999999",
                                "phone_number_id": "123456789",
                            },
                            "messages": [
                                {
                                    "id": message_id,
                                    "from": "5511999999999",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


class TestWebhookVerification:
    def test_valid_challenge_returns_200(self, client):
        response = client.get(
            "/api/v1/webhook/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "test_challenge_123",
                "hub.verify_token": settings.WHATSAPP_VERIFY_TOKEN,
            },
        )
        assert response.status_code == 200
        assert response.text == "test_challenge_123"

    def test_invalid_token_returns_403(self, client):
        response = client.get(
            "/api/v1/webhook/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "test_challenge",
                "hub.verify_token": "wrong_token",
            },
        )
        assert response.status_code == 403


class TestWebhookPost:
    def test_valid_payload_returns_success(self, client, mocker):
        mocker.patch("packages.integrations.webhook.router.process_message_in_background")

        payload = _make_whatsapp_payload()
        body = json.dumps(payload).encode()

        headers = {}
        if settings.WHATSAPP_APP_SECRET:
            headers["X-Hub-Signature-256"] = _make_signature(body, settings.WHATSAPP_APP_SECRET)

        response = client.post(
            "/api/v1/webhook/whatsapp",
            content=body,
            headers={"Content-Type": "application/json", **headers},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    def test_invalid_signature_returns_403(self, client):
        if not settings.WHATSAPP_APP_SECRET:
            pytest.skip("WHATSAPP_APP_SECRET not configured")

        payload = _make_whatsapp_payload()
        body = json.dumps(payload).encode()

        response = client.post(
            "/api/v1/webhook/whatsapp",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalid_signature",
            },
        )
        assert response.status_code == 403

    def test_oversized_payload_returns_413(self, client):
        response = client.post(
            "/api/v1/webhook/whatsapp",
            content=b'{"object":"x","entry":[]}',
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(2 * 1024 * 1024),
            },
        )
        assert response.status_code == 413

    def test_invalid_json_returns_error(self, client):
        headers = {}
        body = b"not-valid-json{{"
        if settings.WHATSAPP_APP_SECRET:
            headers["X-Hub-Signature-256"] = _make_signature(body, settings.WHATSAPP_APP_SECRET)

        response = client.post(
            "/api/v1/webhook/whatsapp",
            content=body,
            headers={"Content-Type": "application/json", **headers},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "error"
