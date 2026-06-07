"""Syncs VITE_* frontend vars from backend Supabase settings in .env."""
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
    if not ENV_FILE.exists():
        print(f"ERRO: {ENV_FILE} não encontrado.")
        return 1

    load_dotenv(ENV_FILE)
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").strip()

    if not supabase_url or not supabase_key:
        print("ERRO: SUPABASE_URL e SUPABASE_KEY são obrigatórios no .env")
        return 1

    content = ENV_FILE.read_text(encoding="utf-8")
    if "# --- Frontend (Vite)" not in content:
        content += "\n# --- Frontend (Vite) ---\n"

    content = _upsert_env_var(content, "VITE_SUPABASE_URL", supabase_url)
    content = _upsert_env_var(content, "VITE_SUPABASE_KEY", supabase_key)
    content = _upsert_env_var(content, "VITE_API_URL", "http://localhost:8000/api/v1")

    ENV_FILE.write_text(content, encoding="utf-8")
    print("OK: VITE_SUPABASE_URL, VITE_SUPABASE_KEY e VITE_API_URL sincronizados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
