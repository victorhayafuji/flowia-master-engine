"""Tests for the payments integration stub (schema/contract only, no execution)."""
import pytest

from packages.integrations.payments import (
    NoOpPaymentProvider,
    PaymentCharge,
    PaymentsNotConfiguredError,
)
from tests.conftest import ORG_A, ORG_B


class TestNoOpProvider:
    def test_disabled_by_default(self):
        provider = NoOpPaymentProvider()
        assert provider.enabled is False

    def test_create_charge_raises(self):
        provider = NoOpPaymentProvider()
        with pytest.raises(PaymentsNotConfiguredError):
            provider.create_charge(PaymentCharge(appointment_id=None, amount_cents=5000))


class TestPaymentsAPI:
    def test_status_disabled(self, client, user_token, mock_db):
        mock_table = mock_db.client.table.return_value
        mock_chain = mock_table.select.return_value.eq.return_value.maybe_single.return_value
        mock_chain.execute.return_value = type("R", (), {"data": {"settings": {}}})()

        response = client.get(
            "/api/v1/integrations/payments/status",
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 200
        assert response.json()["data"]["enabled"] is False

    def test_webhook_not_implemented(self, client):
        response = client.post("/api/v1/integrations/payments/webhook", json={})
        assert response.status_code == 501

    def test_status_tenant_spoof_403(self, client, user_token):
        response = client.get(
            "/api/v1/integrations/payments/status",
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_B},
        )
        assert response.status_code == 403
