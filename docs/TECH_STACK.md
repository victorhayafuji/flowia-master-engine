# Tecnologias Empregadas — Prós e Contras (FlowIA Master Engine)

> Stack do produto ativo (`PRODUCT_LINE=salon`), com o **porquê** de cada escolha, seus **trade-offs**
> e **alternativas consideradas**. Fonte: [`CLAUDE.md`](../CLAUDE.md) §9, §33, §35.
> Versões exatas: [`requirements.txt`](../requirements.txt) e [`apps/salon/dashboard/package.json`](../apps/salon/dashboard/package.json).

Legenda de risco: 🟢 baixo · 🟡 atenção · 🔴 dívida/prazo.

## Backend

### Python 3.12 + FastAPI + Uvicorn + Pydantic v2
- **Papel:** API REST `/api/v1`, validação, async.
- **Prós:** ecossistema de IA maduro; FastAPI = tipagem + OpenAPI automático + async nativo; Pydantic v2 rápido.
- **Contras:** GIL limita CPU-bound (mitigado por I/O async + workers); tipagem dinâmica exige testes/lint.
- **Alternativas:** Node/Nest (menos maduro p/ IA), Django (mais pesado p/ API pura). 🟢

### LangGraph + LangChain + langchain-openai
- **Papel:** grafo de agentes (triagem → recepcionista/suporte/agendamento), tools, checkpointer.
- **Prós:** orquestração com estado/checkpoint; tool-calling estruturado; troca de provider.
- **Contras:** API em evolução rápida (risco de breaking changes); abstrações podem esconder custo de tokens
  — mitigado pelo **motor híbrido determinístico** que evita o LLM quando dá ([§23.1](../CLAUDE.md)). 🟡

### OpenAI — `gpt-4o-mini` (chat) · `gpt-4o` (OCR Vision) · `text-embedding-3-small`
- **Papel:** chat do agente, OCR Bronze→Silver, embeddings RAG.
- **Prós:** qualidade alta; `4o-mini` barato; embeddings consistentes com o pgvector atual.
- **Contras:** dependência de fornecedor + custo por token; **família `gpt-4o` em trajetória de deprecação**
  (migração planejada p/ linha 5.x — [§48.1](../CLAUDE.md)); trocar embeddings exige re-vetorizar o Gold.
- **Alternativas:** Gemini/Claude (chat), modelos locais (custo de infra). 🔴 *prazo de deprecação*

### Supabase — PostgreSQL + RLS + Storage + pgvector
- **Papel:** dados de negócio (multi-tenant via `organization_id` + RLS), Storage (data lake), busca vetorial.
- **Prós:** Postgres gerenciado + RLS = isolamento forte; Storage e pgvector no mesmo lugar; um banco p/ N tenants.
- **Contras:** backend usa `SERVICE_ROLE` (ignora RLS) → no-leak do agente depende de filtro em **código**;
  PostgREST tem limites de linhas a observar em agregações grandes; lock-in parcial. 🟡

### PostgresSaver (checkpointer LangGraph)
- **Papel:** memória de conversa por `thread_id`.
- **Prós:** persistência sem Redis extra (decisão deliberada zero-Redis); reaproveita o Postgres.
- **Contras:** acopla memória ao Postgres; `PostgresSaver.setup()` cria tabelas próprias (internas). 🟢

### PyJWT (HS256) + bcrypt + cookie HttpOnly
- **Papel:** auth do dashboard.
- **Prós:** PyJWT é mantido ativamente (migrado de `python-jose` por CVEs — [§48.2](../CLAUDE.md));
  `algorithms=["HS256"]` fixado (anti algorithm-confusion); cookie HttpOnly+Secure.
- **Contras:** HS256 = segredo compartilhado (rotação exige novo login de todos). 🟢

### slowapi (rate limiting) + APScheduler (jobs)
- **Prós:** rate limit em login/webhook; APScheduler cobre lembretes/no-show/purge sem broker externo.
- **Contras:** ambos **in-process** → limites/cooldowns não são compartilhados entre réplicas;
  **pré-requisito de `scale>1`** mover p/ store compartilhado ([§20, §48.3](../CLAUDE.md)). 🟡

### httpx
- **Papel:** chamadas à Graph API (Meta) com timeout.
- **Prós:** async, timeouts explícitos, sem vazar token em log. **Contras:** —. 🟢

## Frontend

### React 18 + Vite 7 + TypeScript 5 + Tailwind v4
- **Papel:** SPA do dashboard.
- **Prós:** Vite 7 = build/HMR rápidos; TS pega erros em build; Tailwind v4 = design system (tokens GAUSSIX).
- **Contras:** Vite 7 exige Node `>=20.19/22.13/>=24` (padronizado **Node 24 LTS**) — Node ímpar não roda;
  segue em React 18 (migração a 19 separada — [§48.4](../CLAUDE.md)). 🟢

### React Router 7 · lucide-react · @dnd-kit · react-calendar-timeline
- **Prós:** rotas lazy + guards (`ProtectedRoute`/`AdminDevRoute`); DnD na agenda; timeline operacional.
- **Contras:** `react-calendar-timeline` exige CSS scoped p/ herdar os tokens; libs DnD adicionam bundle. 🟢

## Qualidade / Tooling

### pytest + vitest + Playwright · ruff + ESLint
- **Prós:** cobertura backend ~70% (gate 50); E2E mockados p/ CI sem backend; ruff/ESLint no CI;
  suíte **adversarial** (injeção SQL/prompt, no-leak cross-tenant) em camadas.
- **Contras:** Playwright exige Node 24; testes de comportamento LLM real são opt-in (custo) — não no CI. 🟢

## Infraestrutura

### Render (Web + Static) + Supabase prod
- **Prós:** deploy simples (Blueprint `render.yaml`), HTTPS, escala vertical fácil.
- **Contras:** `scale=1` hoje por causa do estado in-process (ver slowapi/APScheduler); host UTC exige
  cuidado com timezone (resolvido nos endpoints/guiado — ver [`SOLUTION_ARCHITECTURE.md`](SOLUTION_ARCHITECTURE.md)). 🟡

## Resumo de dívidas/prazos a acompanhar

| Item | Risco | Referência |
|------|-------|------------|
| Deprecação OpenAI `gpt-4o`/`4o-mini` → 5.x | 🔴 prazo | [§48.1](../CLAUDE.md) |
| Rate limit/cooldown in-process (bloqueia `scale>1`) | 🟡 | [§20, §48.3](../CLAUDE.md) |
| Consentimento "Discordo" não persiste (LGPD) | 🟡 | [§20](../CLAUDE.md) (fast-follow `privacy_declined_at`) |
| Agregação financeira lê linhas (payload no extremo) | 🟢 | [`SOLUTION_ARCHITECTURE.md`](SOLUTION_ARCHITECTURE.md) |

Decisões arquiteturais (ADRs): [`SOLUTION_ARCHITECTURE.md` §7](SOLUTION_ARCHITECTURE.md) · [`CLAUDE.md` §35](../CLAUDE.md).
