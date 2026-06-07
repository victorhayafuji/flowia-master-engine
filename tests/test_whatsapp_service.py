"""Tests for WhatsApp Cloud API outbound service."""
import pytest

from packages.integrations.webhook.whatsapp import WhatsAppService


@pytest.mark.asyncio
async def test_send_text_message_success(mocker):
    mock_db = mocker.patch("packages.integrations.webhook.whatsapp.db")
    mock_table = mock_db.client.table.return_value
    mock_select = mock_table.select.return_value
    mock_eq = mock_select.eq.return_value
    mock_limit = mock_eq.limit.return_value
    mock_limit.execute.return_value = mocker.MagicMock(
        data=[{
            "whatsapp_phone_id": "123456789",
            "whatsapp_access_token": "EAAreal-token-value",
        }]
    )

    mocker.patch(
        "packages.integrations.webhook.whatsapp.get_current_org_id",
        return_value="22222222-2222-2222-2222-222222222222",
    )

    mock_response = mocker.MagicMock()
    mock_response.raise_for_status = mocker.MagicMock()
    mock_client = mocker.AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mocker.AsyncMock(return_value=None)
    mocker.patch(
        "packages.integrations.webhook.whatsapp.httpx.AsyncClient",
        return_value=mock_client,
    )

    service = WhatsAppService()
    ok = await service.send_text_message("5511999999999", "Olá!")
    assert ok is True
    mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_send_text_message_missing_credentials(mocker):
    mock_db = mocker.patch("packages.integrations.webhook.whatsapp.db")
    mock_table = mock_db.client.table.return_value
    mock_select = mock_table.select.return_value
    mock_eq = mock_select.eq.return_value
    mock_limit = mock_eq.limit.return_value
    mock_limit.execute.return_value = mocker.MagicMock(data=[])

    mocker.patch(
        "packages.integrations.webhook.whatsapp.get_current_org_id",
        return_value="22222222-2222-2222-2222-222222222222",
    )

    service = WhatsAppService()
    with pytest.raises(ValueError, match="WhatsApp não configurado"):
        await service.send_text_message("5511999999999", "Olá!")
