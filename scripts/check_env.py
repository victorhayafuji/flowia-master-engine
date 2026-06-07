"""Validates that required environment variables are present (never prints secret values)."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

REQUIRED = [
    "GOOGLE_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "SUPABASE_SERVICE_ROLE",
    "SUPABASE_DB_URL",
    "WHATSAPP_VERIFY_TOKEN",
    "DASHBOARD_API_KEY",
    "DASHBOARD_JWT_SECRET",
    "VITE_SUPABASE_URL",
    "VITE_SUPABASE_KEY",
    "VITE_API_URL",
]

DEV_OPTIONAL = [
    "VITE_DEV_EMAIL",
    "VITE_DEV_PASSWORD",
]


def _is_set(name: str) -> bool:
    value = os.getenv(name, "").strip()
    if not value:
        return False
    placeholders = ("your_", "seu_", "sua_", "REPLACE", "changeme")
    return not any(value.lower().startswith(p) for p in placeholders)


def main() -> int:
    missing = [k for k in REQUIRED if not _is_set(k)]
    dev_missing = [k for k in DEV_OPTIONAL if not _is_set(k)]

    if missing:
        print("ERRO: variáveis obrigatórias ausentes ou com placeholder:")
        for key in missing:
            print(f"  - {key}")
        return 1

    print("OK: todas as variáveis obrigatórias estão definidas.")

    if dev_missing:
        print("\nAVISO: modo desenvolvedor no login não funcionará até configurar:")
        for key in dev_missing:
            print(f"  - {key}")
        print("Execute: python scripts/setup_dev_env.py --email SEU_EMAIL --password SUA_SENHA")
        return 0

    print("OK: VITE_DEV_EMAIL e VITE_DEV_PASSWORD configurados (dev login).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
