"""Simula conversas multi-turno pelo mesmo caminho do Chat Test (master_engine).

Uso nos testes:

    async def test_exemplo(agent_flow):
        flow = agent_flow()
        t1 = await flow.say("Vocês fazem coloração? Qual o preço?")
        t2 = await flow.say("Sim, tem horário para 12 de junho?")
        assert "R$ 250" in t1.message

Ou via CLI:

    py -3.12 -m pytest tests/test_agent_flow.py -v
    py -3.12 -m pytest tests/test_agent_flow.py -k coloracao -v
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from langchain_core.messages import AIMessage

from packages.auth_core.config import settings
from packages.auth_core.tenant import set_tenant_context
from packages.compliance.consent import ConsentAction
from packages.engine.checkpointer import init_checkpointer, shutdown_checkpointer
from packages.engine.engine import RouteOutput
from packages.engine.service import dispatch_chat_test
from tests.conftest import ORG_A

DEFAULT_CATALOG = [
    {
        "id": "svc-color",
        "name": "Coloração Completa",
        "duration_minutes": 120,
        "price": 250.0,
        "professional_id": "pro-ana",
    },
    {
        "id": "svc-corte-m",
        "name": "Corte Masculino",
        "duration_minutes": 45,
        "price": 80.0,
        "professional_id": "pro-maria",
    },
    {
        "id": "svc-corte-f",
        "name": "Corte Feminino",
        "duration_minutes": 60,
        "price": 120.0,
        "professional_id": "pro-maria",
    },
    {
        "id": "svc-manicure",
        "name": "Manicure",
        "duration_minutes": 40,
        "price": 45.0,
        "professional_id": "pro-maria",
    },
]

DEFAULT_AVAILABILITY = (
    "Horários para 'Coloração Completa' em 2026-06-12 (Brasília / America/Sao_Paulo):\n"
    "- Ana Costa: 14:00, 15:00\n\n"
    "Qual horário você prefere? (horário de Brasília)"
)

NO_AVAILABILITY = (
    "Não há horários disponíveis para 'Coloração Completa' no dia 2026-06-12."
)


@dataclass
class AgentTurn:
    """Um turno do cliente → resposta do motor (como no Chat Test)."""

    user_message: str
    message: str
    agent: str
    tokens_used: int
    tokens_in: int
    tokens_out: int
    handoff: bool
    scheduling_path: str | None = None
    receptionist_path: str | None = None
    triage_source: str | None = None
    thread_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return self.message


@dataclass
class AgentFlowConfig:
    org_id: str = ORG_A
    salon_name: str = "Beauty Express"
    reference_date: date = date(2026, 6, 7)
    catalog: list[dict[str, Any]] = field(default_factory=lambda: list(DEFAULT_CATALOG))
    availability_response: str = DEFAULT_AVAILABILITY
    skip_lgpd: bool = True
    consent_mode: str = "proceed"  # proceed | lgpd_two_step
    mock_booking_success: bool = False
    booking_success_message: str = (
        "SUCESSO! Agendamento confirmado para Joao Silva: "
        "'Corte Masculino' em 10/06/2026 11:00."
    )
    rag_results: list[dict[str, Any]] | None = None
    rag_poison: str | None = None


class AgentFlowSimulator:
    """Injeta mensagens no fluxo real do agente (LangGraph + checkpointer in-memory)."""

    def __init__(self, config: AgentFlowConfig | None = None) -> None:
        self.config = config or AgentFlowConfig()
        self.thread_id = str(uuid.uuid4())
        self.turns: list[AgentTurn] = []

    async def say(self, message: str) -> AgentTurn:
        with set_tenant_context(self.config.org_id):
            raw = await dispatch_chat_test(
                message,
                self.thread_id,
                org_id=self.config.org_id,
            )
        turn = AgentTurn(
            user_message=message,
            message=raw.get("response") or "",
            agent=raw.get("agent") or "unknown",
            tokens_used=int(raw.get("tokens_used") or 0),
            tokens_in=int(raw.get("tokens_in") or 0),
            tokens_out=int(raw.get("tokens_out") or 0),
            handoff=bool(raw.get("handoff")),
            scheduling_path=raw.get("scheduling_path"),
            receptionist_path=raw.get("receptionist_path"),
            triage_source=raw.get("triage_source"),
            thread_id=self.thread_id,
            raw=raw,
        )
        self.turns.append(turn)
        return turn

    async def say_many(self, *messages: str) -> list[AgentTurn]:
        return [await self.say(msg) for msg in messages]


def _fixed_date_cls(reference: date) -> type[date]:
    class _FixedToday(date):
        @classmethod
        def today(cls) -> date:
            return reference

    return _FixedToday


def install_agent_flow_mocks(mocker, config: AgentFlowConfig) -> None:
    """Mocks externos (DB, LLM, RAG) — o grafo LangGraph roda de verdade."""
    shutdown_checkpointer()
    init_checkpointer()

    from packages.engine.engine import _build_agent_llm
    from packages.engine.prompts.registry import register_salon_prompts

    register_salon_prompts()
    _build_agent_llm.cache_clear()

    mocker.patch(
        "packages.engine.service.evaluate_consent_gate",
        side_effect=_consent_side_effect(config),
    )
    mocker.patch("packages.engine.service.save_conversation_metric")
    mocker.patch("packages.engine.context.get_salon_name", return_value=config.salon_name)

    mock_service = MagicMock()
    if config.rag_poison is not None:
        rag_payload = [{"content": config.rag_poison}]
    elif config.rag_results is not None:
        rag_payload = config.rag_results
    else:
        rag_payload = []
    mock_service.search_knowledge.return_value = rag_payload
    mocker.patch("packages.engine.tools.DataLakeService", return_value=mock_service)

    catalog = config.catalog
    mocker.patch("packages.scheduling.eligibility.list_catalog_services", return_value=catalog)
    mocker.patch("packages.scheduling.booking_executor.list_catalog_services", return_value=catalog)
    mocker.patch("packages.scheduling.catalog_search.list_catalog_services", return_value=catalog)

    async def _availability_side_effect(service_query: str, date_iso: str, config_arg):
        del config_arg
        service_lower = service_query.lower()
        if "corte masculino" in service_lower:
            return (
                f"Horários para 'Corte Masculino' em {date_iso} (Brasília / America/Sao_Paulo):\n"
                "- Maria Silva: 13:00, 14:00\n\n"
                "Qual horário você prefere? (horário de Brasília)"
            )
        if "corte feminino" in service_lower:
            return (
                f"Horários para 'Corte Feminino' em {date_iso} (Brasília / America/Sao_Paulo):\n"
                "- Maria Silva: 10:00, 11:00\n\n"
                "Qual horário você prefere? (horário de Brasília)"
            )
        if "manicure" in service_lower:
            return (
                f"Horários para 'Manicure' em {date_iso} (Brasília / America/Sao_Paulo):\n"
                "- Maria Silva: 09:00, 09:30\n\n"
                "Qual horário você prefere? (horário de Brasília)"
            )
        if "coloração" in service_lower or "coloracao" in service_lower:
            return config.availability_response.replace("2026-06-12", date_iso)
        return config.availability_response

    mocker.patch(
        "packages.scheduling.booking_executor.fetch_availability_summary",
        new_callable=AsyncMock,
        side_effect=_availability_side_effect,
    )

    fixed = _fixed_date_cls(config.reference_date)
    for target in (
        "packages.scheduling.booking_executor.date",
        "packages.scheduling.guardrails.date",
        "packages.engine.response_composer.date",
        "packages.engine.graph.nodes.date",
        "packages.engine.intent_extractor.date",
        "packages.engine.support_executor.date",
        "packages.scheduling.date_parsing.resolve.date",
        "packages.scheduling.date_parsing.normalize.date",
    ):
        mocker.patch(target, fixed)

    mocker.patch.object(settings, "SCHEDULING_DETERMINISTIC_ENABLED", True)
    mocker.patch.object(settings, "INTENT_EXTRACTOR_ENABLED", False)
    mocker.patch.object(settings, "RESPONSE_POLISH_ENABLED", False)
    mocker.patch.object(settings, "SCHEDULING_LLM_FALLBACK", "never")

    mock_llm = MagicMock()
    router = MagicMock()
    router.invoke.return_value = RouteOutput(destination="receptionist")
    mock_llm.with_structured_output.return_value = router
    mocker.patch("packages.engine.graph.nodes.llm_base", mock_llm)

    def _fake_build_agent_llm(salon_name: str, agent: str):
        chain = MagicMock()
        chain.invoke.return_value = AIMessage(
            content=f"Posso ajudar com serviços e agendamentos ({agent})."
        )
        return chain

    mocker.patch("packages.engine.graph.nodes._build_agent_llm", _fake_build_agent_llm)

    if config.mock_booking_success:
        mocker.patch(
            "packages.scheduling.booking_executor.execute_booking",
            new_callable=AsyncMock,
            return_value=config.booking_success_message,
        )


def _consent_side_effect(config: AgentFlowConfig):
    if config.consent_mode == "lgpd_two_step":
        state = {"calls": 0}

        def _gate(org_id, sender_id, channel):
            del org_id, sender_id, channel
            state["calls"] += 1
            if state["calls"] == 1:
                return (
                    ConsentAction.SEND_NOTICE,
                    "Aviso LGPD: ao continuar você concorda com o tratamento de dados.",
                    False,
                )
            return ConsentAction.PROCEED, None, True

        return _gate

    return lambda *args, **kwargs: (ConsentAction.PROCEED, None, True)
