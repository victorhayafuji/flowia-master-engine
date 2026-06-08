"""Smoke test do agente IA via API /chat/test (local ou produção)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid

import httpx

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Testa agente LangGraph via /chat/test")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000/api/v1",
        help="Base API (ex: https://flowia-api.onrender.com/api/v1)",
    )
    parser.add_argument("--username", default="dono@beauty-express.com")
    parser.add_argument(
        "--password",
        default=os.getenv("PROD_SMOKE_PASSWORD") or os.getenv("VITE_DEV_PASSWORD") or "",
    )
    parser.add_argument(
        "--org-id",
        default="22222222-2222-2222-2222-222222222222",
        help="x-organization-id header",
    )
    args = parser.parse_args()

    base = args.api_url.rstrip("/")
    thread_id = str(uuid.uuid4())
    failures: list[str] = []

    scenarios = [
        {
            "name": "RAG preços",
            "message": "Quanto custa o corte feminino?",
            "expect_any": ["120", "R$", "corte", "preço", "preco", "valor"],
        },
        {
            "name": "Agendamento",
            "message": "Quero agendar manicure amanhã, quais horários disponíveis?",
            "expect_any": ["horário", "horario", "dispon", "10:", "14:", "09:", "manicure", "agendar"],
        },
        {
            "name": "Hybrid scheduling",
            "message": "Quero mechas sexta",
            "expect_agent": "scheduling",
            "expect_path": "deterministic",
            "require_triage": True,
            "expect_any": ["mechas", "sexta", "horário", "horario", "dispon", "14:", "09:", "agendar"],
        },
        {
            "name": "Recepção",
            "message": "Quais serviços vocês oferecem?",
            "expect_any": ["servi", "corte", "manicure", "salão", "salao", "beauty"],
        },
    ]

    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        login = client.post(
            f"{base}/auth/login",
            json={"username": args.username, "password": args.password},
        )
        if login.status_code != 200:
            print(f"ERRO login HTTP {login.status_code}: {login.text[:200]}")
            return 1
        print(f"OK login como {args.username}")

        headers = {"x-organization-id": args.org_id}

        for scenario in scenarios:
            print(f"\n--- {scenario['name']} ---")
            print(f"Pergunta: {scenario['message']}")
            try:
                resp = client.post(
                    f"{base}/chat/test",
                    json={"message": scenario["message"], "thread_id": thread_id},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                failures.append(f"{scenario['name']}: {exc}")
                print(f"FALHOU: {exc}")
                continue

            answer = (data.get("response") or "").strip()
            agent = data.get("agent", "?")
            tokens = data.get("tokens_used", 0)
            path = data.get("scheduling_path")
            triage = data.get("triage_source")
            print(
                f"Agente: {agent} | tokens: {tokens}"
                + (f" | path: {path} | triage: {triage}" if path or triage else "")
            )
            print(f"Resposta: {answer[:400]}{'...' if len(answer) > 400 else ''}")

            expected_agent = scenario.get("expect_agent")
            if expected_agent and agent != expected_agent:
                failures.append(f"{scenario['name']}: agent={agent} (esperado {expected_agent})")
                print(f"FALHOU: agent={agent}")
                continue

            expected_path = scenario.get("expect_path")
            if expected_path and path != expected_path:
                failures.append(f"{scenario['name']}: path={path} (esperado {expected_path})")
                print(f"FALHOU: scheduling_path={path}")
                continue

            if scenario.get("require_triage") and not triage:
                failures.append(f"{scenario['name']}: triage_source ausente")
                print("FALHOU: triage_source ausente")
                continue

            lower = answer.lower()
            if not answer:
                failures.append(f"{scenario['name']}: resposta vazia")
                print("FALHOU: resposta vazia")
            elif not any(k.lower() in lower for k in scenario["expect_any"]):
                failures.append(f"{scenario['name']}: resposta sem keywords esperadas")
                print("AVISO: resposta OK mas sem keywords esperadas (revisar manualmente)")
            else:
                print("OK")

    print("\n" + "=" * 50)
    if failures:
        print("Falhas:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("Agente IA: smoke OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
