# Packages — motor compartilhado

Pacotes compartilhados entre `apps/salon` e `apps/clinic`.

Durante a migração, o código continua importável via `src.*`. Cada subpasta documenta o destino final.

| Pasta | Módulo atual | Responsabilidade |
|-------|--------------|------------------|
| `engine/` | `src/chat/` | LangGraph, prompts shim, métricas |
| `lakehouse/` | `src/analytics/lakehouse_*` | Bronze→Gold, RAG |
| `scheduling/` | `src/scheduling/` | Agenda, tools |
| `auth_core/` | `src/core/`, `src/auth/` | Tenant, JWT, DB |
| `models/` | `src/models/` | Enums e schemas |
| `integrations/webhook/` | `src/webhook/` | WhatsApp, session store |
| `domain/catalog` | `src/organizations/` | Catálogo salão (em `apps/salon/domain`) |
| `domain/clients` | `src/patients/` | Clientes salão (em `apps/salon/domain`) |
