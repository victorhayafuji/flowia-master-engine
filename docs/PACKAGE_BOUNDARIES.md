# Package boundaries — regras de dependência

## Grafo permitido

```
models        → (stdlib/pydantic only)
auth_core     → models
scheduling    → auth_core, models
lakehouse     → auth_core, models
engine        → auth_core, models, scheduling, lakehouse
integrations  → engine, auth_core
apps/salon    → engine, scheduling, lakehouse, auth_core (injeta prompts)
```

**Proibido:** `packages/*` importar de `apps/salon`.

## Mapa de pacotes

| Pacote | Responsabilidade |
|--------|------------------|
| `packages/models` | Enums, DTOs compartilhados |
| `packages/auth_core` | Config, DB, tenant, JWT, limiter |
| `packages/scheduling` | Agenda, tools de booking, date parsing, booking executor |
| `packages/lakehouse` | Pipeline Bronze→Gold, RAG |
| `packages/engine` | LangGraph, métricas, chat test, checkpointer |
| `packages/integrations` | WhatsApp webhook + outbound |
| `apps/salon/domain` | Catálogo e clientes (produto) |
| `apps/salon/api` | Composition root `create_salon_app()` |

## Subpacotes internos (facades preservam imports externos)

| Path | Módulos | Facade / entry |
|------|---------|----------------|
| `packages/scheduling/date_parsing/` | `types`, `normalize`, `calendar`, `helpers`, `relative`, `weekday`, `resolve` | Import via `packages.scheduling.date_parsing` |
| `packages/scheduling/services/` | `config_helpers`, `availability`, `appointments` | `packages/scheduling/service.py` → `SchedulingService` |
| `packages/scheduling/booking/` | `models`, `prompts` | `packages/scheduling/booking_executor.py` (turn logic) |
| `packages/engine/graph/` | `state`, `nodes`, `edges`, `compile` | `packages/engine/engine.py` |
| `apps/salon/domain/catalog/routers/` | `organizations`, `services`, `professionals` | `apps/salon/domain/catalog/router.py` + `helpers.py` |

**Regra:** código externo continua importando facades (`engine.py`, `service.py`, `booking_executor.py`, `catalog/router.py`) — não acoplar a submódulos internos salvo testes ou código no mesmo pacote.

## Seeds e mocks

| Path | Uso |
|------|-----|
| `apps/salon/seeds/vertical_orgs.py` | Org demo Beauty Express |
| `apps/salon/seeds/datalake_mocks/` | Textos mock para `scripts/seed_datalake.py` (substitui `scratch/` gitignored) |

## HTTP — prefixo único

Todos os routers usam paths **relativos**. [`apps/salon/api/app_factory.py`](../apps/salon/api/app_factory.py) monta com `prefix="/api/v1"`.

## Composition root

- [`main.py`](../main.py) — `app = create_salon_app()`
- [`apps/salon/api/app_factory.py`](../apps/salon/api/app_factory.py) — registra routers, middleware, prompts, lifespan (checkpointer)

## Migração concluída

A camada `src/` legada foi removida. Todo código novo deve importar de `packages.*` ou `apps.salon.*`.
