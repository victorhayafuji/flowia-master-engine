"""
Popula o Data Lake com documentos do salão (Bronze → Silver → Gold).

Uso:
  python scripts/seed_datalake.py
  python scripts/seed_datalake.py --ensure-org
  python scripts/seed_datalake.py --org 22222222-2222-2222-2222-222222222222
"""
import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def ensure_organization(org_meta: dict) -> None:
    """Garante que a organização existe no Supabase antes do ingest."""
    from packages.auth_core.database import db

    if not db.wait_for_ready(timeout=5):
        raise RuntimeError("Supabase indisponível para ensure_organization")

    existing = (
        db.client.table("organizations")
        .select("id")
        .eq("id", org_meta["id"])
        .execute()
    )
    if existing.data:
        return

    payload = {
        "id": org_meta["id"],
        "name": org_meta["name"],
        "slug": org_meta["slug"],
        "vertical": org_meta["vertical"],
        "is_active": True,
    }

    db.client.table("organizations").insert(payload).execute()
    print(f"  Organização criada: {org_meta['name']} ({org_meta['id']})")


async def run_pipeline(org_id: str, search_query: str, ensure_org: bool) -> None:
    from apps.salon.seeds.datalake_mocks import generate_documents
    from apps.salon.seeds.vertical_orgs import VERTICAL_ORGS
    from packages.lakehouse.service import DataLakeService, DuplicateDocumentError

    vertical = "salon"
    org_meta = VERTICAL_ORGS[vertical]
    if ensure_org and org_meta["id"] == org_id:
        await ensure_organization(org_meta)

    print(f"Gerando mocks para salão...")
    mock_files = generate_documents(vertical)

    service = DataLakeService()
    ingested = 0
    skipped = 0

    print(f"Ingerindo {len(mock_files)} documento(s) para org {org_id}...")
    for path in mock_files:
        try:
            doc_id = service.ingest_to_bronze(str(path), org_id=org_id)
            ingested += 1
            print(f"  Bronze: {path.name} -> {doc_id}")
        except DuplicateDocumentError:
            skipped += 1
            print(f"  Bronze: {path.name} -> ja existe (ignorado)")

    if ingested == 0 and skipped > 0:
        print("  Nenhum arquivo novo; reprocessando camadas pendentes...")

    print("Processando Silver (OCR)...")
    silver_count = await service.process_silver_layer(org_id=org_id)
    print(f"  {silver_count} documento(s) processados")

    print("Processando Gold (embeddings)...")
    gold_count = await service.process_gold_layer(org_id=org_id)
    print(f"  {gold_count} documento(s) vetorizados")

    status = service.get_pipeline_status(org_id=org_id)
    print("\nStatus do pipeline:")
    for key, value in status.items():
        print(f"  {key}: {value}")

    if status.get("gold_vectors", 0) > 0:
        results = service.search_knowledge(search_query, org_id=org_id)
        print(f"\nBusca de teste ('{search_query}') retornou {len(results)} resultado(s)")
        for hit in results[:2]:
            snippet = (hit.get("content") or "")[:140]
            print(f"  - similarity={hit.get('similarity', 0):.3f}: {snippet}...")


def main() -> int:
    from apps.salon.seeds.vertical_orgs import VERTICAL_ORGS

    meta = VERTICAL_ORGS["salon"]
    parser = argparse.ArgumentParser(description="Seed Data Lake — Salão Beauty Express")
    parser.add_argument("--org", default=meta["id"], help="UUID da organização")
    parser.add_argument(
        "--ensure-org",
        action="store_true",
        help="Cria a organização no Supabase se não existir",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run_pipeline(args.org, meta["search_query"], args.ensure_org))
        print("\nData Lake populado com sucesso.")
        return 0
    except Exception as e:
        print(f"Erro ao popular Data Lake: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
