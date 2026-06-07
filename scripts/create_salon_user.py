"""
Cria usuário org_admin vinculado a um salão (teste de RLS / multi-tenant).

Uso:
  python scripts/create_salon_user.py --email dono@beauty-express.com --password "SenhaForte1!"
  python scripts/create_salon_user.py --email dono@beauty-express.com --password "SenhaForte1!" --org 22222222-2222-2222-2222-222222222222
"""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from apps.salon.seeds.vertical_orgs import SALON_ORG_ID  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Cria login org_admin para um salão")
    parser.add_argument("--email", default=os.getenv("DEV_SALON_EMAIL", "dono@beauty-express.com"))
    parser.add_argument(
        "--password",
        default=os.getenv("DEV_SALON_PASSWORD") or os.getenv("DEV_ADMIN_PASSWORD"),
    )
    parser.add_argument("--org", default=os.getenv("DEV_SALON_ORG_ID", SALON_ORG_ID))
    args = parser.parse_args()

    if not args.password:
        print("ERRO: informe --password ou defina DEV_SALON_PASSWORD / DEV_ADMIN_PASSWORD no .env")
        return 1

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE")
    if not url or not key:
        print("ERRO: SUPABASE_URL e SUPABASE_SERVICE_ROLE são obrigatórios no .env")
        return 1

    from supabase import create_client

    supabase = create_client(url, key)

    org_res = supabase.table("organizations").select("id, name").eq("id", args.org).limit(1).execute()
    if not org_res.data:
        print(f"ERRO: organização {args.org} não encontrada. Rode: python scripts/seed_salon.py")
        return 1

    org_name = org_res.data[0]["name"]
    existing = (
        supabase.table("dashboard_users")
        .select("id, email, role, organization_id")
        .eq("email", args.email)
        .limit(1)
        .execute()
    )

    try:
        if existing.data:
            user_id = existing.data[0]["id"]
            supabase.auth.admin.update_user_by_id(user_id, {"password": args.password})
            supabase.table("dashboard_users").update({
                "role": "org_admin",
                "organization_id": args.org,
            }).eq("id", user_id).execute()
            print(f"OK: usuário atualizado — {args.email}")
        else:
            auth_res = supabase.auth.admin.create_user({
                "email": args.email,
                "password": args.password,
                "email_confirm": True,
            })
            if not auth_res.user:
                print("ERRO: falha ao criar usuário no Supabase Auth")
                return 1
            supabase.table("dashboard_users").insert({
                "id": auth_res.user.id,
                "email": args.email,
                "role": "org_admin",
                "organization_id": args.org,
            }).execute()
            print(f"OK: usuário criado — {args.email}")
    except Exception as e:
        print(f"ERRO: {e}")
        return 1

    print(f"     Papel: org_admin")
    print(f"     Salão: {org_name} ({args.org})")
    print()
    print("Teste no dashboard: login manual com esse e-mail/senha.")
    print("O seletor 'Salão ativo' NÃO deve aparecer (só super_admin com 2+ orgs).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
