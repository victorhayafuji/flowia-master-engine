"""Tests for the self-service WhatsApp config endpoints (org_admin scoped)."""
from unittest.mock import AsyncMock, MagicMock

from packages.integrations.webhook.whatsapp import WhatsAppService
from tests.conftest import ORG_A, ORG_B


def _chain(mock_db):
    """A fluent Supabase chain that returns itself for query builders."""
    chain = mock_db.client.table.return_value
    chain.select.return_value = chain
    chain.update.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    return chain


def _resp(data):
    r = MagicMock()
    r.data = data
    return r


def test_get_whatsapp_masks_token(client, user_token, mock_db):
    chain = _chain(mock_db)
    chain.execute.return_value = _resp([
        {
            "whatsapp_phone_id": "123456789",
            "whatsapp_access_token": "EAAsupersecrettoken1234",
            "whatsapp_business_id": "biz-1",
        }
    ])

    res = client.get(
        "/api/v1/organizations/whatsapp",
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_A},
    )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["whatsapp_phone_id"] == "123456789"
    assert data["whatsapp_business_id"] == "biz-1"
    assert data["token_configured"] is True
    assert data["token_preview"] == "••••1234"
    # Raw token must never reach the client.
    assert "EAAsupersecrettoken1234" not in res.text
    # Verify token is exposed for the owner to configure their Meta webhook.
    assert data["verify_token"]
    # Webhook URL is the public API (never localhost) so Meta can reach it.
    assert data["webhook_url"].endswith("/webhook/whatsapp")
    assert "localhost" not in data["webhook_url"]


def test_patch_whatsapp_updates_columns(client, user_token, mock_db):
    chain = _chain(mock_db)
    chain.execute.return_value = _resp([{"id": ORG_A}])

    res = client.patch(
        "/api/v1/organizations/whatsapp",
        json={
            "whatsapp_phone_id": "999",
            "whatsapp_access_token": "EAAnewtoken",
            "whatsapp_business_id": "biz",
        },
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_A},
    )

    assert res.status_code == 200
    assert res.json()["data"]["updated"] is True
    sent = chain.update.call_args[0][0]
    assert sent["whatsapp_phone_id"] == "999"
    assert sent["whatsapp_access_token"] == "EAAnewtoken"
    assert sent["whatsapp_business_id"] == "biz"
    # Saved token is not echoed back.
    assert "EAAnewtoken" not in res.text


def test_patch_whatsapp_blank_token_kept(client, user_token, mock_db):
    chain = _chain(mock_db)
    chain.execute.return_value = _resp([{"id": ORG_A}])

    res = client.patch(
        "/api/v1/organizations/whatsapp",
        json={"whatsapp_phone_id": "999", "whatsapp_access_token": ""},
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_A},
    )

    assert res.status_code == 200
    sent = chain.update.call_args[0][0]
    # Blank token must not overwrite the saved one.
    assert "whatsapp_access_token" not in sent
    assert sent["whatsapp_phone_id"] == "999"


def test_patch_whatsapp_phone_conflict(client, user_token, mock_db):
    chain = _chain(mock_db)
    chain.execute.side_effect = Exception(
        'duplicate key value violates unique constraint "idx_organizations_whatsapp_phone_id_unique"'
    )

    res = client.patch(
        "/api/v1/organizations/whatsapp",
        json={"whatsapp_phone_id": "999"},
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_A},
    )

    assert res.status_code == 422
    assert "whatsapp_phone_id" in res.json()["detail"]


def test_test_connection_success(client, user_token, mock_db, mocker):
    mocker.patch.object(
        WhatsAppService,
        "verify_credentials",
        new=AsyncMock(
            return_value={
                "ok": True,
                "verified_name": "Salão X",
                "display_phone_number": "+55 11 99999-0000",
            }
        ),
    )

    res = client.post(
        "/api/v1/organizations/whatsapp/test",
        json={"whatsapp_phone_id": "123", "whatsapp_access_token": "EAAtoken"},
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_A},
    )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["ok"] is True
    assert data["verified_name"] == "Salão X"
    assert data["display_phone_number"] == "+55 11 99999-0000"


def test_test_connection_uses_stored_token_when_blank(client, user_token, mock_db, mocker):
    chain = _chain(mock_db)
    chain.execute.return_value = _resp([
        {
            "whatsapp_phone_id": "stored-phone",
            "whatsapp_access_token": "EAAstoredtoken",
        }
    ])
    spy = AsyncMock(return_value={"ok": True, "verified_name": "S", "display_phone_number": "x"})
    mocker.patch.object(WhatsAppService, "verify_credentials", new=spy)

    res = client.post(
        "/api/v1/organizations/whatsapp/test",
        json={},  # nothing typed → fall back to stored credentials
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_A},
    )

    assert res.status_code == 200
    phone_arg, token_arg = spy.await_args[0]
    assert phone_arg == "stored-phone"
    assert token_arg == "EAAstoredtoken"


def test_test_connection_failure_is_friendly(client, user_token, mock_db, mocker):
    mocker.patch.object(
        WhatsAppService,
        "verify_credentials",
        new=AsyncMock(return_value={"ok": False, "error": "Credenciais inválidas ou sem permissão."}),
    )

    res = client.post(
        "/api/v1/organizations/whatsapp/test",
        json={"whatsapp_phone_id": "1", "whatsapp_access_token": "EAAx"},
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_A},
    )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["ok"] is False
    assert "inválid" in data["error"].lower()


def test_whatsapp_cross_org_forbidden(client, user_token, mock_db):
    # org_admin of ORG_A pointing the header at ORG_B → tenant_context rejects.
    res = client.get(
        "/api/v1/organizations/whatsapp",
        cookies={"session_token": user_token},
        headers={"x-organization-id": ORG_B},
    )
    assert res.status_code == 403
