"""Compara custo do hibrido (executor + LLM fallback) vs LLM puro.

  py -3 scripts/test_scheduling_hybrid.py
  py -3 scripts/test_scheduling_hybrid.py -v
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

os.environ.setdefault("CHECKPOINTER_BACKEND", "memory")
os.environ.setdefault("SCHEDULER_ENABLED", "false")

ORG_ID = "22222222-2222-2222-2222-222222222222"

TURNS = [
    "Quero agendar corte masculino no dia 10 de junho",
    "Meu nome e Pedro Silva, telefone 11987654353",
    "Pode ser as 15:00?",
]


async def _run_mode(
    *,
    deterministic: bool,
    llm_fallback: str,
    label: str,
) -> dict:
    os.environ["SCHEDULING_DETERMINISTIC_ENABLED"] = "true" if deterministic else "false"
    os.environ["SCHEDULING_LLM_FALLBACK"] = llm_fallback

    from importlib import reload

    import packages.auth_core.config as config_mod
    import packages.engine.engine as engine_mod
    from langchain_core.messages import HumanMessage
    from packages.auth_core.tenant import set_tenant_context
    from packages.engine.checkpointer import master_engine
    from packages.engine.input_guard import format_user_message_for_agent
    from packages.engine.prompts.registry import register_salon_prompts
    from packages.engine.token_tracking import TurnTokenTracker

    reload(config_mod)
    reload(engine_mod)
    register_salon_prompts()

    thread_id = str(uuid.uuid4())
    total_tokens = 0
    total_llm_calls = 0
    responses: list[str] = []

    with set_tenant_context(ORG_ID):
        for turn in TURNS:
            tracker = TurnTokenTracker()
            config = {
                "configurable": {"thread_id": thread_id, "org_id": ORG_ID, "channel": "hybrid_test"},
                "callbacks": [tracker],
            }
            state = await master_engine.ainvoke(
                {
                    "messages": [
                        HumanMessage(content=format_user_message_for_agent(turn)),
                    ],
                    "sender_id": thread_id,
                },
                config=config,
            )
            total_tokens += tracker.input_tokens + tracker.output_tokens
            total_llm_calls += tracker.llm_calls
            msgs = state.get("messages", [])
            for msg in reversed(msgs):
                if msg.type == "ai" and getattr(msg, "content", ""):
                    responses.append(str(msg.content)[:200])
                    break

    return {
        "label": label,
        "tokens": total_tokens,
        "llm_calls": total_llm_calls,
        "responses": responses,
    }


async def main() -> int:
    verbose = "-v" in sys.argv

    print("Fluxo 3 turnos | Beauty Express\n")

    hybrid = await _run_mode(
        deterministic=True,
        llm_fallback="smart",
        label="hibrido (executor + LLM se precisar)",
    )
    llm_only = await _run_mode(
        deterministic=False,
        llm_fallback="always",
        label="LLM puro (sem executor)",
    )

    for row in (hybrid, llm_only):
        print(f"=== {row['label']} ===")
        print(f"  tokens: {row['tokens']} | chamadas LLM: {row['llm_calls']}")
        if verbose:
            for i, resp in enumerate(row["responses"], 1):
                print(f"  T{i}: {resp}")
        print()

    saved = llm_only["tokens"] - hybrid["tokens"]
    pct = (saved / llm_only["tokens"] * 100) if llm_only["tokens"] else 0
    print(f"Economia hibrido vs LLM puro: {saved} tokens (~{pct:.0f}%)")

    if hybrid["tokens"] >= llm_only["tokens"]:
        print("\nAVISO: hibrido nao economizou — executor pode estar caindo no LLM.")
        print("Verifique logs 'Scheduling path=deterministic' vs 'path=llm' no backend.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
