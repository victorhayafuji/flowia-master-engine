"""Cenários de agendamento — teste rápido sem abrir o Chat Test.

Modos (do mais rápido ao mais fiel):

  python scripts/test_scheduling_conversation.py              # executor mockado (~1s)
  python scripts/test_scheduling_conversation.py --intent     # só parsing (~0.1s)
  python scripts/test_scheduling_conversation.py --live       # Supabase real (slots)
  python scripts/test_scheduling_conversation.py --engine     # LangGraph + OpenAI
  python scripts/test_scheduling_conversation.py --http       # API em localhost:8000

  python scripts/test_scheduling_conversation.py --list       # listar cenários
  python scripts/test_scheduling_conversation.py -s pedro_11h # um cenário
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from dataclasses import dataclass, field
from typing import Literal
from unittest.mock import AsyncMock, patch

os.environ.setdefault("CHECKPOINTER_BACKEND", "memory")
os.environ.setdefault("SCHEDULER_ENABLED", "false")

ORG_ID = "22222222-2222-2222-2222-222222222222"
MOCK_SLOTS = (
    "Horários para 'Corte Masculino' em 2026-06-10:\n"
    "- Maria: 08:00, 09:00, 10:00, 14:00, 15:00, 16:00"
)
MOCK_CATALOG = [
    {"id": "svc-1", "name": "Corte Masculino", "duration_minutes": 45, "price": 80},
    {"id": "svc-2", "name": "Coloração", "duration_minutes": 120, "price": 250},
]


@dataclass
class Turn:
    role: Literal["human", "ai"]
    content: str


@dataclass
class Scenario:
    id: str
    description: str
    turns: list[Turn]
    contains: list[str] = field(default_factory=list)
    not_contains: list[str] = field(default_factory=list)
    intent_fields: dict[str, str | None] | None = None
    destructive: bool = False
    modes: tuple[str, ...] = ("intent", "executor", "live", "engine", "http")


SCENARIOS: list[Scenario] = [
    Scenario(
        id="intent_full",
        description="Mensagem completa extrai data, hora, nome e telefone",
        turns=[
            Turn(
                "human",
                "Quero agendar corte masculino dia 10 de junho as 13:00, Pedro, 11987654353",
            ),
        ],
        intent_fields={
            "date_iso": "2026-06-10",
            "time_hhmm": "13:00",
            "patient_name": "Pedro",
            "patient_phone": "11987654353",
        },
        modes=("intent",),
    ),
    Scenario(
        id="pedro_11h",
        description="11h indisponivel -> lista slots (nao 'dia lotado')",
        turns=[
            Turn(
                "human",
                "Quero agendar corte masculino dia 10 de junho as 11:00, Pedro, 11987654353",
            ),
        ],
        contains=["14:00"],
        not_contains=["dia inteiro", "entrar em contato", "atendente humano"],
    ),
    Scenario(
        id="sem_hora",
        description="So data + servico -> pede horario com slots",
        turns=[Turn("human", "Quero corte masculino dia 10 de junho")],
        contains=["Qual horário", "14:00"],
    ),
    Scenario(
        id="followup_outro",
        description="Follow-up 'tem outro horário?' após recusa",
        turns=[
            Turn(
                "human",
                "Quero corte masculino dia 10 de junho as 11:00, Pedro, 11987654353",
            ),
            Turn(
                "ai",
                "Não há horários disponíveis para 'Corte Masculino' no dia 10 de junho.",
            ),
            Turn("human", "Sim, tem algum outro horario?"),
        ],
        contains=["14:00"],
        not_contains=["qual data", "qual dia"],
    ),
    Scenario(
        id="reaffirm_date",
        description="Cliente repete so a data -> mantem contexto e lista slots",
        turns=[
            Turn("human", "Quero corte masculino"),
            Turn("ai", "Para qual data você gostaria de agendar o Corte Masculino?"),
            Turn("human", "10 de junho"),
        ],
        contains=["10", "Qual horário"],
    ),
    Scenario(
        id="pedro_13h_book",
        description="13h confirma agendamento (grava no banco)",
        turns=[
            Turn(
                "human",
                "Quero agendar corte masculino dia 10 de junho as 13:00, Pedro, 11987654353",
            ),
        ],
        contains=["SUCESSO", "13:00"],
        destructive=True,
        modes=("live", "engine"),
    ),
]


async def _mock_execute_booking(intent, _config):
    if intent.time_hhmm == "11:00":
        return (
            f"O horário 11:00 (Brasília) não está livre para '{intent.service_query}' "
            f"em {intent.date_iso}.\n\n{MOCK_SLOTS}\n\nQual horário você prefere?"
        )
    return (
        f"SUCESSO! Agendamento confirmado para {intent.patient_name}: "
        f"'{intent.service_query}' em 10/06/2026 {intent.time_hhmm}."
    )


def _messages_from_turns(turns: list[Turn]):
    from langchain_core.messages import AIMessage, HumanMessage

    out = []
    for t in turns:
        if t.role == "human":
            out.append(HumanMessage(content=t.content))
        else:
            out.append(AIMessage(content=t.content))
    return out


def _check_response(text: str, scenario: Scenario) -> list[str]:
    errors: list[str] = []
    lower = text.lower()
    for needle in scenario.contains:
        if needle.lower() not in lower:
            errors.append(f"esperado conter {needle!r}")
    for needle in scenario.not_contains:
        if needle.lower() in lower:
            errors.append(f"esperado NÃO conter {needle!r}")
    return errors


def run_intent_scenario(scenario: Scenario) -> list[str]:
    from packages.scheduling.booking_executor import collect_booking_intent

    if not scenario.intent_fields:
        return [f"{scenario.id}: sem intent_fields definidos"]

    messages = _messages_from_turns(scenario.turns)
    intent = collect_booking_intent(messages, ORG_ID)
    if intent is None:
        return [f"{scenario.id}: collect_booking_intent retornou None"]

    errors: list[str] = []
    for key, expected in scenario.intent_fields.items():
        actual = getattr(intent, key, None)
        if actual != expected:
            errors.append(f"{scenario.id}: intent.{key}={actual!r}, esperado {expected!r}")
    return errors


async def run_executor_scenario(scenario: Scenario, *, live: bool) -> tuple[str, list[str]]:
    from packages.scheduling.booking_executor import run_scheduling_turn

    config = {"configurable": {"org_id": ORG_ID}}
    messages = _messages_from_turns(scenario.turns)

    if live:
        with patch(
            "packages.scheduling.booking_executor.list_catalog_services",
            return_value=MOCK_CATALOG,
        ):
            result = await run_scheduling_turn(messages, config)
    else:
        with (
            patch(
                "packages.scheduling.booking_executor.list_catalog_services",
                return_value=MOCK_CATALOG,
            ),
            patch(
                "packages.scheduling.booking_executor.fetch_availability_summary",
                new_callable=AsyncMock,
                return_value=MOCK_SLOTS,
            ),
            patch(
                "packages.scheduling.booking_executor.execute_booking",
                new_callable=AsyncMock,
                side_effect=_mock_execute_booking,
            ),
        ):
            result = await run_scheduling_turn(messages, config)

    if result is None:
        return "", [f"{scenario.id}: run_scheduling_turn retornou None (cairia no LLM)"]

    return result.message, _check_response(result.message, scenario)


async def run_engine_scenario(scenario: Scenario) -> tuple[str, list[str]]:
    from packages.auth_core.tenant import set_tenant_context
    from packages.engine.prompts.registry import register_salon_prompts
    from packages.engine.service import dispatch_chat_test

    register_salon_prompts()
    thread_id = str(uuid.uuid4())
    last_response = ""

    with set_tenant_context(ORG_ID):
        for turn in scenario.turns:
            if turn.role != "human":
                continue
            data = await dispatch_chat_test(turn.content, thread_id=thread_id, org_id=ORG_ID)
            last_response = (data.get("response") or "").strip()
            agent = data.get("agent", "?")
            if agent != "scheduling":
                return last_response, [f"{scenario.id}: agent={agent} (esperado scheduling)"]
            if data.get("handoff"):
                return last_response, [f"{scenario.id}: handoff indevido"]

    return last_response, _check_response(last_response, scenario)


def run_http_scenario(scenario: Scenario, client, headers: dict) -> tuple[str, list[str]]:
    thread_id = str(uuid.uuid4())
    last_response = ""

    for turn in scenario.turns:
        if turn.role != "human":
            continue
        resp = client.post(
            f"{BASE_URL}/chat/test",
            json={"message": turn.content, "thread_id": thread_id},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        last_response = (data.get("response") or "").strip()
        if data.get("agent") != "scheduling":
            return last_response, [f"{scenario.id}: agent={data.get('agent')}"]
        if data.get("handoff"):
            return last_response, [f"{scenario.id}: handoff=True"]

    return last_response, _check_response(last_response, scenario)


BASE_URL = "http://127.0.0.1:8000/api/v1"


def _filter_scenarios(
    mode: str,
    only: str | None,
    allow_destructive: bool,
) -> list[Scenario]:
    out: list[Scenario] = []
    for s in SCENARIOS:
        if only and s.id != only:
            continue
        if mode not in s.modes:
            continue
        if mode == "intent" and not s.intent_fields:
            continue
        if s.destructive and not allow_destructive and mode in ("live", "engine", "http"):
            continue
        out.append(s)
    return out


def _print_result(scenario: Scenario, response: str, errors: list[str], verbose: bool) -> bool:
    ok = not errors
    tag = "OK" if ok else "FAIL"
    print(f"[{tag}] {scenario.id} - {scenario.description}")
    if verbose or not ok:
        preview = response.strip().replace("\n", " ")[:280]
        if preview:
            print(f"       > {preview}{'...' if len(response) > 280 else ''}")
    for err in errors:
        print(f"       ! {err}")
    return ok


async def main_async(args: argparse.Namespace) -> int:
    if args.list:
        for s in SCENARIOS:
            flags = []
            if s.destructive:
                flags.append("destructive")
            modes = ", ".join(s.modes)
            extra = f" [{', '.join(flags)}]" if flags else ""
            print(f"  {s.id:20} ({modes}){extra}  {s.description}")
        return 0

    mode = "intent" if args.intent else "live" if args.live else "engine" if args.engine else "http" if args.http else "executor"
    scenarios = _filter_scenarios(mode, args.scenario, args.allow_write)
    if not scenarios:
        print(f"Nenhum cenário para modo={mode}" + (f" id={args.scenario}" if args.scenario else ""))
        return 1

    print(f"Modo: {mode} | cenários: {len(scenarios)} | org={ORG_ID}\n")

    passed = 0
    failed = 0

    if mode == "intent":
        with patch(
            "packages.scheduling.booking_executor.list_catalog_services",
            return_value=MOCK_CATALOG,
        ):
            for scenario in scenarios:
                errors = run_intent_scenario(scenario)
                if _print_result(scenario, "", errors, args.verbose):
                    passed += 1
                else:
                    failed += 1

    elif mode == "executor":
        for scenario in scenarios:
            response, errors = await run_executor_scenario(scenario, live=False)
            if _print_result(scenario, response, errors, args.verbose):
                passed += 1
            else:
                failed += 1

    elif mode == "live":
        for scenario in scenarios:
            response, errors = await run_executor_scenario(scenario, live=True)
            if _print_result(scenario, response, errors, args.verbose):
                passed += 1
            else:
                failed += 1

    elif mode == "engine":
        for scenario in scenarios:
            response, errors = await run_engine_scenario(scenario)
            if _print_result(scenario, response, errors, args.verbose):
                passed += 1
            else:
                failed += 1

    else:  # http
        import httpx

        email = os.environ.get("DEV_SALON_EMAIL", "dono@beauty-express.com")
        password = os.environ.get("DEV_SALON_PASSWORD", "senha123")
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            login = client.post(f"{BASE_URL}/auth/login", json={"username": email, "password": password})
            if login.status_code != 200:
                print(f"Login falhou ({login.status_code}). Suba a API ou ajuste credenciais.")
                return 1
            headers = {"x-organization-id": ORG_ID}
            for scenario in scenarios:
                response, errors = run_http_scenario(scenario, client, headers)
                if _print_result(scenario, response, errors, args.verbose):
                    passed += 1
                else:
                    failed += 1

    print(f"\n{passed} ok, {failed} falha(s)")
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Cenários de agendamento (sem Chat Test UI)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--intent", action="store_true", help="Só collect_booking_intent (~0.1s)")
    g.add_argument("--live", action="store_true", help="Executor + Supabase real (slots)")
    g.add_argument("--engine", action="store_true", help="LangGraph + OpenAI (lento)")
    g.add_argument("--http", action="store_true", help="POST /chat/test (API rodando)")
    p.add_argument("-s", "--scenario", metavar="ID", help="Rodar um cenário (ex: pedro_11h)")
    p.add_argument("--list", action="store_true", help="Listar cenários")
    p.add_argument("-v", "--verbose", action="store_true", help="Mostrar resposta mesmo quando OK")
    p.add_argument(
        "--allow-write",
        action="store_true",
        help="Inclui cenários destructive (grava agendamento)",
    )
    return p


def main() -> int:
    args = build_parser().parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
