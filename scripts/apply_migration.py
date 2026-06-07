"""Apply a single SQL migration file to Supabase via SUPABASE_DB_URL."""
import argparse
import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a Supabase migration SQL file")
    parser.add_argument("migration", help="Path to .sql migration file")
    args = parser.parse_args()

    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("SUPABASE_DB_URL não configurado no .env")
        return 1

    if not os.path.exists(args.migration):
        print(f"Arquivo não encontrado: {args.migration}")
        return 1

    with open(args.migration, encoding="utf-8") as f:
        sql = f.read()

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        print(f"Aplicando {args.migration}...")
        cur.execute(sql)
        conn.commit()
        cur.close()
        conn.close()
        print("Migration aplicada com sucesso.")
        return 0
    except Exception as e:
        print(f"Erro: {e}")
        if "conn" in locals():
            conn.rollback()
        return 1


if __name__ == "__main__":
    sys.exit(main())
