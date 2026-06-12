# Deploy FlowIA no Render + Supabase

Hosting confirmado para produção multi-tenant:

| Componente | Render | Tipo |
|------------|--------|------|
| API FastAPI | `flowia-api` | Web Service (Python) |
| Dashboard SPA | `flowia-dashboard` | Static Site |
| Landing marketing | `flowia-landing` | Static Site |
| Banco | Supabase (externo) | PostgreSQL + RLS |

Blueprint IaC: [`render.yaml`](../render.yaml) na raiz do repo.

---

## 1. Pré-requisitos

1. Repositório Git no GitHub/GitLab/Bitbucket (Render exige Git para deploy contínuo).
2. Projeto **Supabase de produção** — recomendado separado do dev; piloto Jun/2026 usa o mesmo projeto (ver [`PRODUCTION.md`](PRODUCTION.md)).
3. Conta Render com workspace selecionado.
4. Secrets novos — **nunca** reutilizar dev ([`SECRET_ROTATION.md`](SECRET_ROTATION.md)).

Gerar secrets (stdout — não commitar):

```powershell
venv\Scripts\python.exe scripts\generate_prod_secrets.py
```

Templates de env:

- API: [`deployments/multi-tenant/.env.production.example`](../deployments/multi-tenant/.env.production.example)
- Dashboard build: [`deployments/multi-tenant/render-dashboard.env.example`](../deployments/multi-tenant/render-dashboard.env.example)

---

## 2. Supabase (manhã)

```bash
supabase link --project-ref <PROD_REF>
supabase db push
```

Habilitar **pgvector** no Dashboard se a migration `20260605000000_phase4_data_lake` falhar na extensão.

Seed piloto (`.env` apontando prod temporariamente):

```powershell
venv\Scripts\python.exe scripts\seed_salon.py
venv\Scripts\python.exe scripts\create_salon_user.py --email dono@salao.com --password "SenhaForte1!"
venv\Scripts\python.exe scripts\setup_dev_env.py --email admin@flowia.com --password "SenhaForte2!"
venv\Scripts\python.exe scripts\check_env.py
```

**Migrations pendentes conhecidas** (se o projeto Supabase foi criado antes de Jun/2026): aplicar os 17 arquivos em [`supabase/migrations/`](../supabase/migrations/) na ordem do [`CLAUDE.md`](../CLAUDE.md) §15.

---

## 3. Deploy API — Render Web Service

### Opção A: Blueprint (recomendado)

1. Render Dashboard → **Blueprints** → New Blueprint Instance
2. Conectar repo; Render detecta [`render.yaml`](../render.yaml)
3. Preencher env vars marcadas `sync: false` no painel

### Opção B: Manual

| Campo | Valor |
|-------|-------|
| Runtime | Python 3 |
| Root | repo root |
| Build | `pip install -r requirements.txt` |
| Start | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Health check | `/health` |
| Instâncias | **1** (scheduler) |

### Env vars críticas (API)

