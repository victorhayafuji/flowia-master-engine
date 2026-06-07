# Pacote → Responsabilidade

| Pacote | Responsabilidade |
|--------|------------------|
| `packages/models` | Enums, DTOs compartilhados |
| `packages/auth_core` | Config, DB, tenant, JWT, limiter |
| `packages/scheduling` | Agenda, tools de booking |
| `packages/lakehouse` | Pipeline Bronze→Gold, RAG |
| `packages/engine` | LangGraph, métricas, chat test, checkpointer |
| `packages/integrations` | WhatsApp webhook + outbound |
| `apps/salon/domain` | Catálogo e clientes (produto) |
| `apps/salon/api` | Composition root `create_salon_app()` |

## HTTP routers (`/api/v1`)

| Router | Pacote |
|--------|--------|
| auth | `packages/auth_core` |
| webhook | `packages/integrations` |
| chat, metrics | `packages/engine` |
| lakehouse | `packages/lakehouse` |
| scheduling | `packages/scheduling` |
| patients, organizations | `apps/salon/domain` |
| dashboard | `apps/salon/api/routers` |

Fonte: `docs/PACKAGE_BOUNDARIES.md`, `docs/ARCHITECTURE.md`.
