"""Pre-check duplicate whatsapp_phone_id before applying unique migration."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from packages.auth_core.database import db


def main() -> int:
    if not db.client:
        print("Database unavailable", file=sys.stderr)
        return 1

    rows = (
        db.client.table("organizations")
        .select("id, name, whatsapp_phone_id")
        .neq("whatsapp_phone_id", "")
        .execute()
        .data
        or []
    )
    by_phone: dict[str, list[dict]] = {}
    for row in rows:
        phone = (row.get("whatsapp_phone_id") or "").strip()
        if not phone:
            continue
        by_phone.setdefault(phone, []).append(row)

    duplicates = {phone: orgs for phone, orgs in by_phone.items() if len(orgs) > 1}
    if not duplicates:
        print("OK: no duplicate whatsapp_phone_id values")
        return 0

    print("Duplicate whatsapp_phone_id detected:")
    for phone, orgs in duplicates.items():
        print(f"  {phone}:")
        for org in orgs:
            print(f"    - {org.get('name')} ({org.get('id')})")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
