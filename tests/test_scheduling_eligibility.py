"""Tests for service ↔ professional eligibility."""
from unittest.mock import MagicMock

import pytest

from packages.auth_core.exceptions import BusinessLogicError
from packages.scheduling.eligibility import (
    assert_professional_eligible,
    filter_professionals_by_name,
    list_eligible_professionals,
)

ORG = "22222222-2222-2222-2222-222222222222"
SVC_ID = "55555555-5555-5555-5555-555555555555"
PROF_A = "prof-a"
PROF_B = "prof-b"


class TestListEligibleProfessionals:
    def test_uses_mn_when_rows_exist(self, mocker):
        mock_db = MagicMock()
        mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "professional_id": PROF_B,
                    "professional": {"id": PROF_B, "name": "Ana Costa", "is_active": True},
                },
                {
                    "professional_id": PROF_A,
                    "professional": {"id": PROF_A, "name": "Maria Silva", "is_active": True},
                },
            ]
        )
        mocker.patch("packages.scheduling.eligibility.db", mock_db)

        pros = list_eligible_professionals(ORG, SVC_ID)
        assert [p["name"] for p in pros] == ["Ana Costa", "Maria Silva"]

    def test_falls_back_to_legacy_fk(self, mocker):
        mock_db = MagicMock()

        def table_side(name):
            chain = MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            chain.maybe_single.return_value = chain
            if name == "service_professionals":
                chain.execute.return_value = MagicMock(data=[])
            elif name == "professionals":
                chain.execute.return_value = MagicMock(
                    data={"id": PROF_A, "name": "Maria Silva"}
                )
            return chain

        mock_db.client.table.side_effect = table_side
        mocker.patch("packages.scheduling.eligibility.db", mock_db)

        pros = list_eligible_professionals(ORG, SVC_ID, legacy_professional_id=PROF_A)
        assert pros == [{"id": PROF_A, "name": "Maria Silva"}]

    def test_falls_back_to_all_active(self, mocker):
        mock_db = MagicMock()

        def table_side(name):
            chain = MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            if name == "service_professionals":
                chain.execute.return_value = MagicMock(data=[])
            elif name == "professionals":
                chain.execute.return_value = MagicMock(
                    data=[{"id": PROF_A, "name": "Maria Silva"}]
                )
            return chain

        mock_db.client.table.side_effect = table_side
        mocker.patch("packages.scheduling.eligibility.db", mock_db)

        pros = list_eligible_professionals(ORG, SVC_ID)
        assert pros[0]["id"] == PROF_A


class TestFilterProfessionalsByName:
    def test_filters_case_insensitive(self):
        pros = [{"id": "1", "name": "Maria Silva"}, {"id": "2", "name": "Ana Costa"}]
        filtered = filter_professionals_by_name(pros, "maria")
        assert len(filtered) == 1
        assert filtered[0]["name"] == "Maria Silva"


class TestFindServiceByName:
    def test_synonym_mechas_maps_to_coloracao(self, mocker):
        catalog = [
            {
                "id": SVC_ID,
                "name": "Coloração Completa",
                "duration_minutes": 120,
                "price": 250,
                "professional_id": PROF_A,
            }
        ]
        mocker.patch("packages.scheduling.guardrails.list_catalog_services", return_value=catalog)

        from packages.scheduling.eligibility import find_service_by_name

        match = find_service_by_name(ORG, "mechas")
        assert match is not None
        assert match["name"] == "Coloração Completa"


class TestAssertProfessionalEligible:
    def test_raises_when_not_in_mn(self, mocker):
        mock_db = MagicMock()
        mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"professional_id": PROF_A}]
        )
        mocker.patch("packages.scheduling.eligibility.db", mock_db)

        with pytest.raises(BusinessLogicError, match="elegível"):
            assert_professional_eligible(ORG, SVC_ID, PROF_B)

    def test_passes_when_no_mn_rows(self, mocker):
        mock_db = MagicMock()
        mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        mocker.patch("packages.scheduling.eligibility.db", mock_db)

        assert_professional_eligible(ORG, SVC_ID, PROF_B)
