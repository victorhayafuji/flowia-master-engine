"""
Smoke test do RAG no chatbot (search_kb + opcional API).

Uso:
  python scripts/test_rag_chat.py
  python scripts/test_rag_chat.py --org 22222222-2222-2222-2222-222222222222
"""
import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ORG = "22222222-2222-2222-2222-222222222222"

SMOKE_QUERIES = [
    "quanto custa corte feminino",
    "politica de cancelamento",
    "quero agendar manicure",
]

PRICE_MARKERS = ("R$ 120", "R$ 80", "R$ 45", "corte", "manicure")


def smoke_search(org_id: str) -> int:
    from packages.lakehouse.service import DataLakeService
    from packages.auth_core.tenant import set_tenant_context

    service = DataLakeService()
    passed = 0

    print(f"Smoke RAG (org={org_id})\n")
    with set_tenant_context(org_id):
        for query in SMOKE_QUERIES:
            hits = service.search_knowledge(query, org_id=org_id, match_threshold=0.3, match_count=3)
            print(f"Query: {query!r}")
            print(f"  hits: {len(hits)}")
            if hits:
                top = hits[0].get("content", "")[:120]
                sim = hits[0].get("similarity", 0)
                print(f"  top ({sim:.2f}): {top}...")
            found_price = any(
                marker.lower() in (h.get("content") or "").lower()
                for h in hits
                for marker in PRICE_MARKERS
            )
            if query.startswith("preco") or "enterprise" in query or "custa" in query:
                if found_price or (hits and "plano" in hits[0].get("content", "").lower()):
                    passed += 1
                    print("  OK: conteudo relevante")
                else:
                    print("  WARN: sem precos nos resultados")
            else:
                passed += 1 if hits else 0
                print("  OK" if hits else "  WARN: sem resultados")
            print()

    print(f"Queries com resultado relevante: {passed}/{len(SMOKE_QUERIES)}")
    return 0 if passed >= 2 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test RAG chatbot")
    parser.add_argument("--org", default=DEFAULT_ORG, help="UUID da organizacao")
    args = parser.parse_args()

    try:
        return smoke_search(args.org)
    except Exception as e:
        print(f"Erro: {e}")
        return 1


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    sys.exit(main())
