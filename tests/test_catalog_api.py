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
        # Every service carries M:N eligibility for the UI (empty = all professionals).
        assert response.json()["data"][0]["professional_ids"] == []

    def test_list_services_attaches_professional_ids(self, client, user_token, mock_db, mocker):
        svc_a, svc_b, svc_c = "svc-a", "svc-b", "svc-c"
        prof_1, legacy_pid = str(uuid4()), str(uuid4())

        def _table(name):
            chain = mocker.MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            if name == "service_catalog":
                chain.execute.return_value = type(
                    "R",
                    (),
                    {
                        "data": [
                            {"id": svc_a, "professional_id": None},  # M:N
                            {"id": svc_b, "professional_id": None},  # nothing
                            {"id": svc_c, "professional_id": legacy_pid},  # legacy FK only
                        ]
                    },
                )()
            elif name == "service_professionals":
                chain.execute.return_value = type(
                    "R", (), {"data": [{"service_id": svc_a, "professional_id": prof_1}]}
                )()
            else:
                chain.execute.return_value = type("R", (), {"data": []})()
            return chain

        mock_db.client.table.side_effect = _table

        response = client.get(
            "/api/v1/organizations/services",
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 200
        by_id = {s["id"]: s["professional_ids"] for s in response.json()["data"]}
        assert by_id[svc_a] == [prof_1]  # M:N eligibility wins
        assert by_id[svc_b] == []  # no rows, no legacy = fallback (all professionals)
        assert by_id[svc_c] == [legacy_pid]  # legacy FK fallback when no M:N

    def test_tenant_spoof_returns_403(self, client, user_token):
        response = client.get(
            "/api/v1/organizations/services",
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_B},
        )
        assert response.status_code == 403
