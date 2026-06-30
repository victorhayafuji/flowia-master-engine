"""Kiosk (totem) device provisioning endpoints — scoped to the caller's tenant."""
from tests.conftest import ORG_A


def _R(data):
    return type("R", (), {"data": data})()


class TestKioskDevicesAPI:
    def test_create_returns_token_once(self, client, user_token, mock_db):
        table = mock_db.client.table.return_value
        table.insert.return_value.execute.return_value = _R(
            [{"id": "dev-1", "label": "Recepção"}]
        )

        resp = client.post(
            "/api/v1/organizations/kiosk-devices",
            json={"label": "Recepção"},
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == "dev-1"
        assert data["token"].startswith("kdev_")  # raw token returned exactly once

    def test_create_rejects_empty_label(self, client, user_token, mock_db):
        resp = client.post(
            "/api/v1/organizations/kiosk-devices",
            json={"label": "   "},
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert resp.status_code == 400

    def test_list_omits_token(self, client, user_token, mock_db):
        table = mock_db.client.table.return_value
        table.select.return_value.eq.return_value.order.return_value.execute.return_value = _R(
            [{"id": "dev-1", "label": "Recepção", "is_active": True}]
        )

        resp = client.get(
            "/api/v1/organizations/kiosk-devices",
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert resp.status_code == 200
        rows = resp.json()["data"]
        assert rows and "token" not in rows[0] and "token_hash" not in rows[0]

    def test_revoke_ok(self, client, user_token, mock_db):
        table = mock_db.client.table.return_value
        table.update.return_value.eq.return_value.eq.return_value.execute.return_value = _R(
            [{"id": "dev-1", "is_active": False}]
        )

        resp = client.delete(
            "/api/v1/organizations/kiosk-devices/dev-1",
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["revoked"] is True

    def test_revoke_missing_returns_404(self, client, user_token, mock_db):
        table = mock_db.client.table.return_value
        table.update.return_value.eq.return_value.eq.return_value.execute.return_value = _R([])

        resp = client.delete(
            "/api/v1/organizations/kiosk-devices/nope",
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert resp.status_code == 404
