"""Tests for WhatsApp webhook tenant resolution."""
from packages.integrations.webhook.tenant_resolver import resolve_org_id_from_webhook_value


class TestWebhookTenantResolver:
    def test_resolves_org_by_phone_number_id(self, mocker):
        mock_db = mocker.patch("packages.integrations.webhook.tenant_resolver.db")
        mock_table = mock_db.client.table.return_value
        mock_select = mock_table.select.return_value
        mock_eq = mock_select.eq.return_value
        mock_limit = mock_eq.limit.return_value
        mock_limit.execute.return_value = mocker.MagicMock(
            data=[{"id": "22222222-2222-2222-2222-222222222222"}]
        )

        value = {"metadata": {"phone_number_id": "999888777"}}
        org_id = resolve_org_id_from_webhook_value(value)

        assert org_id == "22222222-2222-2222-2222-222222222222"
        mock_select.eq.assert_called_with("whatsapp_phone_id", "999888777")

    def test_fallback_when_no_metadata(self, mocker):
        mock_db = mocker.patch("packages.integrations.webhook.tenant_resolver.db")
        mock_table = mock_db.client.table.return_value
        mock_select = mock_table.select.return_value
        mock_limit = mock_select.limit.return_value
        mock_limit.execute.return_value = mocker.MagicMock(
            data=[{"id": "fallback-org-id"}]
        )

        org_id = resolve_org_id_from_webhook_value({})

        assert org_id == "fallback-org-id"
