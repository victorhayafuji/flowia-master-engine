from tests.conftest import ORG_A, ORG_B


class TestPatientsAPI:
    def test_create_patient_success(self, client, user_token, mock_db):
        mock_table = mock_db.client.table.return_value
        mock_insert = mock_table.insert.return_value
        mock_insert.execute.return_value.type = "execute"
        mock_insert.execute.return_value = type("R", (), {"data": [{"id": "p1", "name": "Maria", "phone": "11999"}]})()

        response = client.post(
            "/api/v1/patients/",
            json={"name": "Maria", "phone": "11999999999"},
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Maria"

    def test_list_patients_success(self, client, user_token, mock_db):
        mock_table = mock_db.client.table.return_value
        mock_select = mock_table.select.return_value
        mock_eq = mock_select.eq.return_value
        mock_eq.eq.return_value = mock_eq
        mock_eq.execute.return_value = type("R", (), {"data": [{"id": "p1"}]})()

        response = client.get(
            "/api/v1/patients/",
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 200
        assert len(response.json()["data"]) == 1

    def test_tenant_spoof_returns_403(self, client, user_token):
        response = client.get(
            "/api/v1/patients/",
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_B},
        )
        assert response.status_code == 403
