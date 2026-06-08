---
name: flowia-salon-domain
description: Explains FlowIA salon domain flows for multi-tenant auth, scheduling, WhatsApp, LangGraph, and RLS. Use when working on tenant isolation, dashboard auth, appointments, webhooks, agent conversations, or Supabase schema.
disable-model-invocation: true
---

# FlowIA Salon Domain

## Autenticação

FastAPI JWT via cookie HttpOnly — única auth do dashboard.

- Login: `POST /api/v1/auth/login` — body usa **`username`** (valor = email cadastrado) + `password` → cookie `session_token`
- Produção Render: `COOKIE_SECURE=true` → `SameSite=None` + `Secure` (API e dashboard em subdomínios `*.onrender.com` distintos)
- Frontend: `loginWithCredentials()` + `navigate("/")` sem reload; `AuthContext` — **não** Supabase Auth no browser
- Sessão: `GET /api/v1/auth/me`
- Backend valida credenciais via Supabase Auth internamente

## Multi-tenant

- Header `x-organization-id` em requests autenticados
- `validated_tenant_context` em `packages/auth_core/dependencies.py`
- `super_admin`: `ALL` ou qualquer org · `org_admin`: header = `org_id` do JWT (403 se divergir)

## Agendamento

- Pacote: `packages/scheduling`
- Conflitos: `DoubleBookingError` → HTTP 409
- Tools LangGraph consomem scheduling via engine

## WhatsApp

- Inbound: webhook em `packages/integrations` — org via `organizations.whatsapp_phone_id`
- URL prod (futuro): `https://flowia-api.onrender.com/api/v1/webhook/whatsapp`
- Outbound: `packages/integrations/webhook/whatsapp.py` (Meta Graph API v21)
- Credenciais por org: `whatsapp_phone_id`, `whatsapp_access_token`

## LangGraph

- Grafo e chat: `packages/engine`
- Checkpointer: `packages/engine/checkpointer.py` (Prod: PostgresSaver · Testes: memory)
- Grafo lazy via proxy `master_engine`

## Onde estender

| Feature | Onde |
|---------|------|
| Endpoint catálogo/clientes | `apps/salon/domain` + app_factory |
| Nova tool de booking | `packages/scheduling` → engine |
| Novo nó do grafo | `packages/engine` |
| Nova página dashboard | `apps/salon/dashboard/src/` |

Schema: MCP Supabase (read-only). Migrações: `supabase/migrations/`. Doc: `docs/ARCHITECTURE.md`.
