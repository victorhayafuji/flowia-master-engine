"""Apply pending SQL migrations from supabase/migrations/ via direct Postgres connection.

Uses SUPABASE_DB_URL from .env (service role / postgres user).
Tracks applied migrations in supabase_migrations.schema_migrations when possible,
or idempotent SQL (IF NOT EXISTS) for re-runs.

Usage:
  venv\\Scripts\\python.exe scripts/apply_migrations.py
  venv\\Scripts\\python.exe scripts/apply_migrations.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"

# Order from CLAUDE.md §15
MIGRATION_FILES = [
    "20260531200000_multi_tenant_foundation.sql",
    "20260531210000_phase3_anamnesis.sql",
    "20260531220000_rls_jwt_support.sql",
    "20260602000000_auth_uid_rls.sql",
    "20260605000000_phase4_data_lake.sql",
    "20260606000000_bronze_content_hash.sql",
    "20260606010000_service_catalog_professional_id.sql",
    "20260607000000_patient_handoff.sql",
    "20260607010000_appointment_overlap_guard.sql",
    "20260607020000_webhook_message_dedup.sql",
    "20260608000000_internal_tables_rls.sql",
    "20260609000000_updated_at_triggers.sql",
    "20260609010000_soft_delete_and_integrity.sql",
    "20260610000000_professional_user_link.sql",
    "20260610010000_service_professionals.sql",
    "20260610020000_schedule_blocks.sql",
    "20260610030000_appointment_payments.sql",
    "20260610040000_conversation_metrics_observability.sql",
    "20260610050000_conversation_metrics_sender_text.sql",
]


def _get_db_url() -> str:
    load_dotenv(ROOT / ".env")
    import os

    url = os.getenv("SUPABASE_DB_URL", "").strip()
    if not url:
        print("ERRO: SUPABASE_DB_URL ausente no .env")
        sys.exit(1)
    return url


def _ensure_tracking(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE SCHEMA IF NOT EXISTS supabase_migrations;
        CREATE TABLE IF NOT EXISTS supabase_migrations.schema_migrations (
            version TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )


def _migration_name(filename: str) -> str:
    return Path(filename).stem


def _is_applied(conn: psycopg.Connection, filename: str) -> bool:
    name = _migration_name(filename)
    row = conn.execute(
        """
        SELECT 1 FROM supabase_migrations.schema_migrations
        WHERE name = %s OR version = %s
        """,
        (name, name),
    ).fetchone()
    return row is not None


def apply_migrations(dry_run: bool = False) -> int:
    db_url = _get_db_url()
    applied = 0
    skipped = 0

    with psycopg.connect(db_url, autocommit=False) as conn:
        _ensure_tracking(conn)
        conn.commit()

        for filename in MIGRATION_FILES:
            path = MIGRATIONS_DIR / filename
            if not path.exists():
                print(f"AVISO: arquivo ausente: {filename}")
                continue

            version = _migration_name(filename)
            if _is_applied(conn, filename):
                print(f"SKIP {filename} (já aplicada)")
                skipped += 1
                continue

            sql = path.read_text(encoding="utf-8")
            print(f"APPLY {filename}...")
            if dry_run:
                applied += 1
                continue

            try:
                conn.execute(sql)
                conn.execute(
                    """
                    INSERT INTO supabase_migrations.schema_migrations (version, name)
                    VALUES (%s, %s)
                    ON CONFLICT (version) DO NOTHING
                    """,
                    (version, version),
                )
                conn.commit()
                applied += 1
                print(f"  OK {filename}")
            except Exception as exc:
                conn.rollback()
                print(f"  ERRO {filename}: {exc}")
                return 1

    print(f"\nConcluído: {applied} aplicadas, {skipped} ignoradas.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="List migrations to apply")
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Mark all migration files as applied without executing (existing DB)",
    )
    args = parser.parse_args()
    if args.baseline:
        return baseline_migrations()
    return apply_migrations(dry_run=args.dry_run)


def baseline_migrations() -> int:
    """Mark repo migrations as applied when schema already exists (e.g. partial supabase db push)."""
    db_url = _get_db_url()
    with psycopg.connect(db_url, autocommit=False) as conn:
        _ensure_tracking(conn)
        for filename in MIGRATION_FILES:
            version = _migration_name(filename)
            conn.execute(
                """
                INSERT INTO supabase_migrations.schema_migrations (version, name)
                VALUES (%s, %s)
                ON CONFLICT (version) DO NOTHING
                """,
                (version, version),
            )
            print(f"BASELINE {filename}")
        conn.commit()
    print("Baseline concluído.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
