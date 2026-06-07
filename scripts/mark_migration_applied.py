"""Mark a migration as applied without running SQL."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: python scripts/mark_migration_applied.py <migration_stem>")
        return 1

    name = sys.argv[1].removesuffix(".sql")
    load_dotenv(ROOT / ".env")
    url = os.getenv("SUPABASE_DB_URL", "").strip()
    if not url:
        print("ERRO: SUPABASE_DB_URL ausente")
        return 1

    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(
            """
            INSERT INTO supabase_migrations.schema_migrations (version, name)
            VALUES (%s, %s)
            ON CONFLICT (version) DO NOTHING
            """,
            (name, name),
        )
    print(f"Marcada: {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
