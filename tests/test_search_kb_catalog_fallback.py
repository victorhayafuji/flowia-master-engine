"""Tests for catalog fallback in search_kb."""


from packages.auth_core.tenant import set_tenant_context
from packages.engine.tools import search_kb
from packages.scheduling.catalog_search import (
    find_catalog_matches,
    format_catalog_official_block,
)
from tests.conftest import ORG_A

CATALOG = [
    {
        "id": "svc-1",
        "name": "Corte Feminino",
        "duration_minutes": 60,
        "price": 120.0,
        "professional_id": "pro-1",
    },
    {
        "id": "svc-2",
        "name": "Coloração Completa",
        "duration_minutes": 120,
        "price": 250.0,
        "professional_id": "pro-2",
    },
]


class TestCatalogSearch:
    def test_find_coloracao_match(self, mocker):
        mocker.patch(
            "packages.scheduling.catalog_search.list_catalog_services",
            return_value=CATALOG,
        )
        matches = find_catalog_matches(ORG_A, "Vocês fazem coloração? Qual o preço?")
        assert len(matches) == 1
        assert matches[0]["name"] == "Coloração Completa"

    def test_generic_price_lists_catalog(self, mocker):
        mocker.patch(
            "packages.scheduling.catalog_search.list_catalog_services",
            return_value=CATALOG,
        )
        matches = find_catalog_matches(ORG_A, "Quais são os preços?")
        assert len(matches) == 2

    def test_format_block_contains_price(self):
        block = format_catalog_official_block([CATALOG[1]])
        assert "R$ 250,00" in block
        assert "Coloração Completa" in block


class TestSearchKbCatalogFallback:
    def test_rag_empty_uses_catalog(self, mocker):
        mock_service = mocker.MagicMock()
        mock_service.search_knowledge.return_value = []
        mocker.patch("packages.engine.tools.DataLakeService", return_value=mock_service)
        mocker.patch(
            "packages.scheduling.catalog_search.list_catalog_services",
            return_value=CATALOG,
        )

        with set_tenant_context(ORG_A):
            result = search_kb.invoke({"query": "Vocês fazem coloração? Qual o preço?"})

        assert "R$ 250,00" in result
        assert "Coloração Completa" in result
        assert "CATÁLOGO" in result or "CATÁLOGO" in result.upper()

    def test_rag_hit_skips_catalog(self, mocker):
        mock_service = mocker.MagicMock()
        mock_service.search_knowledge.return_value = [
            {"content": "Coloração especial R$ 999", "similarity": 0.9}
        ]
        mocker.patch("packages.engine.tools.DataLakeService", return_value=mock_service)
        catalog_mock = mocker.patch("packages.scheduling.catalog_search.list_catalog_services")

        with set_tenant_context(ORG_A):
            result = search_kb.invoke({"query": "coloração preço"})

        assert "R$ 999" in result
        catalog_mock.assert_not_called()

    def test_both_empty_returns_honest_message(self, mocker):
        mock_service = mocker.MagicMock()
        mock_service.search_knowledge.return_value = []
        mocker.patch("packages.engine.tools.DataLakeService", return_value=mock_service)
        mocker.patch("packages.scheduling.catalog_search.list_catalog_services", return_value=[])

        with set_tenant_context(ORG_A):
            result = search_kb.invoke({"query": "podologia"})

        assert "Nenhuma informação foi encontrada" in result
        assert "equipe" not in result.lower()
