"""Tests for webhook tenant resolution (fail-closed)."""
from unittest.mock import MagicMock

from packages.integrations.webhook import tenant_resolver


class TestTenantResolver:
    def test_returns_none_without_phone_number_id(self, mocker):
        org = tenant_resolver.resolve_org_id_from_webhook_value({"metadata": {}})
        assert org is None

    def test_returns_org_when_matched(self, mocker):
        mock_db = MagicMock()
        mock_db.client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"id": "22222222-2222-2222-2222-222222222222"}]
        )
        mocker.patch.object(tenant_resolver, "db", mock_db)

        org = tenant_resolver.resolve_org_id_from_webhook_value(
            {"metadata": {"phone_number_id": "12345"}}
        )
        assert org == "22222222-2222-2222-2222-222222222222"

    def test_no_fallback_to_first_org(self, mocker):
        mock_db = MagicMock()
        mock_db.client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[]
        )
        mocker.patch.object(tenant_resolver, "db", mock_db)
        mocker.patch.object(tenant_resolver.settings, "SIM_WHATSAPP_ORG_ID", "")

        org = tenant_resolver.resolve_org_id_from_webhook_value(
            {"metadata": {"phone_number_id": "unknown"}}
        )
        assert org is None

    def test_sim_whatsapp_org_override(self, mocker):
        mocker.patch.object(
            tenant_resolver.settings,
            "SIM_WHATSAPP_ORG_ID",
            "22222222-2222-2222-2222-222222222222",
        )
        mocker.patch.object(tenant_resolver.settings, "SIM_WHATSAPP_PHONE_ID", "123456789")
        org = tenant_resolver.resolve_org_id_from_webhook_value(
            {"metadata": {"phone_number_id": "123456789"}}
        )
        assert org == "22222222-2222-2222-2222-222222222222"
