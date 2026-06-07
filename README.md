# Flowia Master Engine

Plataforma SaaS multi-tenant para salões de beleza: dashboard administrativo, agendamento inteligente e assistente conversacional (LangGraph + Gemini).

**Documentação completa:** [`CLAUDE.md`](CLAUDE.md) — fonte da verdade do projeto (negócio + arquitetura + segurança).

**Repositório:** https://github.com/victorhayafuji/flowia-master-engine

## Produção (piloto Render)

| Serviço | URL |
|---------|-----|
| Dashboard | https://flowia-dashboard.onrender.com |
| API | https://flowia-api.onrender.com |
| Health | https://flowia-api.onrender.com/health |

Deploy: [`docs/RENDER.md`](docs/RENDER.md) · Ops: [`docs/PRODUCTION.md`](docs/PRODUCTION.md) · **Tenancy & escala:** [`docs/TENANCY_AND_SCALE.md`](docs/TENANCY_AND_SCALE.md)

## Quick start (local)

```bash
cp .env.example .env          # preencher variáveis
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

cd apps/salon/dashboard && npm install && npm run dev
```

Windows (backend + frontend): `start_flowia.bat`

- API: http://localhost:8000/health
- Dashboard: http://localhost:5173
- Validar env: `python scripts/check_env.py`

## Stack

FastAPI · LangGraph · Gemini · Supabase (PostgreSQL + RLS) · React 18 · Vite 5 · Tailwind 4

## Documentação

| Documento | Conteúdo |
|-----------|----------|
| [**CLAUDE.md**](CLAUDE.md) | Handbook completo — fonte da verdade |
| [AGENTS.md](AGENTS.md) | Guia Cursor (comandos, rules, skills) |
| [docs/README.md](docs/README.md) | Índice temático |
| [docs/PRODUCTION.md](docs/PRODUCTION.md) | URLs, smoke, rollback |
| [docs/TENANCY_AND_SCALE.md](docs/TENANCY_AND_SCALE.md) | Multi-tenant, onboarding, escala 200+ |
| [docs/RENDER.md](docs/RENDER.md) | Deploy Render + Supabase |

## Testes

```bash
pytest --cov=packages --cov=apps/salon
cd apps/salon/dashboard && npm test && npm run lint && npm run build
```

CI: `.github/workflows/ci.yml`

---
*FlowIA Master Engine*
