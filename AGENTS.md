# FlowIA — Agent Guide

Fonte da verdade (negócio + arquitetura + segurança): [`CLAUDE.md`](CLAUDE.md) — atualizar junto com mudanças significativas.

SaaS multi-tenant para salões (`PRODUCT_LINE=salon`).

## Stack

| Camada | Versões |
|--------|---------|
| Runtime | Python 3.12, Node 20 |
| API | FastAPI ≥0.109, Uvicorn ≥0.27, Pydantic v2 |
| AI | LangGraph ≥1.0, langchain-google-genai ≥4.0, Gemini |
| DB | Supabase ≥2.3, PostgreSQL + RLS, psycopg3 |
| Frontend | React 18.3, Vite 5.4, TS 5.6, Tailwind 4.3, React Router 7.16 |
| Test/Lint | pytest 8, ruff, vitest 2, Playwright, ESLint 9 |

## Onde editar

| Escopo | Caminho |
|--------|---------|
| Motor | `packages/` (auth_core, engine, scheduling, lakehouse, integrations, models) |
| Produto salão | `apps/salon/` (api, domain, dashboard, prompts) |
| Entry API | `main.py` → `apps/salon/api/app_factory.py` |
| Frontend | `apps/salon/dashboard/` |
| Testes | `tests/` · Migrações | `supabase/migrations/` |

**Legado proibido:** `src/`, `dashboard/` na raiz, `.agent/`.

## Comandos

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pytest --cov=packages --cov=apps/salon && ruff check packages apps/salon tests main.py
cd apps/salon/dashboard && npm run dev && npm test && npm run lint && npm run build
python scripts/check_env.py
python scripts/test_booking_flow_http.py                  # multi-turn via /chat/test
python scripts/simulate_whatsapp_webhook.py             # webhook fake (sem Meta)
python scripts/test_scheduling_llm.py                   # LLM + tools (Gemini, ~30s)
python scripts/test_scheduling_hybrid.py                # comparar tokens hibrido vs LLM puro
python scripts/generate_prod_secrets.py   # stdout — secrets prod
python scripts/apply_migrations.py        # supabase db push alternativo
python scripts/list_db_migrations.py      # verificar migrations aplicadas
python scripts/smoke_prod.py --api-url https://flowia-api.onrender.com --dashboard-url https://flowia-dashboard.onrender.com
python scripts/smoke_hybrid_prod.py --api-url https://flowia-api.onrender.com  # PROD_SMOKE_PASSWORD no .env
python scripts/smoke_agent.py --api-url https://flowia-api.onrender.com/api/v1
python scripts/onboard_tenant.py --checklist   # runbook 1º cliente pagante
cd apps/landing && npm run dev                 # landing marketing local
start_flowia.bat   # Windows: backend + frontend
```

Testes: `CHECKPOINTER_BACKEND=memory` (ver `tests/conftest.py`).

## Cursor

Regras em [`.cursor/rules/`](.cursor/rules/) · Skills em [`.cursor/skills/`](.cursor/skills/) · MCP: copiar [`.cursor/mcp.json.example`](.cursor/mcp.json.example) → `.cursor/mcp.json` (gitignored) — Supabase read-only + Render ops.

| Regra | Quando |
|-------|--------|
| `01-global-standards` | Sempre |
| `02-monorepo-layout` | `main.py`, app_factory, mover código |
| `03-python-api` | `*.py` em packages/apps/tests |
| `04-react-dashboard` | dashboard `*.ts(x)` |
| `05-supabase-migrations` | `supabase/**/*.sql` |
| `06-lgpd-compliance` | Sempre — PII, consent, DSAR, retenção |

| Skill | Trigger |
|-------|---------|
| `flowia-dev` | Subir local, CI, pytest, `.env` |
| `flowia-monorepo` | Onde colocar código, imports, boundaries |
| `flowia-salon-domain` | Auth, agenda, WhatsApp, LangGraph, RLS |
| `flowia-security` | Auditoria tenant, secrets, webhook, 403 |
| `flowia-lgpd` | Consentimento, DSAR, retenção, checklist LGPD |
| `flowia-data-lake` | Bronze/Silver/Gold, OCR, RAG, DataLake UI |
| `security-audit` | Revisão de injeção (SQL/prompt), vazamento PII/secrets, tenant |
| `performance-optimization` | Bundle/lazy loading, N+1, queries lentas |
| `feature-flag-override` | Toggles (`is_active`, `settings`, `PRODUCT_LINE`, `AdminDevRoute`), UI `card-brutal` |

Skills carregam sob demanda via `@nome` no chat (`disable-model-invocation: true`).

Docs: [`CLAUDE.md`](CLAUDE.md) · [`docs/TENANCY_AND_SCALE.md`](docs/TENANCY_AND_SCALE.md) · [`docs/README.md`](docs/README.md) · [`ROADMAP`](docs/ROADMAP.md) · [`PRODUCTION`](docs/PRODUCTION.md)
