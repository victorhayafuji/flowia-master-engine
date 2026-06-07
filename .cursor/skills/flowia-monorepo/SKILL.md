---
name: flowia-monorepo
description: Guides package placement and import boundaries when moving code, adding modules, or refactoring imports in FlowIA. Use when asking where to put new code, creating packages, or checking dependency direction.
disable-model-invocation: true
---

# FlowIA Monorepo

## Grafo permitido

```
models        → (stdlib/pydantic only)
auth_core     → models
scheduling    → auth_core, models
lakehouse     → auth_core, models
engine        → auth_core, models, scheduling, lakehouse
integrations  → engine, auth_core
apps/salon    → engine, scheduling, lakehouse, auth_core
```

**Proibido:** `packages/*` importar de `apps/salon`.

## Onde colocar código novo

| Tipo | Destino |
|------|---------|
| DTOs/enums compartilhados | `packages/models` |
| Config, DB, JWT, tenant | `packages/auth_core` |
| Agenda, booking tools | `packages/scheduling` |
| Data lake, RAG | `packages/lakehouse` |
| LangGraph, chat, métricas | `packages/engine` |
| WhatsApp webhook/outbound | `packages/integrations` |
| Catálogo, clientes (salão) | `apps/salon/domain` |
| Routers HTTP, app factory | `apps/salon/api` |
| UI React | `apps/salon/dashboard` |
| Prompts do agente | `apps/salon/prompts` |

## Checklist de refactor

1. Identificar pacote correto (tabela acima)
2. Verificar grafo — sem import circular
3. Se expõe HTTP: router + registro em `apps/salon/api/app_factory.py`
4. Rodar `pytest` e `ruff check packages apps/salon tests main.py`

Tabela de routers: [reference.md](reference.md). Doc: `docs/PACKAGE_BOUNDARIES.md`.
