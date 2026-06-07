"""
Reindexa a camada Gold para documentos Silver ja processados.

Uso:
  python scripts/reindex_datalake.py
  python scripts/reindex_datalake.py --org 11111111-1111-1111-1111-111111111111
"""
import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ORG = "11111111-1111-1111-1111-111111111111"


async def reindex(org_id: str) -> None:
    from packages.lakehouse.service import DataLakeService

    service = DataLakeService()
    query = (
        service.supabase.table("docs_silver")
        .select("id")
        .eq("status", "COMPLETED")
        .eq("organization_id", org_id)
    )
    silver_docs = query.execute().data or []

    if not silver_docs:
        print(f"Nenhum documento Silver COMPLETED para org {org_id}.")
        return

    print(f"Reindexando {len(silver_docs)} documento(s) Silver...")
    for doc in silver_docs:
        silver_id = doc["id"]
        service.supabase.table("docs_gold_vectors").delete().eq("silver_id", silver_id).execute()
        service.supabase.table("docs_silver").update({"status": "SILVER_READY"}).eq("id", silver_id).execute()
        print(f"  Reset: {silver_id}")

    gold_count = await service.process_gold_layer(org_id=org_id)
    status = service.get_pipeline_status(org_id=org_id)
    print(f"\nGold reprocessado: {gold_count} documento(s)")
    print(f"Total vetores: {status.get('gold_vectors', 0)}")

    hits = service.search_knowledge("precos plano enterprise", org_id=org_id)
    print(f"Busca de teste: {len(hits)} resultado(s)")
    for hit in hits[:3]:
        snippet = (hit.get("content") or "")[:120]
        sim = hit.get("similarity", 0)
        print(f"  - {sim:.2f}: {snippet}...")


def main() -> int:
    parser = argparse.ArgumentParser(description="Reindexa camada Gold do Data Lake")
    parser.add_argument("--org", default=DEFAULT_ORG, help="UUID da organizacao")
    args = parser.parse_args()

    try:
        asyncio.run(reindex(args.org))
        print("\nReindexacao concluida.")
        return 0
    except Exception as e:
        print(f"Erro na reindexacao: {e}")
        return 1


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    sys.exit(main())
