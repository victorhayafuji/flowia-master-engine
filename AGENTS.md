# FlowIA — Agent Guide

Fonte da verdade (negócio + arquitetura + segurança): [`CLAUDE.md`](CLAUDE.md) — atualizar junto com mudanças significativas.

SaaS multi-tenant para salões (`PRODUCT_LINE=salon`).

**Guardrail:** [`CLAUDE.md` Parte VIII](CLAUDE.md#parte-viii--futuras-implementações-não-mvp) é visão pós-MVP — **não implementar** (código, migrations, endpoints, prompts) salvo pedido explícito do usuário. Escopo ativo = Partes I–VII.

## Stack

| Camada | Versões |
|--------|---------|
| Runtime | Python 3.12, Node 24 LTS |
| API | FastAPI ≥0.109, Uvicorn ≥0.27, Pydantic v2 |
| AI | LangGraph ≥1.0, langchain-openai, OpenAI |
| Modelos | `gpt-4o-mini` (chat), `gpt-4o` (OCR), `text-embedding-3-small` (RAG) — ver `CLAUDE.md` §9 |
| DB | Supabase ≥2.3, PostgreSQL + RLS, psycopg3 |
| Frontend | React 18.3, Vite 7.3 (dashboard), TS 5.6, Tailwind 4.3, React Router 7.16 |
| Test/Lint | pytest 8, ruff, vitest 3, Playwright, ESLint 9 |

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
python scripts/test_scheduling_llm.py                   # LLM + tools (OpenAI, ~30s)
python scripts/test_scheduling_hybrid.py                # comparar tokens hibrido vs LLM puro
python scripts/generate_prod_secrets.py   # stdout — secrets prod
python scripts/apply_migrations.py        # supabase db push alternativo
python scripts/list_db_migrations.py      # verificar migrations aplicadas
python scripts/smoke_prod.py --api-url https://flowia-api.onrender.com --dashboard-url https://flowia-dashboard.onrender.com
python scripts/smoke_hybrid_prod.py --api-url https://flowia-api.onrender.com  # PROD_SMOKE_PASSWORD no .env
python scripts/smoke_agent.py --api-url https://flowia-api.onrender.com/api/v1
python scripts/onboard_tenant.py --checklist   # runbook 1º cliente pagante
start_flowia.bat   # Windows: backend + frontend
```

Testes: `CHECKPOINTER_BACKEND=memory` (ver `tests/conftest.py`).

## Cursor + Claude Code (dual agent)

Dois agentes no mesmo repo — **contexto não é compartilhado** entre sessões. Reafirme escopo (Partes I–VII vs Parte VIII) ao abrir cada um.

| Ferramenta | Quando usar | Config no repo |
|------------|-------------|----------------|
| **Cursor Agent** | Edição multi-arquivo, subagentes (explore, CI, bugbot), skills `@flowia-*`, integração IDE | [`.cursor/rules/`](.cursor/rules/) · [`.cursor/skills/`](.cursor/skills/) · MCP: `.cursor/mcp.json` (gitignored) |
| **Claude Code** | Refactors longos, planejamento (`defaultMode: plan`), terminal autônomo com permissões explícitas | [`.claude/settings.json`](.claude/settings.json) · MCP: `.mcp.json` (gitignored) · lê [`CLAUDE.md`](CLAUDE.md) na raiz |

**Setup único (Windows):**

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_claude_code.ps1
npm install -g @anthropic-ai/claude-code   # CLI opcional
cursor --install-extension anthropic.claude-code
```

MCP: copiar [`.cursor/mcp.json.example`](.cursor/mcp.json.example) → `.cursor/mcp.json` **e** [`.mcp.json.example`](.mcp.json.example) → `.mcp.json` (ou rodar o script acima para sincronizar Cursor → Claude). Supabase read-only + Render ops.

**Só você pode fazer (OAuth):** login Anthropic Pro no painel Claude Code (ícone Spark) e/ou `claude auth login` no terminal. Billing Anthropic ≠ Cursor.

**Teste pós-login:** *"Leia CLAUDE.md Partes I–VII; não implementar Parte VIII sem pedido explícito."*

## Cursor (regras e skills)

| Regra | Quando |
|-------|--------|
| `01-global-standards` | Sempre |
| `02-monorepo-layout` | `main.py`, app_factory, mover código |
| `03-python-api` | `*.py` em packages/apps/tests |
| `04-react-dashboard` | dashboard `*.ts(x)` |
| `05-supabase-migrations` | `supabase/**/*.sql` |
| `06-lgpd-compliance` | Sempre — PII, consent, DSAR, retenção |
| `07-future-scope` | Sempre — Parte VIII / CJI não implementar sem pedido explícito |

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

## Adversarial tests

```bash
py -3.12 scripts/run_adversarial_matrix.py
py -3.12 -m pytest tests/test_engine_input_guard.py tests/test_lakehouse_governance.py tests/test_search_kb_security.py tests/test_prompt_guardrails_static.py tests/test_chat_security.py tests/test_webhook_input_guard.py tests/test_agent_flow_adversarial.py -m "not llm_behavior" -q
RUN_LLM_BEHAVIOR_TESTS=1 py -3.12 -m pytest tests/test_agent_behavior_llm.py -m llm_behavior -q
```

