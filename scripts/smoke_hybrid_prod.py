"""Smoke pós-deploy: health, auth, motor híbrido (scheduling_path) e today-board."""
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


def _normalize_api_base(raw: str) -> tuple[str, str]:
    base = raw.rstrip("/")
    if base.endswith("/api/v1"):
        return base[: -len("/api/v1")], base
    return base, f"{base}/api/v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="FlowIA hybrid agent production smoke")
    parser.add_argument(
        "--api-url",
        default="https://flowia-api.onrender.com",
        help="API origin or .../api/v1",
    )
    parser.add_argument("--username", default="dono@beauty-express.com")
    parser.add_argument(
        "--password",
        default=os.getenv("PROD_SMOKE_PASSWORD") or os.getenv("VITE_DEV_PASSWORD") or "",
        help="Senha piloto (ou env PROD_SMOKE_PASSWORD / VITE_DEV_PASSWORD via .env)",
    )
    parser.add_argument(
        "--org-id",
        default="22222222-2222-2222-2222-222222222222",
        help="x-organization-id header",
    )
    args = parser.parse_args()

    if not args.password:
        print("ERRO: informe --password ou PROD_SMOKE_PASSWORD")
        return 1

    origin, api_v1 = _normalize_api_base(args.api_url)
    failures: list[str] = []
    thread_id = str(uuid.uuid4())

    def ok(label: str, detail: str = "") -> None:
        suffix = f" — {detail}" if detail else ""
        print(f"OK {label}{suffix}")

    def fail(label: str, detail: str) -> None:
        failures.append(f"{label}: {detail}")
        print(f"FAIL {label}: {detail}")

    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        try:
            resp = client.get(f"{origin}/health")
            resp.raise_for_status()
            health = resp.json()
            if health.get("status") != "ok":
                fail("health", f"status={health.get('status')}")
            elif health.get("database") != "connected":
                fail("health", f"database={health.get('database')}")
            else:
                ok("health", json.dumps(health, ensure_ascii=False))
        except Exception as exc:
            fail("health", str(exc))
            print("\nAbortando — API inacessível.")
            return 1

        login = client.post(
            f"{api_v1}/auth/login",
            json={"username": args.username, "password": args.password},
        )
        if login.status_code != 200:
            fail("login", f"HTTP {login.status_code}: {login.text[:200]}")
            return 1
        ok("login", args.username)

        headers = {"x-organization-id": args.org_id}

        me = client.get(f"{api_v1}/auth/me", headers=headers)
        if me.status_code != 200:
            fail("auth/me", f"HTTP {me.status_code}")
        else:
            role = (me.json().get("user") or {}).get("role")
            if role != "org_admin":
                fail("auth/me", f"role={role} (esperado org_admin)")
            else:
                ok("auth/me", f"role={role}")

        turn1_msg = "Quero mechas sexta"
        try:
            resp = client.post(
                f"{api_v1}/chat/test",
                json={"message": turn1_msg, "thread_id": thread_id},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            fail("chat/test turno1", str(exc))
            data = {}

        if data:
            agent = data.get("agent")
            path = data.get("scheduling_path")
            triage = data.get("triage_source")
            tokens = data.get("tokens_used", 0)
            answer = (data.get("response") or "").strip()
            print(f"  turno1 agent={agent} path={path} triage={triage} tokens={tokens}")
            print(f"  resposta: {answer[:200]}{'...' if len(answer) > 200 else ''}")

            if agent != "scheduling":
                fail("chat/test turno1", f"agent={agent}")
            elif path != "deterministic":
                fail("chat/test turno1", f"scheduling_path={path} (esperado deterministic)")
            elif not triage:
                fail("chat/test turno1", "triage_source ausente")
            elif not answer:
                fail("chat/test turno1", "resposta vazia")
            else:
                ok("chat/test turno1", f"path={path} triage={triage}")

        turn2_msg = "14:00"
        try:
            resp = client.post(
                f"{api_v1}/chat/test",
                json={"message": turn2_msg, "thread_id": thread_id},
                headers=headers,
            )
            resp.raise_for_status()
            data2 = resp.json()
        except Exception as exc:
            fail("chat/test turno2", str(exc))
            data2 = {}

        if data2:
            agent2 = data2.get("agent")
            answer2 = (data2.get("response") or "").strip()
            print(f"  turno2 agent={agent2} path={data2.get('scheduling_path')} tokens={data2.get('tokens_used', 0)}")
            if agent2 != "scheduling":
                fail("chat/test turno2", f"agent={agent2}")
            elif not answer2:
                fail("chat/test turno2", "resposta vazia")
            else:
                ok("chat/test turno2", answer2[:80])

        board = client.get(f"{api_v1}/dashboard/today-board", headers=headers)
        if board.status_code != 200:
            fail("dashboard/today-board", f"HTTP {board.status_code}")
        else:
            payload = board.json().get("data", {})
            ok(
                "dashboard/today-board",
                f"pros={len(payload.get('board', []))} total={payload.get('counts', {}).get('total')}",
            )

    print("\n" + "=" * 50)
    if failures:
        print("FALHOU:")
        for item in failures:
            print(f"  - {item}")
        return 1

    print(f"Smoke híbrido OK | thread_id={thread_id}")
    print("Próximo: validar conversation_metrics no Supabase e smoke manual no browser (/agenda).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
