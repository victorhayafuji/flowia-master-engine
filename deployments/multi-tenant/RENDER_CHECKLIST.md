# Checklist Render — deploy manual (dia D)

Use após push do repo para GitHub/GitLab. Blueprint: [`render.yaml`](../../render.yaml).

## Pré-flight

- [ ] Repo Git remoto conectado ao Render
- [ ] `python scripts/generate_prod_secrets.py` — secrets no painel Render (sync off)
- [ ] Supabase prod: `python scripts/apply_migrations.py` ou `supabase db push`
- [ ] Usuários: `create_salon_user.py` + `create_platform_admin.py`

## 1. Web Service `flowia-api`

Dashboard → New → Web Service → conectar repo.

| Campo | Valor |
|-------|-------|
| Name | `flowia-api` |
| Runtime | Python 3 |
| Build | `pip install -r requirements.txt` |
| Start | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Health | `/health` |
| Instances | 1 |

Copiar env de [`.env.production.example`](.env.production.example). Ajustar `ALLOWED_HOSTS` após obter URL `*.onrender.com`.

## 2. Static Site `flowia-dashboard`

Dashboard → New → Static Site.

| Campo | Valor |
|-------|-------|
| Root | `apps/salon/dashboard` |
| Build | `npm ci && npm run build` |
| Publish | `dist` |

Env build: [`render-dashboard.env.example`](render-dashboard.env.example) — `VITE_API_URL` = URL da API + `/api/v1`.

**Rewrite SPA:** incluído no `render.yaml`; ou Dashboard → Redirects/Rewrites → `/*` → `/index.html`.

## 3. Fechar CORS

Voltar em `flowia-api` → Environment:

```
ALLOWED_ORIGINS=["https://SEU-DASHBOARD.onrender.com"]
```

Redeploy API se necessário.

## 4. Smoke

```powershell
venv\Scripts\python.exe scripts\smoke_prod.py --api-url https://flowia-api.onrender.com --dashboard-url https://flowia-dashboard.onrender.com
```

Registrar URLs em [`docs/PRODUCTION.md`](../../docs/PRODUCTION.md).

## Render MCP (Cursor)

Adicionar ao `.cursor/mcp.json`:

```json
"render": {
  "url": "https://mcp.render.com/mcp",
  "headers": { "Authorization": "Bearer <RENDER_API_KEY>" }
}
```

API key: Render Dashboard → Account Settings → API Keys.
