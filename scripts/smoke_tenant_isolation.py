"""Verificação AO VIVO do isolamento multi-tenant do agente (banco real).

Prova, contra o Supabase real, que o agente de uma org NÃO vaza dados de outra:
cria uma 2ª org temporária com um serviço exclusivo, pergunta por esse serviço
pelo agente da org demo (não deve conhecer) e pelo agente da org temporária
(deve conhecer), confirma o boundary de API (403 cross-org) e limpa tudo.

NÃO roda em CI. Exige `.env` com SUPABASE_URL/SUPABASE_SERVICE_ROLE e um backend
no ar para o modo `probe`. Reaproveita padrões de `onboard_tenant.py`,
`create_salon_user.py` e `smoke_agent.py`.

Uso (PowerShell):
  python -m uvicorn main:app --host 0.0.0.0 --port 8000   # backend (outro terminal)

  py -3.12 scripts/smoke_tenant_isolation.py --mode all \
    --api-url http://localhost:8000/api/v1 \
    --org-a-user dono@beauty-express.com --org-a-pass "<senha ORG_A>" \
    --org-b-user admin@isolation-temp.com --org-b-pass "<senha temp>"

  # ou passo a passo: --mode setup | --mode probe | --mode cleanup
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

# --- Constantes da org temporária (resolvida por slug — sem capturar saída) ---
TEMP_SLUG = "isolation-test-temp"
TEMP_ORG_NAME = "Studio Isolation Temp"
BEAUTY_EXPRESS_ID = "22222222-2222-2222-2222-222222222222"

# Marcador exclusivo da ORG_B (controlado por nós). Preço improvável na demo.
SERVICE_B_NAME = "Barboterapia Studio"
SERVICE_B_PRICE = 277.0
SERVICE_B_MARKERS = ("Barboterapia", "277")

DEFAULT_ORG_A_ID = BEAUTY_EXPRESS_ID


def _get_supabase():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL e SUPABASE_SERVICE_ROLE são obrigatórios no .env")
    from supabase import create_client

    return create_client(url, key)


def _resolve_org_by_slug(sb, slug: str) -> str | None:
    res = sb.table("organizations").select("id").eq("slug", slug).limit(1).execute()
    return res.data[0]["id"] if res.data else None


# --------------------------------------------------------------------------- #
# SETUP                                                                        #
# --------------------------------------------------------------------------- #
def setup(sb, args) -> str:
    print("\n=== [SETUP] org temporária + serviço exclusivo + org_admin ===")

    org_id = _resolve_org_by_slug(sb, TEMP_SLUG)
    if org_id:
        print(f"[SETUP] org já existe (reuso): {org_id}")
    else:
        org_id = str(uuid4())
        sb.table("organizations").insert({
            "id": org_id,
            "name": TEMP_ORG_NAME,
            "slug": TEMP_SLUG,
            "vertical": "salon",
            "is_active": True,
            "timezone": "America/Sao_Paulo",
        }).execute()
        print(f"[SETUP] org criada: {TEMP_ORG_NAME} ({org_id})")

    # Serviço exclusivo (professional_id nulo — coluna legada nullable).
    svc = (
        sb.table("service_catalog")
        .select("id")
        .eq("organization_id", org_id)
        .eq("name", SERVICE_B_NAME)
        .limit(1)
        .execute()
    )
    if svc.data:
        print(f"[SETUP] serviço já existe (reuso): {SERVICE_B_NAME}")
    else:
        sb.table("service_catalog").insert({
            "id": str(uuid4()),
            "organization_id": org_id,
            "name": SERVICE_B_NAME,
            "duration_minutes": 45,
            "price": SERVICE_B_PRICE,
            "category": "Teste",
            "professional_id": None,
            "is_active": True,
        }).execute()
        print(f"[SETUP] serviço criado: {SERVICE_B_NAME} (R$ {SERVICE_B_PRICE:.2f})")

    # org_admin da ORG_B (Auth user + dashboard_users), como create_salon_user.py.
    row = {"role": "org_admin", "organization_id": org_id, "professional_id": None}
    existing = (
        sb.table("dashboard_users").select("id").eq("email", args.org_b_user).limit(1).execute()
    )
    if existing.data:
        user_id = existing.data[0]["id"]
        sb.auth.admin.update_user_by_id(user_id, {"password": args.org_b_pass})
        sb.table("dashboard_users").update(row).eq("id", user_id).execute()
        print(f"[SETUP] org_admin atualizado: {args.org_b_user}")
    else:
        auth_res = sb.auth.admin.create_user({
            "email": args.org_b_user,
            "password": args.org_b_pass,
            "email_confirm": True,
        })
        if not auth_res.user:
            raise RuntimeError("falha ao criar usuário no Supabase Auth")
        sb.table("dashboard_users").insert(
            {"id": auth_res.user.id, "email": args.org_b_user, **row}
        ).execute()
        print(f"[SETUP] org_admin criado: {args.org_b_user}")

    print(f"[SETUP] OK — ORG_B={org_id} | marcador exclusivo: {SERVICE_B_MARKERS}")
    return org_id


# --------------------------------------------------------------------------- #
# PROBE (HTTP)                                                                 #
# --------------------------------------------------------------------------- #
def _login(base: str, username: str, password: str) -> httpx.Client:
    client = httpx.Client(timeout=120.0, follow_redirects=True)
    resp = client.post(f"{base}/auth/login", json={"username": username, "password": password})
    if resp.status_code != 200:
        client.close()
        raise RuntimeError(f"login {username} HTTP {resp.status_code}: {resp.text[:200]}")
    return client


def _ask(client: httpx.Client, base: str, org_id: str, message: str):
    resp = client.post(
        f"{base}/chat/test",
        json={"message": message, "thread_id": str(uuid4())},
        headers={"x-organization-id": org_id},
    )
    return resp


def probe(args, org_b_id: str) -> int:
    print("\n=== [PROBE] cross-tenant via /chat/test ===")
    base = args.api_url.rstrip("/")
    org_a_id = args.org_a_id
    failures: list[str] = []
    a = b = None
    try:
        a = _login(base, args.org_a_user, args.org_a_pass)
        b = _login(base, args.org_b_user, args.org_b_pass)
        print(f"[PROBE] login OK: {args.org_a_user} (ORG_A) e {args.org_b_user} (ORG_B)")

        q_b = f"Quanto custa {SERVICE_B_NAME}?"

        # 1. Sanity ORG_B: o dado existe para a própria org.
        r = _ask(b, base, org_b_id, q_b)
        txt = (r.json().get("response") or "") if r.status_code == 200 else ""
        if r.status_code == 200 and "277" in txt:
            print(f"[PROBE] 1 sanity ORG_B: OK (resposta cita 277) — {txt[:120]!r}")
        else:
            failures.append(f"sanity ORG_B (HTTP {r.status_code}, cita 277? {'277' in txt})")
            print(f"[PROBE] 1 sanity ORG_B: FALHOU — HTTP {r.status_code} — {txt[:160]!r}")

        # 2. No-leak: ORG_A NÃO conhece o serviço exclusivo da ORG_B.
        r = _ask(a, base, org_a_id, q_b)
        txt = (r.json().get("response") or "") if r.status_code == 200 else ""
        lower = txt.lower()
        leaked = [m for m in SERVICE_B_MARKERS if m.lower() in lower]
        if r.status_code == 200 and not leaked:
            print(f"[PROBE] 2 no-leak ORG_A: OK (sem marcadores da ORG_B) — {txt[:120]!r}")
        else:
            failures.append(f"no-leak ORG_A vazou {leaked} (HTTP {r.status_code})")
            print(f"[PROBE] 2 no-leak ORG_A: FALHOU — vazou {leaked} — {txt[:200]!r}")

        # 3. Spoof 403: header de outra org com JWT de org_admin.
        r = _ask(a, base, org_b_id, "oi")
        if r.status_code == 403:
            print("[PROBE] 3a spoof ORG_A→ORG_B: OK (403)")
        else:
            failures.append(f"spoof ORG_A→ORG_B esperava 403, veio {r.status_code}")
            print(f"[PROBE] 3a spoof ORG_A→ORG_B: FALHOU — HTTP {r.status_code}")

        r = _ask(b, base, org_a_id, "oi")
        if r.status_code == 403:
            print("[PROBE] 3b spoof ORG_B→ORG_A: OK (403)")
        else:
            failures.append(f"spoof ORG_B→ORG_A esperava 403, veio {r.status_code}")
            print(f"[PROBE] 3b spoof ORG_B→ORG_A: FALHOU — HTTP {r.status_code}")

        # 4. Best-effort (direção reversa): ORG_B não cita serviço real da ORG_A.
        r = _ask(b, base, org_b_id, f"Quanto custa {args.service_a_query}?")
        txt = (r.json().get("response") or "") if r.status_code == 200 else ""
        if r.status_code == 200 and args.service_a_marker.lower() not in txt.lower():
            print(f"[PROBE] 4 reverso ORG_B: OK (sem marcador {args.service_a_marker!r} da ORG_A)")
        else:
            print(
                f"[PROBE] 4 reverso ORG_B: AVISO — revisar manualmente "
                f"(HTTP {r.status_code}; marcador ORG_A pode divergir) — {txt[:160]!r}"
            )
    finally:
        if a:
            a.close()
        if b:
            b.close()

    print("\n" + "=" * 50)
    if failures:
        print("[PROBE] FALHAS:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("[PROBE] Isolamento ao vivo: OK")
    return 0


# --------------------------------------------------------------------------- #
# CLEANUP                                                                      #
# --------------------------------------------------------------------------- #
def cleanup(sb, args) -> None:
    print("\n=== [CLEANUP] removendo artefatos da org temporária ===")
    org_id = _resolve_org_by_slug(sb, TEMP_SLUG)
    if not org_id:
        print("[CLEANUP] nada a remover (org temporária não encontrada).")
        return

    # Guard: nunca apagar a org demo.
    if org_id == BEAUTY_EXPRESS_ID:
        raise RuntimeError("ABORT: slug temporário aponta para Beauty Express — não vou apagar.")

    sb.table("conversation_metrics").delete().eq("organization_id", org_id).execute()
    print("[CLEANUP] conversation_metrics removidos")

    sb.table("service_catalog").delete().eq("organization_id", org_id).execute()
    print("[CLEANUP] service_catalog removido")

    users = (
        sb.table("dashboard_users").select("id").eq("organization_id", org_id).execute()
    )
    for u in users.data or []:
        uid = u["id"]
        sb.table("dashboard_users").delete().eq("id", uid).execute()
        try:
            sb.auth.admin.delete_user(uid)
        except Exception as e:  # auth user pode já não existir
            print(f"[CLEANUP] aviso auth delete {uid[:8]}: {e}")
    print(f"[CLEANUP] dashboard_users + Auth users removidos ({len(users.data or [])})")

    sb.table("organizations").delete().eq("id", org_id).execute()
    print(f"[CLEANUP] organização {org_id} removida")

    if args.with_checkpoints:
        _cleanup_checkpoints(org_id)


def _cleanup_checkpoints(org_id: str) -> None:
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("[CLEANUP] SUPABASE_DB_URL ausente — pulei checkpoints")
        return
    try:
        import psycopg
    except ImportError:
        print("[CLEANUP] psycopg indisponível — pulei checkpoints")
        return
    like = f"{org_id}:%"
    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
            try:
                cur.execute(f"DELETE FROM {table} WHERE thread_id LIKE %s", (like,))
            except Exception as e:
                print(f"[CLEANUP] aviso {table}: {e}")
        conn.commit()
    print("[CLEANUP] checkpoints removidos")


# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description="Verificação ao vivo do isolamento multi-tenant")
    parser.add_argument("--mode", choices=["setup", "probe", "cleanup", "all"], default="all")
    parser.add_argument("--api-url", default="http://localhost:8000/api/v1")
    parser.add_argument("--org-a-id", default=DEFAULT_ORG_A_ID, help="org demo (Beauty Express)")
    parser.add_argument("--org-a-user", default="dono@beauty-express.com")
    parser.add_argument("--org-a-pass", default=os.getenv("PROD_SMOKE_PASSWORD") or "")
    parser.add_argument("--org-b-user", default="admin@isolation-temp.com")
    parser.add_argument("--org-b-pass", default="IsolationTemp123!")
    parser.add_argument(
        "--service-a-query", default="Coloração Completa", help="serviço real da ORG_A (reverso)"
    )
    parser.add_argument(
        "--service-a-marker", default="250", help="marcador da ORG_A p/ checagem reversa (soft)"
    )
    parser.add_argument("--with-checkpoints", action="store_true", help="também limpa checkpoints")
    args = parser.parse_args()

    try:
        if args.mode == "setup":
            setup(_get_supabase(), args)
            return 0

        if args.mode == "probe":
            sb = _get_supabase()
            org_b_id = _resolve_org_by_slug(sb, TEMP_SLUG)
            if not org_b_id:
                print("ERRO: ORG_B não existe. Rode --mode setup primeiro.")
                return 1
            return probe(args, org_b_id)

        if args.mode == "cleanup":
            cleanup(_get_supabase(), args)
            return 0

        # all: setup → probe → cleanup (cleanup sempre, mesmo se probe falhar)
        sb = _get_supabase()
        org_b_id = setup(sb, args)
        try:
            code = probe(args, org_b_id)
        finally:
            cleanup(sb, args)
        return code
    except Exception as exc:
        print(f"ERRO: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
