"""
Remove documentos Bronze duplicados (mesmo org + file_name + file_size).

Uso:
  python scripts/cleanup_datalake_duplicates.py              # dry-run (default)
  python scripts/cleanup_datalake_duplicates.py --apply
  python scripts/cleanup_datalake_duplicates.py --org UUID --apply
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
BRONZE_BUCKET = "bronze_raw"
def _pick_keep(docs: list[dict]) -> dict:
    completed = [d for d in docs if d.get("status") == "COMPLETED"]
    pool = completed if completed else docs
    return max(pool, key=lambda d: d.get("created_at") or "")


def cleanup(org_id: str | None, apply: bool) -> int:
    from packages.lakehouse.service import DataLakeService

    service = DataLakeService()
    query = service.supabase.table("docs_bronze").select(
        "id, organization_id, file_name, file_size, status, storage_path, created_at"
    )
    if org_id:
        query = query.eq("organization_id", org_id)

    rows = query.execute().data or []
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        key = (row["organization_id"], row["file_name"], row.get("file_size"))
        groups[key].append(row)

    to_remove: list[dict] = []
    for key, docs in groups.items():
        if len(docs) <= 1:
            continue
        keep = _pick_keep(docs)
        for doc in docs:
            if doc["id"] != keep["id"]:
                to_remove.append(doc)

    if not to_remove:
        print("Nenhuma duplicata encontrada.")
    else:
        print(f"{'APLICANDO' if apply else 'DRY-RUN'}: {len(to_remove)} documento(s) a remover:")
        for doc in to_remove:
            print(
                f"  - {doc['file_name']} ({doc['status']}) "
                f"id={doc['id'][:8]}... size={doc.get('file_size')}"
            )

    if apply:
        for doc in to_remove:
            path = doc.get("storage_path")
            if path:
                try:
                    service.supabase.storage.from_(BRONZE_BUCKET).remove([path])
                except Exception as e:
                    print(f"  aviso storage {path}: {e}")
            service.supabase.table("docs_bronze").delete().eq("id", doc["id"]).execute()

    status = service.get_pipeline_status(org_id)
    print("\nContadores atuais:")
    print(f"  bronze_completed={status['bronze_completed']} bronze_error={status['bronze_error']}")
    print(f"  silver_completed={status['silver_completed']} gold_vectors={status['gold_vectors']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove duplicatas do Data Lake Bronze")
    parser.add_argument("--org", default=None, help="Filtrar por organization_id")
    parser.add_argument("--apply", action="store_true", help="Executar remocao (default: dry-run)")
    args = parser.parse_args()

    try:
        return cleanup(args.org, args.apply)
    except Exception as e:
        print(f"Erro: {e}")
        return 1


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    sys.exit(main())
