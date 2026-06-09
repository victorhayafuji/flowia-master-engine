"""Teste de agendamento via LLM (OpenAI + tools) — caminho real do produto.

Por padrao DESLIGA o booking_executor deterministico para forcar o agente
scheduling a usar check_availability e book_time.

Uso:
  py -3 scripts/test_scheduling_llm.py              # todos os cenarios
  py -3 scripts/test_scheduling_llm.py -s junho_10   # um cenario
  py -3 scripts/test_scheduling_llm.py --list
  py -3 scripts/test_scheduling_llm.py -v            # resposta completa

Requisitos: .env com OPENAI_API_KEY + Supabase (org demo Beauty Express).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from dataclasses import dataclass, field

# Antes de importar settings/engine
os.environ.setdefault("CHECKPOINTER_BACKEND", "memory")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("SCHEDULING_DETERMINISTIC_ENABLED", "false")

ORG_ID = "22222222-2222-2222-2222-222222222222"

BAD_PHRASES = (
    "2024",
    "2025",
    "qual ano",
    "em que ano",
    "atendente humano",
    "entrar em contato",
    "solicitei um atendente",
    "transferir para",
)


@dataclass
class TurnExpect:
    user: str
    agent: str = "scheduling"
    tools_min: list[str] = field(default_factory=list)
    require_any_tool: bool = False
    contains: list[str] = field(default_factory=list)
    not_contains: list[str] = field(default_factory=list)
    allow_handoff: bool = False


@dataclass
class LlmScenario:
    id: str
    description: str
    turns: list[TurnExpect]


SCENARIOS: list[LlmScenario] = [
    LlmScenario(
        id="junho_10",
        description="Data relativa + servico -> check_availability (sem perguntar ano)",
        turns=[
            TurnExpect(
                user="Quero agendar corte masculino no dia 10 de junho",
                tools_min=["check_availability"],
                contains=["hor", "10"],
                not_contains=["2024", "2025", "qual ano"],
            ),
        ],
    ),
    LlmScenario(
        id="fluxo_3_turnos",
        description="Servico+data, depois contato, depois horario especifico",
        turns=[
            TurnExpect(
                user="Quero agendar corte masculino no dia 10 de junho",
                tools_min=["check_availability"],
            ),
            TurnExpect(
                user="Meu nome e Pedro Silva, telefone 11987654353",
            ),
            TurnExpect(
                user="Pode ser as 14:00?",
                tools_min=["book_time"],
                contains=["14", "confirmad"],
            ),
        ],
    ),
    LlmScenario(
        id="hora_11h",
        description="Horario indisponivel (pausa) -> alternativas, sem handoff",
        turns=[
            TurnExpect(
                user=(
                    "Quero corte masculino dia 10 de junho as 11:00, "
                    "Pedro Silva, 11987654353"
                ),
                tools_min=["check_availability"],
                not_contains=list(BAD_PHRASES),
            ),
        ],
    ),
    LlmScenario(
        id="mensagem_completa_17h",
        description="Uma mensagem com tudo -> confirma agendamento",
        turns=[
            TurnExpect(
                user=(
                    "Quero agendar corte masculino dia 10 de junho as 17:15, "
                    "Ana Teste LLM, telefone 11999887766"
                ),
                tools_min=[],  # LLM pode ir direto em book_time ou checar antes
                require_any_tool=True,
                contains=["17", "confirmad"],
                not_contains=list(BAD_PHRASES),
            ),
        ],
    ),
]


def _tools_since(messages: list, start: int) -> list[str]:
    from langchain_core.messages import AIMessage

    names: list[str] = []
    for msg in messages[start:]:
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            names.extend(tc["name"] for tc in msg.tool_calls)
    return names


def _last_ai_text(messages: list) -> str:
    from langchain_core.messages import AIMessage, HumanMessage

    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            break
        if isinstance(msg, AIMessage):
            content = getattr(msg, "content", "") or ""
            if isinstance(content, list):
                content = " ".join(
                    b.get("text", "") for b in content if isinstance(b, dict)
                )
            if str(content).strip() and not getattr(msg, "tool_calls", None):
                return str(content).strip()
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content = getattr(msg, "content", "") or ""
            return str(content).strip()
    return ""


async def run_turn(
    message: str,
    thread_id: str,
    msg_count_before: int,
) -> tuple[dict, list[str], str]:
    from langchain_core.messages import HumanMessage

    from packages.auth_core.tenant import set_tenant_context
    from packages.engine.checkpointer import master_engine
    from packages.engine.input_guard import format_user_message_for_agent
    from packages.engine.token_tracking import TurnTokenTracker

    token_tracker = TurnTokenTracker()
    config = {
        "configurable": {
            "thread_id": thread_id,
            "org_id": ORG_ID,
            "channel": "llm_test",
        },
        "callbacks": [token_tracker],
    }
    formatted = format_user_message_for_agent(message)

    with set_tenant_context(ORG_ID):
        state = await master_engine.ainvoke(
            {"messages": [HumanMessage(content=formatted)], "sender_id": thread_id},
            config=config,
        )

    messages = state.get("messages", [])
    tools = _tools_since(messages, msg_count_before)
    response = _last_ai_text(messages)

    meta = {
        "agent": state.get("active_agent", "?"),
        "handoff": bool(state.get("handoff_requested")),
        "tokens": token_tracker.input_tokens + token_tracker.output_tokens,
        "llm_calls": token_tracker.llm_calls,
        "msg_count": len(messages),
    }
    return meta, tools, response


def _check_turn(
    scenario_id: str,
    turn_idx: int,
    expect: TurnExpect,
    meta: dict,
    tools: list[str],
    response: str,
) -> list[str]:
    errors: list[str] = []
    prefix = f"{scenario_id} T{turn_idx}"

    if meta["agent"] != expect.agent:
        errors.append(f"{prefix}: agent={meta['agent']} (esperado {expect.agent})")
    if meta["handoff"] and not expect.allow_handoff:
        errors.append(f"{prefix}: handoff=True")
    if expect.tools_min and not tools:
        errors.append(
            f"{prefix}: LLM nao chamou tools (esperado {expect.tools_min})"
        )
    elif expect.require_any_tool and not tools:
        errors.append(f"{prefix}: LLM nao chamou nenhuma tool de agenda")
    for tool in expect.tools_min:
        if tool not in tools:
            errors.append(f"{prefix}: faltou tool {tool!r} (chamadas: {tools})")

    lower = response.lower()
    for needle in expect.contains:
        if needle.lower() not in lower:
            errors.append(f"{prefix}: resposta deveria conter {needle!r}")
    for needle in expect.not_contains:
        if needle.lower() in lower:
            errors.append(f"{prefix}: resposta NAO deveria conter {needle!r}")

    if not response.strip():
        errors.append(f"{prefix}: resposta vazia")

    return errors


async def run_scenario(scenario: LlmScenario, verbose: bool) -> tuple[int, int]:
    from packages.engine.prompts.registry import register_salon_prompts

    register_salon_prompts()
    thread_id = str(uuid.uuid4())
    msg_count = 0
    failures = 0
    ok_count = 0

    print(f"\n=== {scenario.id}: {scenario.description} ===")
    print(f"thread={thread_id} | deterministic=OFF\n")

    for i, turn in enumerate(scenario.turns, start=1):
        print(f"--- Turno {i} ---")
        print(f"VOCE: {turn.user}")

        meta, tools, response = await run_turn(turn.user, thread_id, msg_count)
        msg_count = meta["msg_count"]

        print(
            f"Agente: {meta['agent']} | tools={tools} | "
            f"tokens={meta['tokens']} | llm_calls={meta['llm_calls']}"
        )
        preview = response.replace("\n", " ")[:400]
        print(f"RESPOSTA: {preview}{'...' if len(response) > 400 else ''}")

        errors = _check_turn(scenario.id, i, turn, meta, tools, response)
        if errors:
            failures += len(errors)
            for err in errors:
                print(f"  FALHA: {err}")
        else:
            ok_count += 1
            print("  OK")
        if verbose and len(response) > 400:
            print(f"\n{response}\n")

    return ok_count, failures


async def main_async(args: argparse.Namespace) -> int:
    if args.list:
        for s in SCENARIOS:
            print(f"  {s.id:22}  {s.description} ({len(s.turns)} turno(s))")
        return 0

    try:
        from packages.auth_core.config import settings

        if not settings.OPENAI_API_KEY:
            print("OPENAI_API_KEY ausente no .env")
            return 1
        det = settings.SCHEDULING_DETERMINISTIC_ENABLED
        print(f"Modelo: {settings.MODEL_NAME} | SCHEDULING_DETERMINISTIC_ENABLED={det}")
        if det:
            print("AVISO: deterministico ainda ligado — export SCHEDULING_DETERMINISTIC_ENABLED=false")
    except Exception as exc:
        print(f"Erro ao carregar settings: {exc}")
        return 1

    scenarios = SCENARIOS
    if args.scenario:
        scenarios = [s for s in SCENARIOS if s.id == args.scenario]
        if not scenarios:
            print(f"Cenario {args.scenario!r} nao encontrado. Use --list")
            return 1

    total_ok = 0
    total_fail = 0
    for scenario in scenarios:
        ok, fail = await run_scenario(scenario, args.verbose)
        total_ok += ok
        total_fail += fail

    print(f"\n{'=' * 50}")
    print(f"Turnos OK: {total_ok} | falhas: {total_fail}")
    if total_fail:
        print("\nDica: falhas com 'nenhuma tool' = LLM nao usou agenda (prompt ou roteamento).")
        print("      Compare com Chat Test usando thread NOVA apos deploy.")
    return 1 if total_fail else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Teste LLM de agendamento (OpenAI + tools)")
    p.add_argument("-s", "--scenario", metavar="ID", help="Rodar um cenario")
    p.add_argument("--list", action="store_true", help="Listar cenarios")
    p.add_argument("-v", "--verbose", action="store_true", help="Resposta completa")
    return p


def main() -> int:
    return asyncio.run(main_async(build_parser().parse_args()))


if __name__ == "__main__":
    sys.exit(main())
