# Produção — URLs, smoke e rollback

Registro operacional pós-deploy. Preencher após o dia D.

## URLs (preencher)

| Serviço | URL | Notas |
|---------|-----|-------|
| API Render | | Web Service `flowia-api` |
| Dashboard Render | | Static Site `flowia-dashboard` |
| Supabase prod | | Projeto separado do dev |

## Smoke executado

Local (pré-deploy Render — validação dos scripts):

```powershell
venv\Scripts\python.exe scripts\smoke_prod.py --api-url http://127.0.0.1:8765
# OK: health status ok, database connected
```

Produção Render (preencher após deploy):

```powershell
venv\Scripts\python.exe scripts\smoke_prod.py --api-url https://flowia-api.onrender.com --dashboard-url https://flowia-dashboard.onrender.com
```

| # | Teste | Data | OK? |
|---|-------|------|-----|
| 1 | `/health` database connected | | |
| 2 | Login org_admin | | |
| 3 | Páginas dashboard sem CORS | | |
| 4 | CRUD cliente + agendamento | | |
| 5 | super_admin sem rotas admin dev | | |

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
2. `COOKIE_SECURE=true` na API
3. `VITE_API_URL` no build = `https://API.onrender.com/api/v1`
4. Redeploy dashboard após corrigir `VITE_*`

## Supabase migrations (aplicadas)

Todas as 13 migrations do repo foram sincronizadas via `scripts/apply_migrations.py` (Jun/2026).

Verificar: `python scripts/list_db_migrations.py`

## Contatos / credenciais

- org_admin piloto: *(email definido no create_salon_user.py)*
- super_admin plataforma: *(email definido no setup_dev_env.py)*

Secrets: Render Environment (sync off) — nunca commitar.
