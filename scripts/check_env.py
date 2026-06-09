"""Validates that required environment variables are present (never prints secret values)."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

REQUIRED = [
    "OPENAI_API_KEY",
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


def _dotenv_only(name: str) -> str:
    """Value from .env file only (ignores process env overrides)."""
    from dotenv import dotenv_values

    return (dotenv_values(ROOT / ".env").get(name) or "").strip()


def _process_env(name: str) -> str:
    return os.getenv(name, "").strip()


def _is_placeholder(value: str) -> bool:
    if not value:
        return True
    lowered = value.lower()
    if lowered in {"test-key", "test-anon-key", "test-service-role", "test-dashboard-api-key"}:
        return True
    if "example.supabase.co" in lowered:
        return True
    placeholders = ("your_", "seu_", "sua_", "replace", "changeme", "test-jwt-secret")
    return any(lowered.startswith(p) for p in placeholders)


def _check_shell_overrides() -> list[str]:
    """Warn when pytest/CI placeholders in the shell override .env (Pydantic prefers process env)."""
    warnings: list[str] = []
    for key in (
        "OPENAI_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "SUPABASE_SERVICE_ROLE",
        "SUPABASE_DB_URL",
    ):
        file_val = _dotenv_only(key)
        proc_val = _process_env(key)
        if not file_val or not proc_val or proc_val == file_val:
            continue
        if _is_placeholder(proc_val):
            warnings.append(
                f"{key} no shell está com placeholder de CI/teste e sobrescreve o .env — "
                f"remova a variável ou abra um terminal novo antes de subir o uvicorn."
            )
        elif key == "OPENAI_API_KEY":
            warnings.append(
                f"{key} no shell difere do .env — o backend usará o valor do shell, não o arquivo."
            )
    return warnings


def main() -> int:
    missing = [k for k in REQUIRED if not _is_set(k)]
    dev_missing = [k for k in DEV_OPTIONAL if not _is_set(k)]
    override_warnings = _check_shell_overrides()

    if missing:
        print("ERRO: variáveis obrigatórias ausentes ou com placeholder:")
        for key in missing:
            print(f"  - {key}")
        return 1

    print("OK: todas as variáveis obrigatórias estão definidas.")

    if override_warnings:
        print("\nAVISO: variáveis de ambiente do shell sobrescrevem o .env:")
        for line in override_warnings:
            print(f"  - {line}")
        print(
            "\nPowerShell (antes de uvicorn): "
            "Remove-Item Env:OPENAI_API_KEY,Env:SUPABASE_URL,Env:SUPABASE_KEY,"
            "Env:SUPABASE_SERVICE_ROLE -ErrorAction SilentlyContinue"
        )

    if dev_missing:
        print("\nAVISO: modo desenvolvedor no login não funcionará até configurar:")
        for key in dev_missing:
            print(f"  - {key}")
        print("Execute: python scripts/setup_dev_env.py --email SEU_EMAIL --password SUA_SENHA")
        return 1 if override_warnings else 0

    if override_warnings:
        return 1

    print("OK: VITE_DEV_EMAIL e VITE_DEV_PASSWORD configurados (dev login).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
