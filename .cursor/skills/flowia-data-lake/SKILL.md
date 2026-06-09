---
name: flowia-data-lake
description: Guides Bronze→Silver→Gold pipeline, OCR semaphore, governance SQL guardrails, and RAG search in packages/lakehouse. Use when working on DataLake dashboard, docs_bronze/silver/gold, embeddings, or data-lake.md.
disable-model-invocation: true
---

# FlowIA Data Lake

Pipeline Medallion em `packages/lakehouse/`. Doc: `docs/data-lake.md`.

## Camadas

| Camada | Storage | Status |
|--------|---------|--------|
| Bronze | Supabase Storage `bronze_raw` + `docs_bronze` | PENDING → PROCESSING |
| Silver | `docs_silver` (texto OCR) | SILVER_READY |
| Gold | `docs_gold_vectors` (pgvector) | pronto para RAG |

## Fluxo

1. Upload: `POST /api/v1/lakehouse/upload` (max 10MB)
2. Background: OCR via OpenAI Vision (`VISION_MODEL_NAME`, default `gpt-4o`) com semáforo async (`service.py`)
3. Chunking + embeddings (`EMBEDDING_MODEL_NAME`, default `text-embedding-3-small`) → pgvector
4. Sync pendentes: `POST /api/v1/lakehouse/sync`
5. Busca RAG: `POST /api/v1/lakehouse/search`

## API endpoints

Registrados em `packages/lakehouse/router.py`: upload, sync, status, search, governance query.

## Governance

`packages/lakehouse/governance.py`:

- `ACTIVE_DICTIONARY` — schema metadata para queries seguras
- SQL guardrails: bloquear DDL/DML destrutivo
- PII masking em resultados

## Dashboard

UI: `apps/salon/dashboard/src/features/admin/DataLake.tsx` (`/admin/data-lake`, dev + super_admin).

## Dev seeds

```bash
python scripts/seed_dev.py
```

Org referência: `apps/salon/seeds/vertical_orgs.py` (ex: Beauty Express `22222222-...`).

Migration: `supabase/migrations/20260605000000_phase4_data_lake.sql` — requer extensão pgvector.

## Padrões de código

- OCR concorrente limitado por `asyncio.Semaphore` — não remover
- Reprocessamento: registros `PENDING`/`ERROR` reprocessáveis via sync
- Toda operação com `organization_id` do tenant atual
