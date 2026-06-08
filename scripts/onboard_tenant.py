"""
Runbook interativo para onboarding de novo salão pagante (SaaS compartilhado).

Uso:
  python scripts/onboard_tenant.py --checklist          # imprime passos
  python scripts/onboard_tenant.py --name "Salão X" --slug salao-x --email dono@salao.com --password "SenhaForte1!"
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

CHECKLIST = """
Onboarding — novo salão pagante (sem novo Render/Supabase)
==========================================================
0. Prod real: Supabase prod separado + secrets novos (docs/PRODUCTION.md)
1. Organization: vertical=salon, slug único
2. Dono: create_salon_user.py --role org_admin
3. Catálogo: serviços + profissionais no dashboard
3b. Funcionários (opcional): create_salon_user.py --role professional --professional-id <UUID>
4. KB: upload Data Lake ou seed_datalake.py --org <UUID>
5. WhatsApp: organizations.whatsapp_phone_id + whatsapp_access_token (docs/WHATSAPP_SETUP.md)
6. Smoke: login + agendamento; chat/WhatsApp quando Meta ativo
7. LGPD: PRIVACY_CONTACT_EMAIL, PRIVACY_POLICY_URL, docs/legal/LGPD_ONBOARDING_CHECKLIST.md
Webhook prod: https://flowia-api.onrender.com/api/v1/webhook/whatsapp
"""


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "salon"


def print_checklist() -> None:
    print(CHECKLIST.strip())


def create_organization(name: str, slug: str) -> str:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL e SUPABASE_SERVICE_ROLE são obrigatórios no .env")

    from supabase import create_client

    org_id = str(uuid4())
    supabase = create_client(url, key)
    existing = supabase.table("organizations").select("id").eq("slug", slug).limit(1).execute()
    if existing.data:
        raise RuntimeError(f"Slug '{slug}' já existe — escolha outro")

    payload = {
        "id": org_id,
        "name": name,
        "slug": slug,
        "vertical": "salon",
        "is_active": True,
        "timezone": "America/Sao_Paulo",
    }
    supabase.table("organizations").insert(payload).execute()
    return org_id


def create_owner(email: str, password: str, org_id: str) -> None:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "create_salon_user.py"),
        "--email",
        email,
        "--password",
        password,
        "--org",
        org_id,
    ]
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Onboarding de novo tenant salão")
    parser.add_argument("--checklist", action="store_true", help="Imprime checklist e sai")
    parser.add_argument("--name", help="Nome do salão (ex: Studio Bella)")
    parser.add_argument("--slug", help="Slug único (ex: studio-bella)")
    parser.add_argument("--email", help="Email do org_admin")
    parser.add_argument("--password", help="Senha inicial do org_admin")
    args = parser.parse_args()

    if args.checklist or not args.name:
        print_checklist()
        if not args.name:
            print("\nPara criar org + dono: --name ... --email ... --password ...")
        return 0

    if not args.email or not args.password:
        print("ERRO: --email e --password são obrigatórios para criar tenant")
        return 1

    slug = args.slug or _slugify(args.name)
    try:
        org_id = create_organization(args.name, slug)
        print(f"Organization criada: {args.name} ({org_id}) slug={slug}")
        create_owner(args.email, args.password, org_id)
        print(f"org_admin criado: {args.email}")
        print("\nPróximos passos:")
        print(f"  1. Dashboard → catálogo para org {org_id}")
        print("  2. Upload KB (Data Lake)")
        print("  3. WhatsApp fields em organizations (WHATSAPP_SETUP.md)")
        print("  4. Smoke manual + smoke_hybrid_prod.py")
        print("  5. LGPD: PRIVACY_CONTACT_EMAIL, PRIVACY_POLICY_URL — docs/legal/LGPD_ONBOARDING_CHECKLIST.md")
        return 0
    except subprocess.CalledProcessError:
        print("ERRO ao criar usuário — verifique saída acima")
        return 1
    except Exception as exc:
        print(f"ERRO: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
