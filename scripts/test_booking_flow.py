"""Multi-turn booking smoke test (local LangGraph, código atual)."""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

os.environ.setdefault("CHECKPOINTER_BACKEND", "memory")
os.environ.setdefault("SCHEDULER_ENABLED", "false")

ORG_ID = "22222222-2222-2222-2222-222222222222"

TURNS = [
    "Quero agendar coloração na sexta-feira, 13/06/2026",
    "Sou Victor, 11987654320",
    "Tem horário disponível às 11:00?",
]


async def main() -> int:
    from packages.engine.prompts.registry import register_salon_prompts
    from packages.auth_core.tenant import set_tenant_context
    from packages.engine.service import dispatch_chat_test

    register_salon_prompts()

    thread_id = str(uuid.uuid4())
    print(f"Thread: {thread_id}\n")

    failures: list[str] = []

    for i, message in enumerate(TURNS, start=1):
        print(f"--- Turno {i} ---")
        print(f"VOCÊ: {message}")
        with set_tenant_context(ORG_ID):
            result = await dispatch_chat_test(message, thread_id=thread_id)

        agent = result.get("agent", "?")
        handoff = result.get("handoff", False)
        response = (result.get("response") or "").strip()
        tokens = result.get("tokens_used", 0)

        print(f"Agente: {agent} | handoff={handoff} | tokens={tokens}")
        print(f"RESPOSTA: {response[:500]}{'...' if len(response) > 500 else ''}\n")

        if i >= 2 and agent != "scheduling":
            failures.append(f"Turno {i}: esperado agent=scheduling, veio {agent}")
        if handoff:
            failures.append(f"Turno {i}: handoff indevido")
        if i == 3 and any(
            phrase in response.lower()
            for phrase in ("atendente", "entrar em contato", "transferir", "solicitei")
        ):
            failures.append(f"Turno {i}: resposta parece handoff humano em vez de tool de agenda")

    print("=" * 50)
    if failures:
        print("FALHAS:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("OK: fluxo de agendamento concluído com agente scheduling")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
