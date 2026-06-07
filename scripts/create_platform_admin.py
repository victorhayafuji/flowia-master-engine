"""
Cria usuário super_admin da plataforma (cross-tenant).

Uso:
  python scripts/create_platform_admin.py --email admin@flowia.com --password "SenhaForte2!"
"""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cria login super_admin plataforma")
    parser.add_argument("--email", default=os.getenv("DEV_ADMIN_EMAIL", "admin@flowia.com"))
    parser.add_argument(
        "--password",
        default=os.getenv("DEV_ADMIN_PASSWORD"),
    )
    args = parser.parse_args()

    if not args.password:
        print("ERRO: informe --password ou defina DEV_ADMIN_PASSWORD no .env")
        return 1

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE")
    if not url or not key:
        print("ERRO: SUPABASE_URL e SUPABASE_SERVICE_ROLE são obrigatórios no .env")
        return 1

    from supabase import create_client

    supabase = create_client(url, key)
    existing = (
        supabase.table("dashboard_users")
        .select("id, email, role")
        .eq("email", args.email)
        .limit(1)
        .execute()
    )

    def _auth_user_id() -> str | None:
        page = 1
        while True:
            batch = supabase.auth.admin.list_users(page=page, per_page=200)
            users = batch if isinstance(batch, list) else getattr(batch, "users", []) or []
            if not users:
                return None
            for user in users:
                email = getattr(user, "email", None) or user.get("email")
                uid = getattr(user, "id", None) or user.get("id")
                if email == args.email and uid:
                    return str(uid)
            if len(users) < 200:
                return None
            page += 1

    try:
        auth_id = _auth_user_id()
        if auth_id:
            supabase.auth.admin.update_user_by_id(auth_id, {"password": args.password})
            supabase.table("dashboard_users").delete().eq("email", args.email).execute()
            supabase.table("dashboard_users").insert({
                "id": auth_id,
                "email": args.email,
                "role": "super_admin",
                "organization_id": None,
            }).execute()
            print(f"OK: super_admin sincronizado — {args.email}")
            return 0

        if existing.data:
            user_id = existing.data[0]["id"]
            try:
                supabase.auth.admin.update_user_by_id(user_id, {"password": args.password})
            except Exception:
                supabase.table("dashboard_users").delete().eq("email", args.email).execute()
                auth_res = supabase.auth.admin.create_user({
                    "email": args.email,
                    "password": args.password,
                    "email_confirm": True,
                })
                if not auth_res.user:
                    print("ERRO: falha ao recriar usuário no Supabase Auth")
                    return 1
                user_id = auth_res.user.id
                supabase.table("dashboard_users").insert({
                    "id": user_id,
                    "email": args.email,
                    "role": "super_admin",
                    "organization_id": None,
                }).execute()
                print(f"OK: super_admin recriado — {args.email}")
                return 0
            supabase.table("dashboard_users").update({
                "role": "super_admin",
                "organization_id": None,
            }).eq("id", user_id).execute()
            print(f"OK: super_admin atualizado — {args.email}")
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
                "role": "super_admin",
                "organization_id": None,
            }).execute()
            print(f"OK: super_admin criado — {args.email}")
    except Exception as exc:
        print(f"ERRO: {exc}")
        return 1

    print("     Papel: super_admin (sem organization_id)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
