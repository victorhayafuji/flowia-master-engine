from uuid import uuid4

from tests.conftest import ORG_A, ORG_B


class TestCatalogAPI:
    def test_create_service_with_professional(self, client, user_token, mock_db):
        professional_id = str(uuid4())
        mock_table = mock_db.client.table.return_value
        mock_insert = mock_table.insert.return_value
        mock_insert.execute.return_value = type(
            "R",
            (),
            {"data": [{"id": "svc-1", "name": "Corte", "professional_id": professional_id}]},
        )()

        response = client.post(
            "/api/v1/organizations/services",
            json={
                "name": "Corte feminino",
                "duration_minutes": 60,
                "price": 120.0,
                "professional_id": professional_id,
            },
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 200
        assert response.json()["data"]["professional_id"] == professional_id

    def test_list_services(self, client, user_token, mock_db):
        mock_table = mock_db.client.table.return_value
        mock_select = mock_table.select.return_value
        mock_eq = mock_select.eq.return_value
        mock_eq.eq.return_value = mock_eq
        mock_eq.execute.return_value = type("R", (), {"data": [{"id": "svc-1"}]})()

        response = client.get(
            "/api/v1/organizations/services",
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 200

    def test_tenant_spoof_returns_403(self, client, user_token):
        response = client.get(
            "/api/v1/organizations/services",
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_B},
        )
        assert response.status_code == 403
