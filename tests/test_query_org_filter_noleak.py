"""Data-layer proof that no-leak queries actually carry the org filter.

Lesson from PR #45 ([[supabase-mock-column-validation]]): a mock returning an
empty list proves nothing — the query could be missing its
``.eq("organization_id", ...)`` and a real PostgREST call would leak. Here we
spy on the fluent chain and assert the org filter is genuinely applied, with the
exact org value from the request — not just that the result was empty.

Covers:
  * RAG vector search → ``filter_org_id`` reaches the RPC for a concrete org,
    and is OMITTED for ALL/None (super_admin cross-tenant).
  * Compliance export/erase → the patient lookup is gated by
    ``.eq("organization_id", org)``, so a foreign patient is "not found".
"""
from __future__ import annotations

import pytest

from tests.conftest import ORG_A, ORG_B


class _Chain:
    """Records every .eq(col, val) applied along the fluent chain."""

    def __init__(self, recorder, data):
        self._rec = recorder
        self._data = data

    def select(self, *a, **k):
        return self

    def eq(self, col, val):
        self._rec.append((col, val))
        return self

    def limit(self, *a, **k):
        return self

    def maybe_single(self, *a, **k):
        return self

    def execute(self):
        return type("R", (), {"data": self._data, "count": len(self._data)})()


class TestRagFilterOrgIsApplied:
    """The RAG RPC carries filter_org_id for a concrete org only."""

    def _run_search(self, mocker, org_id):
        from unittest.mock import MagicMock

        from packages.lakehouse.search import SearchLayer

        mocker.patch("packages.lakehouse.search.embed_text", return_value=[0.1, 0.2, 0.3])
        mocker.patch("packages.lakehouse.search.normalize_embedding", side_effect=lambda v: v)

        service = MagicMock()
        service.supabase.rpc.return_value.execute.return_value.data = []
        layer = SearchLayer(service)
        layer.search_knowledge("quanto custa", org_id=org_id, match_count=3)

        rpc_call = service.supabase.rpc.call_args
        assert rpc_call.args[0] == "match_documents"
        return rpc_call.args[1]

    def test_org_a_search_sends_its_own_filter(self, mocker):
        params = self._run_search(mocker, ORG_A)
        assert params.get("filter_org_id") == ORG_A

    def test_org_b_search_sends_its_own_filter(self, mocker):
        # Different org → different filter value. Proves the value is wired from
        # the caller, not a hardcoded constant that would pass for any org.
        params = self._run_search(mocker, ORG_B)
        assert params.get("filter_org_id") == ORG_B

    def test_all_org_omits_filter(self, mocker):
        params = self._run_search(mocker, "ALL")
        assert "filter_org_id" not in params


class TestComplianceExportOrgScoped:
    """DSAR export gates the patient lookup by organization_id."""

    def test_export_patient_query_filters_by_org(self, mocker):
        from packages.compliance import export as export_mod

        recorded: list[tuple[str, str]] = []

        # Patient lookup returns the patient ONLY because we let it; the dente is
        # that organization_id == ORG_A was applied to the lookup.
        def _table(name):
            if name == "patients":
                return _Chain(recorded, [{"id": "pat-a", "organization_id": ORG_A}])
            return _Chain([], [])

        mocker.patch.object(export_mod.db, "client", mocker.MagicMock(table=_table))

        export_mod.export_patient_data(ORG_A, "pat-a")

        assert ("organization_id", ORG_A) in recorded, recorded

    def test_export_foreign_patient_not_found(self, mocker):
        # Patient belongs to ORG_B; export under ORG_A applies
        # .eq(organization_id, ORG_A) so the row is filtered out → ValueError
        # (router maps to 404). No ORG_B data is ever returned.
        from packages.compliance import export as export_mod

        recorded: list[tuple[str, str]] = []

        def _table(name):
            if name == "patients":
                # Empty: the org filter excluded the foreign-tenant patient.
                return _Chain(recorded, [])
            return _Chain([], [])

        mocker.patch.object(export_mod.db, "client", mocker.MagicMock(table=_table))

        with pytest.raises(ValueError):
            export_mod.export_patient_data(ORG_A, "pat-belongs-to-b")

        assert ("organization_id", ORG_A) in recorded, recorded


class TestComplianceEraseOrgScoped:
    """DSAR erase gates the patient lookup by organization_id too."""

    def test_erase_foreign_patient_not_found(self, mocker):
        from packages.compliance import erasure as erasure_mod

        recorded: list[tuple[str, str]] = []

        def _table(name):
            if name == "patients":
                return _Chain(recorded, [])  # foreign patient excluded by org filter
            return _Chain([], [])

        mocker.patch.object(erasure_mod.db, "client", mocker.MagicMock(table=_table))

        with pytest.raises(ValueError):
            erasure_mod.erase_patient_data(ORG_A, "pat-belongs-to-b")

        assert ("organization_id", ORG_A) in recorded, recorded
