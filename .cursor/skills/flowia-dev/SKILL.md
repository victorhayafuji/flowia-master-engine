---
name: flowia-dev
description: Runs local dev, tests, CI checks, and .env validation for FlowIA monorepo. Use when starting the app locally, running pytest/ruff/npm test, debugging CI failures, or validating environment configuration.
disable-model-invocation: true
---

# FlowIA Dev

Comandos rápidos: ver `AGENTS.md`. Detalhes abaixo.

## Validar .env

```bash
python scripts/check_env.py
python scripts/setup_dev_env.py --email admin@flowia.com --password SUA_SENHA
```

Nunca commitar `.env`. Vite lê `.env` da raiz do monorepo.

## Testes backend

```bash
set CHECKPOINTER_BACKEND=memory   # Windows
export CHECKPOINTER_BACKEND=memory  # Linux/macOS
pytest --cov=packages --cov=apps/salon
ruff check packages apps/salon tests main.py
```

Env vars mínimas (espelha `.github/workflows/ci.yml`):

```
GOOGLE_API_KEY=test-key
SUPABASE_URL=https://example.supabase.co
SUPABASE_KEY=test-anon-key
SUPABASE_SERVICE_ROLE=test-service-role
SUPABASE_DB_URL=postgresql://postgres:pass@localhost:5432/postgres
WHATSAPP_VERIFY_TOKEN=test-verify-token
DASHBOARD_API_KEY=test-dashboard-api-key
DASHBOARD_JWT_SECRET=test-jwt-secret-for-ci-only-32chars
CHECKPOINTER_BACKEND=memory
SCHEDULER_ENABLED=false
```

## Testes frontend

```bash
cd apps/salon/dashboard && npm ci && npm run lint && npm test && npm run build
```

Build requer: `VITE_SUPABASE_URL`, `VITE_SUPABASE_KEY`, `VITE_API_URL=http://localhost:8000/api/v1`

## CI & migrações

- CI: `.github/workflows/ci.yml` — ruff + pytest (cov ≥30%), lint + vitest + build
- Migrações: `supabase db push`, `python scripts/apply_migrations.py` ou SQL Editor
- Verificar: `python scripts/list_db_migrations.py`
- Windows multi-tenant: `start_flowia.bat tenants\beauty-express`

## Smoke produção

```powershell
venv\Scripts\python.exe scripts\smoke_prod.py --api-url https://flowia-api.onrender.com --dashboard-url https://flowia-dashboard.onrender.com
venv\Scripts\python.exe scripts\smoke_agent.py --api-url https://flowia-api.onrender.com/api/v1
venv\Scripts\python.exe scripts\test_rag_chat.py
```

Ops: [`docs/PRODUCTION.md`](../../docs/PRODUCTION.md) · Deploy: [`docs/RENDER.md`](../../docs/RENDER.md)
