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
| `packages/scheduling` | Agenda, tools de booking |
| `packages/lakehouse` | Pipeline Bronze→Gold, RAG |
| `packages/engine` | LangGraph, métricas, chat test, checkpointer |
| `packages/integrations` | WhatsApp webhook + outbound |
| `apps/salon/domain` | Catálogo e clientes (produto) |
| `apps/salon/api` | Composition root `create_salon_app()` |

## HTTP — prefixo único

Todos os routers usam paths **relativos**. [`apps/salon/api/app_factory.py`](../apps/salon/api/app_factory.py) monta com `prefix="/api/v1"`.

## Composition root

- [`main.py`](../main.py) — `app = create_salon_app()`
- [`apps/salon/api/app_factory.py`](../apps/salon/api/app_factory.py) — registra routers, middleware, prompts, lifespan (checkpointer)

## Migração concluída

A camada `src/` legada foi removida. Todo código novo deve importar de `packages.*` ou `apps.salon.*`.
