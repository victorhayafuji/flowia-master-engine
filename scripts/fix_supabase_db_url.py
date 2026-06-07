"""Alinha SUPABASE_DB_URL ao mesmo project_ref de SUPABASE_URL."""
import os
import re
import sys
from urllib.parse import quote, urlparse, urlunparse

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(ROOT, ".env")


def project_ref_from_supabase_url(url: str) -> str:
    host = urlparse(url).hostname or ""
    return host.replace(".supabase.co", "")


def rebuild_db_url(api_url: str, current_db_url: str) -> str:
    ref = project_ref_from_supabase_url(api_url)
    parsed = urlparse(current_db_url)
    if not parsed.password:
        raise ValueError("SUPABASE_DB_URL sem senha configurada")
    new_host = f"db.{ref}.supabase.co"
    netloc = f"{parsed.username}:{quote(parsed.password, safe='')}@{new_host}:{parsed.port or 5432}"
    return urlunparse((parsed.scheme, netloc, parsed.path or "/postgres", "", "", ""))


def main() -> int:
    load_dotenv(ENV_FILE)
    api_url = os.environ.get("SUPABASE_URL", "").strip()
    db_url = os.environ.get("SUPABASE_DB_URL", "").strip()

    if not api_url or not db_url:
        print("SUPABASE_URL e SUPABASE_DB_URL são obrigatórios.")
        return 1

    api_ref = project_ref_from_supabase_url(api_url)
    db_ref = project_ref_from_supabase_url(db_url).replace("db.", "")

    if api_ref == db_ref:
        print(f"SUPABASE_DB_URL já aponta para {api_ref}.")
        return 0

    fixed = rebuild_db_url(api_url, db_url)
    content = open(ENV_FILE, encoding="utf-8").read()
    content = re.sub(
        r'^SUPABASE_DB_URL=.*$',
        f'SUPABASE_DB_URL="{fixed}"',
        content,
        flags=re.MULTILINE,
    )
    open(ENV_FILE, "w", encoding="utf-8").write(content)
    print(f"SUPABASE_DB_URL atualizado: {db_ref} -> {api_ref}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
