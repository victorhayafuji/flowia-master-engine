"""Catalog routers must never leak raw exception text in the HTTP response.

Mirrors the str(e) hardening landed for clients/router.py (PR #41): an internal
failure surfaces a generic PT-BR message, the raw exception string stays out of
`detail`, and the error is logged via logger.exception (detail only in the log).
"""
from tests.conftest import ORG_A

_SECRET = "supabase connection string postgres://user:pass@host"


class TestCatalogErrorLeak:
    def test_create_service_internal_error_is_generic(
        self, client, user_token, mock_db, mocker
    ):
        # insert(...).execute() raises with a sensitive message.
        mock_table = mock_db.client.table.return_value
        mock_table.insert.return_value.execute.side_effect = RuntimeError(_SECRET)

        spy = mocker.spy(
            __import__(
                "apps.salon.domain.catalog.routers.services",
                fromlist=["logger"],
            ).logger,
            "exception",
        )

        response = client.post(
            "/api/v1/organizations/services",
            json={"name": "Corte", "duration_minutes": 60, "price": 100.0},
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail == "Erro ao criar serviço."
        # Raw exception text must NOT reach the client.
        assert _SECRET not in detail
        assert "postgres://" not in detail
        # Detail belongs in the log, not the response.
        spy.assert_called_once()

    def test_list_professionals_internal_error_is_generic(
        self, client, user_token, mock_db
    ):
        mock_table = mock_db.client.table.return_value
        mock_table.select.return_value.eq.return_value.eq.return_value.execute.side_effect = (
            RuntimeError(_SECRET)
        )

        response = client.get(
            "/api/v1/organizations/professionals",
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Erro ao listar profissionais."
        assert _SECRET not in response.text
