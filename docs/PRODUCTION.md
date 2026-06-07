# Produção — URLs, smoke e rollback

Registro operacional do deploy Render (Jun/2026). Detalhes de deploy: [`RENDER.md`](RENDER.md).

**Antes do 1º cliente pagante:** ler [`TENANCY_AND_SCALE.md`](TENANCY_AND_SCALE.md) (ambiente prod vs onboarding de salão).

## Piloto atual vs recomendado

| Aspecto | Piloto atual (Jun/2026) | Recomendado antes de clientes pagantes |
|---------|-------------------------|----------------------------------------|
| Supabase | Mesmo projeto do dev local (`vwhsivwoiiicydanypmo`) | Projeto Supabase **separado** + secrets novos |
| Secrets | Copiados do `.env` local para Render | `generate_prod_secrets.py` — nunca reutilizar dev |
| WhatsApp | Não configurado | Credenciais Meta por org |

## URLs

| Serviço | URL | Notas |
|---------|-----|-------|
| API Render | https://flowia-api.onrender.com | Web Service `flowia-api` (`srv-d8if4437uimc73ammat0`) |
| Dashboard Render | https://flowia-dashboard.onrender.com | Static Site `flowia-dashboard` (`srv-d8if463tqb8s73b38rog`) |
| Supabase | https://vwhsivwoiiicydanypmo.supabase.co | Piloto: mesmo projeto do dev local |
| Webhook WhatsApp (futuro) | https://flowia-api.onrender.com/api/v1/whatsapp | Aguardando credenciais Meta |

## Smoke executado

Local (pré-deploy Render — validação dos scripts):

```powershell
venv\Scripts\python.exe scripts\smoke_prod.py --api-url http://127.0.0.1:8765
# OK: health status ok, database connected
```

Produção Render (2026-06-07):

```powershell
venv\Scripts\python.exe scripts\smoke_prod.py --api-url https://flowia-api.onrender.com --dashboard-url https://flowia-dashboard.onrender.com
venv\Scripts\python.exe scripts\smoke_agent.py --api-url https://flowia-api.onrender.com/api/v1
# OK: health + dashboard HTTP 200; RAG via chat test
# Login API: POST /api/v1/auth/login com username (não email) — 200 + cookie SameSite=None
```

Manual no browser: https://flowia-dashboard.onrender.com/login — `dono@beauty-express.com` / senha do seed local.

| # | Teste | Data | OK? |
|---|-------|------|-----|
| 1 | `/health` database connected | 2026-06-07 | Sim |
| 2 | Login org_admin (API) | 2026-06-07 | Sim (username + cookie) |
| 3 | Dashboard HTTP 200 | 2026-06-07 | Sim |
| 4 | SPA `/agenda` rewrite | 2026-06-07 | Sim (após PUT routes) |
| 5 | CRUD cliente + agendamento | | Pendente browser |
| 6 | super_admin sem rotas admin dev | | Pendente browser |

## Rollback

### API (Render)

1. Dashboard → **flowia-api** → Deploys
2. Selecionar deploy anterior estável → **Rollback**
3. Verificar `/health`

### Dashboard (Render)

1. Dashboard → **flowia-dashboard** → Deploys → Rollback
2. Ou redeploy com `VITE_*` corrigidos

### Supabase

1. Point-in-time recovery (Dashboard → Database → Backups) se migration corrompeu dados
2. **Não** rodar `seed_salon.py` em prod sem backup — sobrescreve demo org

### CORS / cookie

Sintoma: login 401/403 ou CORS no browser.

1. `ALLOWED_ORIGINS` na API = URL **exata** do Static Site (HTTPS, sem trailing slash inconsistente)
2. `COOKIE_SECURE=true` na API (cookie `SameSite=None` + `Secure` para subdomínios Render distintos)
3. `VITE_API_URL` no build = `https://flowia-api.onrender.com/api/v1`
4. Redeploy dashboard após corrigir `VITE_*`

## Supabase migrations (aplicadas)

Todas as 17 migrations do repo foram sincronizadas via `scripts/apply_migrations.py` (Jun/2026).

Verificar: `python scripts/list_db_migrations.py`

## Contatos / credenciais

- org_admin piloto: `dono@beauty-express.com` (Beauty Express org)
- super_admin plataforma: `admin@flowia.com` (setup local)

Secrets: Render Environment (sync off) — nunca commitar.