| Variável | Valor |
|----------|-------|
| `PRODUCT_LINE` | `salon` |
| `CHECKPOINTER_BACKEND` | `auto` |
| `SCHEDULER_ENABLED` | `true` |
| `COOKIE_SECURE` | `true` |
| `WEBHOOK_DEDUP_RETENTION_DAYS` | `7` |
| `ALLOWED_ORIGINS` | `["https://SEU-DASHBOARD.onrender.com"]` |
| `ALLOWED_HOSTS` | `["SEU-API.onrender.com"]` |
| `OPENAI_API_KEY` | secret prod ([OpenAI Platform](https://platform.openai.com/api-keys)) |
| `MODEL_NAME` | `gpt-4o-mini` (default) |
| `VISION_MODEL_NAME` | `gpt-4o` (OCR data lake) |
| `EMBEDDING_MODEL_NAME` | `text-embedding-3-small` (RAG) |
| `SUPABASE_*`, `DASHBOARD_*`, `WHATSAPP_VERIFY_TOKEN` | secrets prod |
| `WHATSAPP_QUEUE_MODE` | `inline` na API (default); worker Render usa `worker` |

### Worker WhatsApp (`flowia-whatsapp-worker`)

Background worker no Blueprint consome `whatsapp_inbound_jobs` (FIFO). Ativar após webhook Meta validado; API permanece com `WHATSAPP_QUEUE_MODE=inline` até go-live ou escalar worker explicitamente.


**Não definir:** `DEV_*`, `VITE_DEV_*`.

Anotar URL da API: `https://flowia-api.onrender.com` (exemplo).

---

## 4. Deploy Dashboard — Render Static Site

| Campo | Valor |
|-------|-------|
| Root | `apps/salon/dashboard` |
| Build | `npm ci && npm run build` |
| Publish | `dist` |

### Env vars build-time

| Variável | Valor |
|----------|-------|
| `NODE_VERSION` | `24` (Node 24 LTS — obrigatório para Vite 7 no dashboard; ver `.node-version` na raiz) |
| `VITE_API_URL` | `https://flowia-api.onrender.com/api/v1` |
| `VITE_SUPABASE_URL` | URL prod |
| `VITE_SUPABASE_KEY` | anon key prod |

### SPA routing

O [`render.yaml`](../render.yaml) inclui rewrite `/* → /index.html`. Fallback adicional: [`apps/salon/dashboard/public/_redirects`](../apps/salon/dashboard/public/_redirects).

Após obter URL final do Static Site, **atualizar `ALLOWED_ORIGINS`** na API.

---

## 4b. Deploy Landing — Render Static Site

| Campo | Valor |
|-------|-------|
| Nome | `flowia-landing` |
| Root | `apps/landing` |
| Build | `npm ci && npm run build` |
| Publish | `dist` |

Sem env vars obrigatórias de runtime (CTA `mailto:` estático).

| Variável | Valor |
|----------|-------|
| `NODE_VERSION` | `24` (alinhado ao monorepo — `engines >=24` em `apps/landing/package.json`) |
| `VITE_DEMO_EMAIL` | opcional — contato no build (default no blueprint: `contato@gaussix.com.br`) |

URL esperada: https://flowia-landing.onrender.com — registrar em [`PRODUCTION.md`](PRODUCTION.md).

### Homologação — conferir Node 24 nos Static Sites

Após merge na `main` (ou antes do go-live), validar **cada** Static Site no Render Dashboard:

| Serviço | Env var | Valor esperado |
|---------|---------|----------------|
| `flowia-dashboard` | `NODE_VERSION` | `24` |
| `flowia-landing` | `NODE_VERSION` | `24` |

Se o serviço foi criado antes do pin: **Environment → Add** `NODE_VERSION=24` → **Manual Deploy**. No log de build, a primeira linha deve indicar Node **24.x**. O [`render.yaml`](../render.yaml) na raiz já declara `NODE_VERSION: "24"` para novos syncs de Blueprint.

---

## 5. Smoke produção

Automático (health + dashboard HTTP + agente RAG):

```powershell
venv\Scripts\python.exe scripts\smoke_prod.py --api-url https://flowia-api.onrender.com --dashboard-url https://flowia-dashboard.onrender.com
venv\Scripts\python.exe scripts\smoke_agent.py --api-url https://flowia-api.onrender.com/api/v1
```

Manual:

| # | Teste | Esperado |
|---|-------|----------|
| 1 | `GET /health` | `status: ok`, `database: connected` |
| 2 | Login org_admin | cookie `session_token` |
| 3 | Overview, Agenda, Catálogo, Clientes | sem CORS |
| 4 | Criar cliente + agendamento | persiste no Supabase |
| 5 | super_admin | sem `/admin/*` em prod (AdminDevRoute exige DEV) |

Checklist completo: [`STAGING.md`](STAGING.md) · Rollback: [`PRODUCTION.md`](PRODUCTION.md)

---

## 6. Rollback rápido

| Problema | Ação |
|----------|------|
| Deploy API quebrado | Render → flowia-api → **Rollback** deploy anterior |
| CORS / login | Conferir `ALLOWED_ORIGINS` = URL exata HTTPS do dashboard; `COOKIE_SECURE=true` (SameSite=None) |
| Scheduler duplicado | Manter **1 instância** Web Service |
| Cold start (free tier) | Upgrade para Starter ou plano always-on |

---

## 7. Render MCP (opcional)

Copie [`.cursor/mcp.json.example`](../.cursor/mcp.json.example) para `.cursor/mcp.json` (gitignored) ou `~/.cursor/mcp.json`. Preencha `Authorization: Bearer <RENDER_API_KEY>`. Sem auth, usar Dashboard ou Blueprint.

---

## URLs de produção

Registro canônico: [`PRODUCTION.md`](PRODUCTION.md).

| Serviço | URL |
|---------|-----|
| API | https://flowia-api.onrender.com |
| Dashboard | https://flowia-dashboard.onrender.com |
| Landing | https://flowia-landing.onrender.com |
| Supabase (piloto) | https://vwhsivwoiiicydanypmo.supabase.co |
| Webhook WhatsApp (futuro) | https://flowia-api.onrender.com/api/v1/webhook/whatsapp |
