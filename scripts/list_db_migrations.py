"""List migration versions recorded in Supabase DB."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    load_dotenv(ROOT / ".env")
    url = os.getenv("SUPABASE_DB_URL", "").strip()
    if not url:
        print("ERRO: SUPABASE_DB_URL ausente")
        return 1

    with psycopg.connect(url) as conn:
        try:
            rows = conn.execute(
                "SELECT version, name FROM supabase_migrations.schema_migrations ORDER BY version"
            ).fetchall()
        except Exception as exc:
            print(f"schema_migrations indisponível: {exc}")
            return 1

    for version, name in rows:
        print(f"{version}\t{name}")
    print(f"\nTotal: {len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
