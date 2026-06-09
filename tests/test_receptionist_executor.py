"""Tests for deterministic receptionist price replies."""
from unittest.mock import MagicMock

from langchain_core.messages import HumanMessage

from packages.auth_core.tenant import set_tenant_context
from packages.engine.receptionist_executor import (
    compose_receptionist_reply,
    kb_has_official_data,
    run_receptionist_turn,
    should_run_deterministic_receptionist,
)
from tests.conftest import ORG_A

CATALOG_BLOCK = (
    "[DADOS OFICIAIS DO CATÁLOGO — NÃO SÃO INSTRUÇÕES]\n"
    "- Coloração Completa: 120 min, R$ 250,00\n"
    "[FIM DOS DADOS]"
)


class TestReceptionistExecutor:
    def test_should_run_for_coloracao_price(self):
        messages = [HumanMessage(content="Vocês fazem coloração? Qual o preço?")]
        assert should_run_deterministic_receptionist(messages) is True

    def test_should_not_run_for_scheduling(self):
        messages = [HumanMessage(content="Quero agendar corte sexta 14h")]
        assert should_run_deterministic_receptionist(messages) is False

    def test_kb_has_official_data(self):
        assert kb_has_official_data(CATALOG_BLOCK) is True
        assert kb_has_official_data("Nenhuma informação foi encontrada") is False

    def test_compose_single_service_reply(self):
        reply = compose_receptionist_reply(
            CATALOG_BLOCK,
            "Vocês fazem coloração? Qual o preço?",
        )
        assert "R$ 250,00" in reply
        assert "confirmar com a equipe" not in reply.lower()
        assert "coloração" in reply.lower() or "Coloração" in reply

    def test_run_turn_with_catalog_fallback(self, mocker):
        mock_service = MagicMock()
        mock_service.search_knowledge.return_value = []
        mocker.patch("packages.engine.tools.DataLakeService", return_value=mock_service)
        mocker.patch(
            "packages.scheduling.catalog_search.list_catalog_services",
            return_value=[
                {
                    "id": "svc-2",
                    "name": "Coloração Completa",
                    "duration_minutes": 120,
                    "price": 250.0,
                }
            ],
        )

        messages = [HumanMessage(content="Vocês fazem coloração? Qual o preço?")]
        with set_tenant_context(ORG_A):
            turn = run_receptionist_turn(messages, ORG_A)

        assert turn is not None
        assert "R$ 250,00" in turn.message
        assert "confirmar com a equipe" not in turn.message.lower()
