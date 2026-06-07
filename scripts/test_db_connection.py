"""Testa conexão direta ao PostgreSQL via SUPABASE_DB_URL."""
import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    db_url = os.environ.get("SUPABASE_DB_URL", "").strip()
    if not db_url:
        print("FAIL: SUPABASE_DB_URL não configurado no .env")
        return 1

    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
        cur = conn.cursor()
        cur.execute("SELECT current_database(), current_user")
        database, user = cur.fetchone()
        cur.execute("SELECT COUNT(*) FROM organizations")
        org_count = cur.fetchone()[0]
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='docs_bronze' ORDER BY ordinal_position"
        )
        cols = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()

        print("OK: conexão PostgreSQL estabelecida")
        print(f"  database={database}")
        print(f"  user={user}")
        print(f"  organizations={org_count} registros")
        print(f"  docs_bronze colunas={cols}")
        return 0
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
