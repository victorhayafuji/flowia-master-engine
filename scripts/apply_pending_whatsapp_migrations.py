"""Apply pending local migration files not yet on Supabase (dev/staging ops)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

PENDING = (
    "20260611000000_whatsapp_phone_id_unique.sql",
    "20260611010000_whatsapp_inbound_jobs.sql",
)


def main() -> int:
    from packages.auth_core.config import settings

    if not settings.SUPABASE_DB_URL:
        print("SUPABASE_DB_URL não configurado", file=sys.stderr)
        return 1

    import psycopg

    migrations_dir = ROOT / "supabase" / "migrations"
    try:
        with psycopg.connect(settings.SUPABASE_DB_URL, autocommit=True, connect_timeout=15) as conn:
            with conn.cursor() as cur:
                for name in PENDING:
                    path = migrations_dir / name
                    if not path.exists():
                        print(f"SKIP missing file: {name}")
                        continue
                    sql = path.read_text(encoding="utf-8")
                    print(f"Applying {name} ...")
                    cur.execute(sql)
                    print(f"OK {name}")
    except Exception as exc:
        print(f"Falha ao conectar/aplicar: {exc}", file=sys.stderr)
        print("Alternativa: Supabase Dashboard → SQL Editor → colar os arquivos em supabase/migrations/", file=sys.stderr)
        return 1

    print("Done. Valide com: py scripts/check_whatsapp_phone_duplicates.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
