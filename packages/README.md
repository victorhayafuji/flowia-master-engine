# Packages — motor compartilhado

Pacotes compartilhados entre `apps/salon` e `apps/clinic`.

Mapa completo: [`CLAUDE.md`](../CLAUDE.md) §10 · Boundaries: [`docs/PACKAGE_BOUNDARIES.md`](../docs/PACKAGE_BOUNDARIES.md)

| Pasta | Responsabilidade |
|-------|------------------|
| `models/` | Enums, DTOs compartilhados |
| `auth_core/` | Config, DB, JWT, tenant, limiter |
| `scheduling/` | Agenda, tools de booking |
| `lakehouse/` | Pipeline Bronze→Gold, OCR (`gpt-4o`), RAG (`text-embedding-3-small`) |
| `engine/` | LangGraph, chat (`gpt-4o-mini`), métricas, checkpointer |
| `integrations/` | Webhook WhatsApp, outbound Meta |

**Proibido:** `packages/*` importar de `apps/salon`.
