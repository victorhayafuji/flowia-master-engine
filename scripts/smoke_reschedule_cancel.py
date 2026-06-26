"""Smoke E2E do recurso reagendar/cancelar via /chat/test.

Cria 1 cliente + 1 agendamento futuro na Beauty Express, depois roda cenários
multi-turn pelo /chat/test (mesma rota que o "Ensaie" usa). Imprime veredito por
cenário e cleanup ao final.

Uso:
    py -3.12 scripts/smoke_reschedule_cancel.py \\
        --username dono@beauty-express.com --password ***
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

SALON_ORG_ID = "22222222-2222-2222-2222-222222222222"
TZ = ZoneInfo("America/Sao_Paulo")


def _next_weekday_at(hour: int = 14, minute: int = 0, days_ahead: int = 3) -> datetime:
    """Próxima data útil às HH:MM no fuso do salão, X dias à frente (default 3)."""
    now = datetime.now(TZ)
    target = (now + timedelta(days=days_ahead)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    # pula domingo (6) -- Beauty Express tem horário seg-sex (default no _get_org_config)
    while target.weekday() in (5, 6):
        target += timedelta(days=1)
    return target


def _pick_resource(rows: list[dict], name: str) -> dict | None:
    for r in rows or []:
        if (r.get("name") or "").lower() == name.lower():
            return r
    return rows[0] if rows else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-url", default="http://localhost:8000/api/v1")
    ap.add_argument("--username", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--org-id", default=SALON_ORG_ID)
    args = ap.parse_args()

    base = args.api_url.rstrip("/")
    headers = {"x-organization-id": args.org_id}
    failures: list[str] = []
    patient_id: str | None = None
    appointment_id: str | None = None

    with httpx.Client(timeout=180.0, follow_redirects=True) as client:
        # 1. Login (cookie JWT)
        r = client.post(f"{base}/auth/login", json={"username": args.username, "password": args.password})
        if r.status_code != 200:
            print(f"[FAIL] Login HTTP {r.status_code}: {r.text[:200]}")
            return 1
        print(f"[OK] Login: {args.username}")

        # 2. Dados de teste
        services = (client.get(f"{base}/organizations/services", headers=headers).json() or {}).get("data") or []
        pros = (client.get(f"{base}/organizations/professionals", headers=headers).json() or {}).get("data") or []
        if not services or not pros:
            print("[FAIL] Beauty Express sem serviços/profissionais cadastrados -- seed primeiro.")
            return 1
        service = _pick_resource(services, "Corte Feminino") or services[0]
        pro = _pick_resource(pros, "Maria")  # qualquer um serve

        unique = uuid.uuid4().hex[:6]
        patient_phone = f"5511{unique[:9]}".ljust(13, "0")
        patient_name = f"Smoke Tester {unique}"
        r = client.post(
            f"{base}/patients/",
            json={"name": patient_name, "phone": patient_phone},
            headers=headers,
        )
        if r.status_code not in (200, 201):
            print(f"[FAIL] Criar paciente HTTP {r.status_code}: {r.text[:200]}")
            return 1
        patient_id = (r.json().get("data") or r.json()).get("id")
        print(f"[OK] Paciente: {patient_name} (id={patient_id[:8]}...)")

        sched_at = _next_weekday_at(14, 0, days_ahead=3)
        r = client.post(
            f"{base}/scheduling/",
            json={
                "patient_id": patient_id,
                "professional_id": pro["id"] if pro else pros[0]["id"],
                "service_id": service["id"],
                "scheduled_at": sched_at.isoformat(),
                "duration_minutes": int(service.get("duration_minutes") or 30),
            },
            headers=headers,
        )
        if r.status_code not in (200, 201):
            print(f"[FAIL] Criar appointment HTTP {r.status_code}: {r.text[:200]}")
            return 1
        appointment_id = (r.json().get("data") or r.json()).get("id")
        local_label = sched_at.strftime("%d/%m %H:%M")
        print(f"[OK] Agendamento: {service['name']} em {local_label} (id={appointment_id[:8]}...)")

        # 3. Cenários de chat (multi-turn por thread)
        def chat(thread: str, msg: str, label: str, _retry: bool = False) -> dict:
            r = client.post(
                f"{base}/chat/test",
                json={"message": msg, "thread_id": thread, "guided": False, "patient_id": patient_id},
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()
            resp = (data.get("response") or "").strip()
            agent = data.get("agent")
            path = data.get("scheduling_path")
            triage = data.get("triage_source")
            tools = data.get("tools_called") or []
            # 1ª msg de thread nova abre o aviso LGPD (agent=compliance); aceita e refaz.
            if agent == "compliance" and not _retry:
                client.post(
                    f"{base}/chat/test",
                    json={"message": "ok", "thread_id": thread, "guided": False, "patient_id": patient_id},
                    headers=headers,
                )
                return chat(thread, msg, label, _retry=True)
            print(
                f"   -> agent={agent} path={path} triage={triage} tools={tools}\n"
                f"     > {resp[:280]}{'...' if len(resp) > 280 else ''}"
            )
            return {"text": resp, "agent": agent, "path": path, "tools": tools}

        def expect(cond: bool, msg: str) -> None:
            if not cond:
                failures.append(msg)
                print(f"   [FAIL] {msg}")
            else:
                print(f"   [OK] {msg}")

        # Cenário 1: list_my_appointments
        print("\n-- Cenário 1: listar meus agendamentos --")
        t1 = str(uuid.uuid4())
        out = chat(t1, "Quais são meus agendamentos?", "list")
        expect(service["name"].lower() in out["text"].lower(), "menciona o serviço agendado")

        # Cenário 2: reagendar single-shot (mesmo dia, hora livre)
        print("\n-- Cenário 2: reagendar single-shot --")
        t2 = str(uuid.uuid4())
        new_dt = sched_at.replace(hour=16, minute=0)  # 16:00 mesmo dia
        new_label = new_dt.strftime("%d/%m às %H:%M")
        out = chat(t2, f"Quero remarcar para {new_label}", "reschedule single")
        expect(out["agent"] == "scheduling", "agente=scheduling")
        expect("reschedule_time" in out["tools"] or "remarcad" in out["text"].lower(),
               "tool reschedule_time foi chamada ou confirmou remarcação")

        # Cenário 3: reagendar multi-turn (a feature do #38)
        print("\n-- Cenário 3: reagendar multi-turn (#38) --")
        t3 = str(uuid.uuid4())
        chat(t3, "Quero remarcar", "reschedule turn 1")
        new_dt2 = sched_at.replace(hour=10, minute=0)
        out = chat(t3, f"Pode ser {new_dt2.strftime('%d/%m às %H:%M')}", "reschedule turn 2")
        expect(out["path"] == "llm", "scheduling_path=llm na 2ª mensagem (sem verbo)")

        # Cenário 4: cancelar com confirmação (suporte)
        print("\n-- Cenário 4: cancelar (2 passos) --")
        t4 = str(uuid.uuid4())
        out = chat(t4, "Quero cancelar meu agendamento", "cancel turn 1")
        expect(out["agent"] == "support", "agente=support para cancelar")
        expect("confirma" in out["text"].lower(), "pede confirmação no turno 1")
        out = chat(t4, "sim, pode cancelar", "cancel turn 2")
        expect("cancel_appointment" in out["tools"] or "cancel" in out["text"].lower(),
               "tool cancel_appointment foi chamada ou confirmou cancelamento")

        # Cenário 5: política ≠ ação (não regrediu)
        print("\n-- Cenário 5: política de cancelamento (não dispara cancel) --")
        t5 = str(uuid.uuid4())
        out = chat(t5, "Qual a política de cancelamento?", "policy")
        expect("cancel_appointment" not in out["tools"], "NÃO chamou cancel_appointment")

        # 4. Cleanup best-effort
        print("\n-- Cleanup --")
        try:
            client.delete(f"{base}/patients/{patient_id}", headers=headers)
            print(f"   [OK] paciente {patient_id[:8]} desativado")
        except Exception as exc:
            print(f"   [!] cleanup paciente: {exc}")

    # 5. Veredito
    print("\n" + "=" * 60)
    if failures:
        print(f"[FAIL] {len(failures)} falha(s):")
        for f in failures:
            print(f"   - {f}")
        return 1
    print("[OK] Smoke reagendar/cancelar: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
