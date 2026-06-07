"""
Preenche content_hash dos documentos Bronze existentes (download do Storage).

Uso:
  python scripts/backfill_bronze_hashes.py
  python scripts/backfill_bronze_hashes.py --org UUID
"""
import argparse
import hashlib
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
BRONZE_BUCKET = "bronze_raw"


def backfill(org_id: str | None) -> int:
    from packages.lakehouse.service import DataLakeService

    service = DataLakeService()
    query = (
        service.supabase.table("docs_bronze")
        .select("id, storage_path, content_hash, file_name")
        .is_("content_hash", "null")
    )
    if org_id:
        query = query.eq("organization_id", org_id)

    rows = query.execute().data or []
    if not rows:
        print("Nenhum bronze sem content_hash.")
        return 0

    print(f"Preenchendo hash de {len(rows)} documento(s)...")
    for row in rows:
        path = row.get("storage_path")
        if not path:
            continue
        try:
            data = service.supabase.storage.from_(BRONZE_BUCKET).download(path)
            content_hash = hashlib.sha256(data).hexdigest()
            service.supabase.table("docs_bronze").update(
                {"content_hash": content_hash}
            ).eq("id", row["id"]).execute()
            print(f"  OK: {row['file_name']}")
        except Exception as e:
            print(f"  SKIP {row['file_name']}: {e}")

    print("Backfill concluido.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill content_hash em docs_bronze")
    parser.add_argument("--org", default=None, help="Filtrar por organization_id")
    args = parser.parse_args()
    try:
        return backfill(args.org)
    except Exception as e:
        print(f"Erro: {e}")
        return 1


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    sys.exit(main())
