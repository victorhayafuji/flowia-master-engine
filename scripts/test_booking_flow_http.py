"""Teste multi-turno via HTTP /chat/test (mesmo fluxo do Chat Test UI)."""
from __future__ import annotations

import sys
import uuid

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
ORG = "22222222-2222-2222-2222-222222222222"
EMAIL = "dono@beauty-express.com"
PASSWORD = "senha123"

TURNS = [
    "Quero agendar coloração na sexta",
    "Sou Victor, 11987654320",
    "Tem agendamento para às 11:00?",
]


def main() -> int:
    thread_id = str(uuid.uuid4())
    failures: list[str] = []

    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        login = client.post(f"{BASE}/auth/login", json={"username": EMAIL, "password": PASSWORD})
        if login.status_code != 200:
            print(f"Login falhou ({login.status_code}): {login.text[:200]}")
            print("Ajuste --email/--password ou use VITE_DEV_SALON_* do .env")
            return 1

        headers = {"x-organization-id": ORG}
        print(f"Login OK | thread={thread_id}\n")

        for i, message in enumerate(TURNS, 1):
            resp = client.post(
                f"{BASE}/chat/test",
                json={"message": message, "thread_id": thread_id},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            agent = data.get("agent", "?")
            handoff = data.get("handoff", False)
            path = data.get("scheduling_path")
            triage = data.get("triage_source")
            answer = (data.get("response") or "").strip()

            print(f"--- Turno {i} ---")
            print(f"VOCÊ: {message}")
            print(
                f"Agente: {agent} | handoff={handoff} | tokens={data.get('tokens_used', 0)}"
                f" | path={path} | triage={triage}"
            )
            print(f"RESPOSTA: {answer[:400]}\n")

            if i >= 1 and agent != "scheduling":
                failures.append(f"Turno {i}: agent={agent} (esperado scheduling)")
            if handoff:
                failures.append(f"Turno {i}: handoff=True")

    if failures:
        print("FALHAS:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("OK via API — abra http://localhost:5173/admin/chat-test para repetir no browser")
    return 0


if __name__ == "__main__":
    sys.exit(main())
