"""Cross-tenant isolation for the AI agent — no data leaks between organizations.

FlowIA is multi-tenant: the agent serving organization Y must never surface
organization X's catalog/KB data. These tests prove the agent's answer is
bounded to the org-scoped sources it was given, and that the RAG query layer
only filters by a concrete org.

Behavioral cases run through the real engine via the ``agent_flow`` harness
(LangGraph + in-memory checkpointer). The harness re-installs global catalog/RAG
mocks on every ``agent_flow(...)`` call, so each tenant is exercised
sequentially (configure A, assert A; then configure B, assert B) — never
interleaved. Assertions target the deterministic receptionist path (tokens==0),
since the harness fakes the LLM.

    py -3.12 -m pytest tests/test_agent_tenant_isolation.py -v
"""
from __future__ import annotations

import pytest

from tests.conftest import ORG_A, ORG_B

# Distinct catalogs per org. Names contain recognized service tokens (hidrat /
# color) so a query for the *other* org's service hits the genuine "not found"
# path instead of being treated as a generic catalog dump. The exclusive name +
# price of each org is the "marker" we assert is never echoed by the other org.
ORG_A_CATALOG = [
    {
        "id": "svc-a-hidra",
        "name": "Hidratação Aurora",
        "duration_minutes": 60,
        "price": 199.0,
        "professional_id": "pro-a",
    },
    {
        "id": "svc-a-escova",
        "name": "Escova Modelada",
        "duration_minutes": 45,
        "price": 89.0,
        "professional_id": "pro-a",
    },
]
ORG_B_CATALOG = [
    {
        "id": "svc-b-color",
        "name": "Coloração Platinum",
        "duration_minutes": 120,
        "price": 299.0,
        "professional_id": "pro-b",
    },
    {
        "id": "svc-b-corte",
        "name": "Corte Premium",
        "duration_minutes": 50,
        "price": 159.0,
        "professional_id": "pro-b",
    },
]

# Substrings that uniquely identify each org's exclusive offering.
ORG_A_MARKERS = ("Hidratação Aurora", "199")
ORG_B_MARKERS = ("Coloração Platinum", "299")


def _assert_absent(message: str, markers: tuple[str, ...]) -> None:
    lower = message.lower()
    for marker in markers:
        assert marker.lower() not in lower, f"leaked cross-tenant marker {marker!r}: {message!r}"


@pytest.mark.agent_flow
class TestAgentCrossTenantIsolation:
    # Each probe uses a fresh flow (new thread): a single price turn routes to the
    # deterministic receptionist, avoiding multi-turn triage stickiness.

    @pytest.mark.asyncio
    async def test_org_a_agent_serves_own_catalog(self, agent_flow):
        flow = agent_flow(org_id=ORG_A, salon_name="Salão Aurora", catalog=list(ORG_A_CATALOG))
        own = await flow.say("Quanto custa a Hidratação Aurora?")

        assert own.agent == "receptionist"
        assert own.receptionist_path == "deterministic"
        assert own.tokens_used == 0
        assert "199" in own.message

    @pytest.mark.asyncio
    async def test_org_a_agent_does_not_leak_org_b_service(self, agent_flow):
        # ORG_A's agent asked about a service that exists ONLY in ORG_B's catalog.
        # Hard guarantee: ORG_B's price/name never appears — the agent has no
        # access to ORG_B's tenant-scoped catalog, so it cannot surface it.
        flow = agent_flow(org_id=ORG_A, salon_name="Salão Aurora", catalog=list(ORG_A_CATALOG))
        other = await flow.say("Quanto custa a Coloração Platinum?")

        assert other.agent == "receptionist"
        assert other.handoff is False
        _assert_absent(other.message, ORG_B_MARKERS)

    @pytest.mark.asyncio
    async def test_org_b_agent_serves_own_catalog(self, agent_flow):
        flow = agent_flow(org_id=ORG_B, salon_name="Studio Bela", catalog=list(ORG_B_CATALOG))
        own = await flow.say("Quanto custa a Barboterapia VIP?")

        assert own.agent == "receptionist"
        assert own.receptionist_path == "deterministic"
        assert own.tokens_used == 0
        assert "299" in own.message

    @pytest.mark.asyncio
    async def test_org_b_agent_does_not_leak_org_a_service(self, agent_flow):
        # ORG_B's agent asked about a service that exists ONLY in ORG_A's catalog.
        flow = agent_flow(org_id=ORG_B, salon_name="Studio Bela", catalog=list(ORG_B_CATALOG))
        other = await flow.say("Quanto custa a Hidratação Aurora?")

        assert other.agent == "receptionist"
        assert other.handoff is False
        _assert_absent(other.message, ORG_A_MARKERS)

    @pytest.mark.asyncio
    async def test_agent_refuses_unknown_service_honestly(self, agent_flow):
        # The literal "não sei te responder" behavior: a service absent from the
        # org's catalog yields an honest refusal, not an invented answer.
        flow = agent_flow(org_id=ORG_A, salon_name="Salão Aurora", catalog=list(ORG_A_CATALOG))
        turn = await flow.say("Quanto custa podologia?")

        assert turn.agent == "receptionist"
        lower = turn.message.lower()
        assert "confirmar com a equipe" not in lower
        assert (
            "nenhuma informação" in lower
            or "não encontrei" in lower
            or "catálogo" in lower
        ), f"expected honest refusal, got: {turn.message!r}"


class TestRagOrgFilter:
    """Data-layer proof: the vector search RPC only filters by a concrete org."""

    def _run_search(self, mocker, org_id):
        from unittest.mock import MagicMock

        from packages.lakehouse.search import SearchLayer

        mocker.patch("packages.lakehouse.search.embed_text", return_value=[0.1, 0.2, 0.3])
        mocker.patch(
            "packages.lakehouse.search.normalize_embedding",
            side_effect=lambda v: v,
        )

        service = MagicMock()
        service.supabase.rpc.return_value.execute.return_value.data = []

        layer = SearchLayer(service)
        layer.search_knowledge("quanto custa", org_id=org_id, match_count=3)

        rpc_call = service.supabase.rpc.call_args
        assert rpc_call.args[0] == "match_documents"
        return rpc_call.args[1]

    def test_specific_org_sends_filter(self, mocker):
        params = self._run_search(mocker, ORG_A)
        assert params.get("filter_org_id") == ORG_A

    def test_all_org_omits_filter(self, mocker):
        params = self._run_search(mocker, "ALL")
        assert "filter_org_id" not in params

    def test_none_org_omits_filter(self, mocker):
        params = self._run_search(mocker, None)
        assert "filter_org_id" not in params
