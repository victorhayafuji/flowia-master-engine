# Multi-tenant SaaS — um deploy, vários salões (organization_id + RLS)

## Hosting produção (Render + Supabase)

| Componente | Onde |
|------------|------|
| API | Render Web Service — [`render.yaml`](../../render.yaml) |
| Dashboard | Render Static Site — root `apps/salon/dashboard` |
| Banco | Supabase prod (projeto separado do dev) |

Guia completo: [`docs/RENDER.md`](../../docs/RENDER.md)

## Setup local

1. Copie `.env.example` para a raiz do projeto como `.env`
2. Execute `python scripts/seed_dev.py` (salão + KB + usuário demo)
3. Inicie com `start_flowia.bat` na raiz

Templates produção (não commitar secrets):

- [`.env.production.example`](.env.production.example) — API Render
- [`render-dashboard.env.example`](render-dashboard.env.example) — build Vite

## Onboarding de novo salão

1. Criar org via API (`POST /api/v1/organizations/`, `vertical=salon`)
2. Seed KB: `python scripts/seed_datalake.py --org <UUID> --ensure-org`
3. Cadastrar serviços/profissionais no catálogo
4. `python scripts/create_salon_user.py --email ... --password ... --org <UUID>`

## Supabase migrations

```bash
supabase link --project-ref <PROD_REF>
supabase db push
```

13 migrations em [`supabase/migrations/`](../../supabase/migrations/) — ordem em [`CLAUDE.md`](../../CLAUDE.md) §15.
