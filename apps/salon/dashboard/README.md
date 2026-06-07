# FlowIA Salon Dashboard

SPA React (Vite 5 + TypeScript + Tailwind 4) — painel administrativo do produto salão.

**Handbook:** [`CLAUDE.md`](../../../CLAUDE.md) §28–31

## Rotas

| Path | Página | Acesso |
|------|--------|--------|
| `/login` | Login | público |
| `/` | Overview | autenticado |
| `/agenda` | Agenda | autenticado |
| `/patients` | Clientes | autenticado |
| `/catalog` | Catálogo | autenticado |
| `/admin/data-lake` | Data Lake | super_admin + DEV |
| `/admin/chat-test` | Chat Test | super_admin + DEV |

## Env (build-time)

| Variável | Local | Produção Render |
|----------|-------|-----------------|
| `VITE_API_URL` | `http://localhost:8000/api/v1` | `https://flowia-api.onrender.com/api/v1` |
| `VITE_SUPABASE_URL` | projeto Supabase | projeto Supabase |
| `VITE_SUPABASE_KEY` | anon key | anon key |

Lê `.env` da **raiz do monorepo**. Template build prod: [`deployments/multi-tenant/render-dashboard.env.example`](../../../deployments/multi-tenant/render-dashboard.env.example)

## Comandos

```bash
cd apps/salon/dashboard
npm install
npm run dev          # http://localhost:5173
npm test && npm run lint && npm run build
npm run test:e2e     # Playwright
```

## Auth

Cookie JWT HttpOnly da API — **não** usa Supabase Auth no browser. Client: `@/shared/lib/api`.

## Deploy

Render Static Site — root `apps/salon/dashboard`, publish `dist`. SPA rewrite: `render.yaml` + `public/_redirects`.
