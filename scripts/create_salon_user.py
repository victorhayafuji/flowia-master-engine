"""
Cria usuário do salão (org_admin ou professional) para teste de RLS / multi-tenant.

Uso:
  python scripts/create_salon_user.py --email dono@beauty-express.com --password "SenhaForte1!"
  python scripts/create_salon_user.py --email dono@beauty-express.com --password "SenhaForte1!" --org 22222222-2222-2222-2222-222222222222
  python scripts/create_salon_user.py --email joao@beauty-express.com --password "SenhaForte1!" --role professional --professional-id <uuid>
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
    parser = argparse.ArgumentParser(description="Cria login (org_admin | professional) para um salão")
    parser.add_argument("--email", default=os.getenv("DEV_SALON_EMAIL", "dono@beauty-express.com"))
    parser.add_argument(
        "--password",
        default=os.getenv("DEV_SALON_PASSWORD") or os.getenv("DEV_ADMIN_PASSWORD"),
    )
    parser.add_argument("--org", default=os.getenv("DEV_SALON_ORG_ID", SALON_ORG_ID))
    parser.add_argument("--role", default="org_admin", choices=["org_admin", "professional"])
    parser.add_argument(
        "--professional-id",
        dest="professional_id",
        default=None,
        help="UUID do profissional vinculado (obrigatório quando --role professional)",
    )
    args = parser.parse_args()

    if not args.password:
        print("ERRO: informe --password ou defina DEV_SALON_PASSWORD / DEV_ADMIN_PASSWORD no .env")
        return 1

    if args.role == "professional" and not args.professional_id:
        print("ERRO: --role professional exige --professional-id <uuid> (profissional do catálogo)")
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

    if args.professional_id:
        prof_res = (
            supabase.table("professionals")
            .select("id, name, organization_id")
            .eq("id", args.professional_id)
            .limit(1)
            .execute()
        )
        if not prof_res.data:
            print(f"ERRO: profissional {args.professional_id} não encontrado.")
            return 1
        if prof_res.data[0]["organization_id"] != args.org:
            print("ERRO: o profissional pertence a outra organização.")
            return 1

    existing = (
        supabase.table("dashboard_users")
        .select("id, email, role, organization_id")
        .eq("email", args.email)
        .limit(1)
        .execute()
    )

    row = {
        "role": args.role,
        "organization_id": args.org,
        "professional_id": args.professional_id,
    }

    try:
        if existing.data:
            user_id = existing.data[0]["id"]
            supabase.auth.admin.update_user_by_id(user_id, {"password": args.password})
            supabase.table("dashboard_users").update(row).eq("id", user_id).execute()
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
            supabase.table("dashboard_users").insert({"id": auth_res.user.id, "email": args.email, **row}).execute()
            print(f"OK: usuário criado — {args.email}")
    except Exception as e:
        print(f"ERRO: {e}")
        return 1

    print(f"     Papel: {args.role}")
    print(f"     Salão: {org_name} ({args.org})")
    if args.professional_id:
        print(f"     Profissional vinculado: {args.professional_id}")
    print()
    print("Teste no dashboard: login manual com esse e-mail/senha.")
    if args.role == "professional":
        print("Profissional vê apenas Visão Geral + Agenda (somente seus agendamentos).")
    else:
        print("O seletor 'Salão ativo' NÃO deve aparecer (só super_admin com 2+ orgs).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
