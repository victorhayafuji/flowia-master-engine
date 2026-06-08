"""Tests for RAG-enabled chat test endpoint and search_kb tenant isolation."""
from unittest.mock import AsyncMock

from packages.auth_core.tenant import get_current_org_id, set_tenant_context
from packages.engine.tools import search_kb
from tests.conftest import ORG_A, ORG_B


class TestChatTestEndpoint:
    def test_chat_test_requires_auth(self, client):
        response = client.post(
            "/api/v1/chat/test",
            json={"message": "quanto custa corte feminino"},
            headers={"x-organization-id": ORG_A},
        )
        assert response.status_code == 401

    def test_chat_test_requires_org_header(self, client, user_token):
        response = client.post(
            "/api/v1/chat/test",
            json={"message": "quanto custa corte feminino"},
            cookies={"session_token": user_token},
        )
        assert response.status_code == 422

    def test_chat_test_rejects_all_org_for_org_admin(self, client, user_token):
        response = client.post(
            "/api/v1/chat/test",
            json={"message": "preços"},
            cookies={"session_token": user_token},
            headers={"x-organization-id": "ALL"},
        )
        assert response.status_code == 403

    def test_chat_test_rejects_all_org_for_super_admin(self, client, admin_token):
        response = client.post(
            "/api/v1/chat/test",
            json={"message": "preços"},
            cookies={"session_token": admin_token},
            headers={"x-organization-id": "ALL"},
        )
        assert response.status_code == 400

    def test_chat_test_sets_tenant(self, client, user_token, mocker):
        captured: dict = {}

        async def fake_dispatch(message, thread_id=None, org_id=None):
            captured["org"] = get_current_org_id()
            return {
                "response": "Resposta de teste",
                "agent": "receptionist",
                "tokens_used": 10,
                "tokens_in": 8,
                "tokens_out": 2,
                "estimated_cost_brl": 0.0001,
                "thread_id": thread_id or "test-thread",
                "handoff": False,
                "messages_count": 2,
            }

        mocker.patch(
            "packages.engine.chat_router.dispatch_chat_test",
            new_callable=AsyncMock,
            side_effect=fake_dispatch,
        )

        response = client.post(
            "/api/v1/chat/test",
            json={"message": "Quanto custa corte feminino?"},
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_A},
        )

        assert response.status_code == 200
        assert captured["org"] == ORG_A
        assert response.json()["response"] == "Resposta de teste"

    def test_chat_test_rejects_spoofed_org(self, client, user_token):
        response = client.post(
            "/api/v1/chat/test",
            json={"message": "preços"},
            cookies={"session_token": user_token},
            headers={"x-organization-id": ORG_B},
        )
        assert response.status_code == 403


class TestSearchKbTenant:
    def test_search_kb_uses_tenant_context(self, mocker):
        mock_service = mocker.MagicMock()
        mock_service.search_knowledge.return_value = [
            {"content": "Corte Feminino: R$ 120 (60 min)", "similarity": 0.8}
        ]
        mocker.patch("packages.engine.tools.DataLakeService", return_value=mock_service)

        with set_tenant_context(ORG_A):
            result = search_kb.invoke({"query": "corte feminino preco"})

        mock_service.search_knowledge.assert_called_once_with(
            "corte feminino preco",
            org_id=ORG_A,
            match_threshold=0.3,
            match_count=3,
        )
        assert "R$ 120" in result

    def test_search_kb_without_tenant_passes_none(self, mocker):
        mock_service = mocker.MagicMock()
        mock_service.search_knowledge.return_value = []
        mocker.patch("packages.engine.tools.DataLakeService", return_value=mock_service)

        result = search_kb.invoke({"query": "precos"})

        mock_service.search_knowledge.assert_called_once_with(
            "precos",
            org_id=None,
            match_threshold=0.3,
            match_count=3,
        )
        assert "Nenhuma informação" in result
