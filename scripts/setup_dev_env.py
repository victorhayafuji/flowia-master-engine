"""Adds or updates VITE_DEV_* vars in root .env for local dev login button."""
import argparse
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"


def _upsert_env_var(content: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    line = f'{key}="{value}"'
    if pattern.search(content):
        return pattern.sub(line, content)
    return content.rstrip() + f"\n{line}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure VITE_DEV_* in .env")
    parser.add_argument("--email", default=None, help="Dev super_admin email")
    parser.add_argument("--password", default=None, help="Dev super_admin password (Supabase Auth)")
    parser.add_argument("--salon-email", default=None, help="Dev org_admin (dono do salão) email")
    parser.add_argument("--salon-password", default=None, help="Dev org_admin password")
    args = parser.parse_args()

    load_dotenv(ENV_FILE)
    email = args.email or os.getenv("DEV_ADMIN_EMAIL", "admin@flowia.com")
    password = args.password or os.getenv("DEV_ADMIN_PASSWORD")

    if not password and ENV_FILE.exists():
        comment_match = re.search(
            r"^#\s*password\s*=\s*(.+?)\s*$",
            ENV_FILE.read_text(encoding="utf-8"),
            re.MULTILINE | re.IGNORECASE,
        )
        if comment_match:
            password = comment_match.group(1).strip()

    if not password:
        print("ERRO: informe --password, defina DEV_ADMIN_PASSWORD no .env,")
        print("      ou adicione um comentário: # password = sua_senha")
        return 1

    if not ENV_FILE.exists():
        print(f"ERRO: {ENV_FILE} não encontrado. Copie .env.example para .env primeiro.")
        return 1

    content = ENV_FILE.read_text(encoding="utf-8")
    if "# --- Dev-only login bypass" not in content:
        content += "\n# --- Dev-only login bypass (local development only) ---\n"

    content = _upsert_env_var(content, "VITE_DEV_EMAIL", email)
    content = _upsert_env_var(content, "VITE_DEV_PASSWORD", password)
    content = _upsert_env_var(content, "DEV_ADMIN_EMAIL", email)
    content = _upsert_env_var(content, "DEV_ADMIN_PASSWORD", password)

    salon_email = args.salon_email or os.getenv("DEV_SALON_EMAIL", "dono@beauty-express.com")
    salon_password = args.salon_password or os.getenv("DEV_SALON_PASSWORD")
    if salon_password:
        content = _upsert_env_var(content, "DEV_SALON_EMAIL", salon_email)
        content = _upsert_env_var(content, "DEV_SALON_PASSWORD", salon_password)
        content = _upsert_env_var(content, "VITE_DEV_SALON_EMAIL", salon_email)
        content = _upsert_env_var(content, "VITE_DEV_SALON_PASSWORD", salon_password)

    ENV_FILE.write_text(content, encoding="utf-8")
    print(f"OK: credenciais de dev atualizadas em {ENV_FILE}")
    if salon_password:
        print("     + login dono do salão (VITE_DEV_SALON_*)")
    print("Reinicie o frontend (npm run dev) para aplicar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
