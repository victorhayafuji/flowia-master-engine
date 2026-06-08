# Staging — checklist de deploy

Checklist para publicar uma instância piloto do FlowIA Salão multi-tenant.

**Hosting produção:** Render (API Web Service + Dashboard Static Site) + Supabase. Guia: [`docs/RENDER.md`](RENDER.md). Tenancy: [`docs/TENANCY_AND_SCALE.md`](TENANCY_AND_SCALE.md).

## Pré-requisitos

- Projeto Supabase criado — **recomendado** prod separado do dev; piloto atual compartilha projeto local (ver [`PRODUCTION.md`](PRODUCTION.md))
- Migrations aplicadas: `supabase db push`, `python scripts/apply_migrations.py` ou SQL Editor em `supabase/migrations/`
- Extensão **pgvector** habilitada (Data Lake / RAG)
- Secrets prod novos: `python scripts/generate_prod_secrets.py` (stdout — não commitar)
- Templates: `deployments/multi-tenant/.env.production.example`

## Validar configuração

```bash
python scripts/check_env.py
python scripts/setup_dev_env.py --email admin@flowia.com --password SUA_SENHA
python scripts/seed_salon.py   # opcional — dados demo
```

## Variáveis críticas (produção)

| Variável | Valor recomendado |
|----------|-------------------|
| `CHECKPOINTER_BACKEND` | `auto` (Postgres via `SUPABASE_DB_URL`) |
| `SCHEDULER_ENABLED` | `true` (lembretes stub + no-show) |
| `COOKIE_SECURE` | `true` (HTTPS; cookie `SameSite=None` em prod Render) |
| `ALLOWED_ORIGINS` | URL HTTPS exata do dashboard Render |
| `ALLOWED_HOSTS` | hostname da API Render |
| `WEBHOOK_DEDUP_RETENTION_DAYS` | `7` |

Testes e CI usam `CHECKPOINTER_BACKEND=memory` e `SCHEDULER_ENABLED=false`.

**Nunca em produção:** `DEV_*`, `VITE_DEV_*`.

## Smoke pós-deploy

Produção (API + dashboard no ar):

```powershell
venv\Scripts\python.exe scripts\smoke_prod.py --api-url https://SUA-API.onrender.com --dashboard-url https://SEU-DASHBOARD.onrender.com
```

Local antes do deploy:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000
cd apps/salon/dashboard && npm run build && npm run preview
cd apps/salon/dashboard && npm run test:e2e
```

Rollback e registro de URLs: [`docs/PRODUCTION.md`](PRODUCTION.md).

Checklist de negócio: [`docs/SALON_BUSINESS_AUDIT.md`](SALON_BUSINESS_AUDIT.md).

## Rotação de secrets

Se `.env` foi exposto: [`docs/SECRET_ROTATION.md`](SECRET_ROTATION.md).

## WhatsApp (pendente)

Outbound/inbound real requer credenciais Meta Business API. Webhook prod: `https://flowia-api.onrender.com/api/v1/webhook/whatsapp`. Doc: [`WHATSAPP_SETUP.md`](WHATSAPP_SETUP.md). Até lá, lembretes rodam em modo stub (log + status `sent` no banco).
