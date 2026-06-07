"""Read-only pre-flight check for pending Jun/2026 migrations."""
import json
import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    db_url = os.environ.get("SUPABASE_DB_URL", "").strip()
    if not db_url:
        print("FAIL: SUPABASE_DB_URL not set")
        return 1

    conn = psycopg2.connect(db_url, connect_timeout=15)
    cur = conn.cursor()

    cur.execute("SELECT current_database(), current_user")
    db, user = cur.fetchone()
    print(f"OK: connected database={db} user={user}")

    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='patients' "
        "AND column_name IN ('handoff_requested_at', 'handoff_reason')"
    )
    handoff_cols = sorted(r[0] for r in cur.fetchall())

    cur.execute(
        "SELECT conname FROM pg_constraint WHERE conname='appointments_no_overlap'"
    )
    overlap_constraint = cur.fetchone() is not None

    cur.execute("SELECT extname FROM pg_extension WHERE extname='btree_gist'")
    btree_gist = cur.fetchone() is not None

    cur.execute("SELECT to_regclass('public.webhook_message_dedup')")
    webhook_table = cur.fetchone()[0] is not None

    cur.execute(
        """
        SELECT count(*)
        FROM appointments a
        JOIN appointments b
          ON a.professional_id = b.professional_id
         AND a.id < b.id
         AND a.status NOT IN ('cancelled', 'no_show')
         AND b.status NOT IN ('cancelled', 'no_show')
         AND tstzrange(
               a.scheduled_at,
               a.scheduled_at + (a.duration_minutes * interval '1 minute'),
               '[)'
             )
             && tstzrange(
               b.scheduled_at,
               b.scheduled_at + (b.duration_minutes * interval '1 minute'),
               '[)'
             )
        """
    )
    overlap_count = cur.fetchone()[0]

    conflicts = []
    if overlap_count:
        cur.execute(
            """
            SELECT a.id, b.id, a.professional_id, a.scheduled_at, b.scheduled_at
            FROM appointments a
            JOIN appointments b
              ON a.professional_id = b.professional_id
             AND a.id < b.id
             AND a.status NOT IN ('cancelled', 'no_show')
             AND b.status NOT IN ('cancelled', 'no_show')
             AND tstzrange(
                   a.scheduled_at,
                   a.scheduled_at + (a.duration_minutes * interval '1 minute'),
                   '[)'
                 )
                 && tstzrange(
                   b.scheduled_at,
                   b.scheduled_at + (b.duration_minutes * interval '1 minute'),
                   '[)'
                 )
            LIMIT 10
            """
        )
        conflicts = [
            {
                "appointment_a": str(row[0]),
                "appointment_b": str(row[1]),
                "professional_id": str(row[2]),
                "scheduled_at_a": row[3].isoformat(),
                "scheduled_at_b": row[4].isoformat(),
            }
            for row in cur.fetchall()
        ]

    cur.execute("SELECT count(*) FROM appointments")
    total_appointments = cur.fetchone()[0]

    cur.close()
    conn.close()

    report = {
        "handoff_cols": handoff_cols,
        "handoff_ready": set(handoff_cols) == {"handoff_reason", "handoff_requested_at"},
        "overlap_constraint": overlap_constraint,
        "btree_gist": btree_gist,
        "webhook_dedup_table": webhook_table,
        "existing_overlaps": overlap_count,
        "overlap_conflicts_sample": conflicts,
        "total_appointments": total_appointments,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
