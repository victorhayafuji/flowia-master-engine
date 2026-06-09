# Multi-tenant SaaS — um deploy, vários salões (organization_id + RLS)

> **1 Render + 1 Supabase prod + N organizations.** Novo salão pagante = nova org no banco, **não** novo deploy.  
> Playbook: [`docs/TENANCY_AND_SCALE.md`](../../docs/TENANCY_AND_SCALE.md)

## Hosting produção (Render + Supabase)

| Componente | Onde |
|------------|------|
| API | Render Web Service — [`render.yaml`](../../render.yaml) |
| Dashboard | Render Static Site — root `apps/salon/dashboard` |
| Banco | Supabase — **recomendado** projeto separado do dev |

**Piloto Jun/2026:** mesmo Supabase do dev local — ver [`docs/PRODUCTION.md`](../../docs/PRODUCTION.md).

Guia completo: [`docs/RENDER.md`](../../docs/RENDER.md)

## Setup local

1. Copie `.env.example` para a raiz do projeto como `.env`
2. Execute `python scripts/seed_dev.py` (salão + KB + usuário demo)
3. Inicie com `start_flowia.bat` na raiz

Templates produção (não commitar secrets):

- [`.env.production.example`](.env.production.example) — API Render (`OPENAI_API_KEY`, `MODEL_NAME`, `VISION_MODEL_NAME`, `EMBEDDING_MODEL_NAME`)
- [`render-dashboard.env.example`](render-dashboard.env.example) — build Vite

## Onboarding de novo salão

Checklist completo: [`docs/TENANCY_AND_SCALE.md`](../../docs/TENANCY_AND_SCALE.md) § Onboarding.

Resumo:
1. Criar org via API (`POST /api/v1/organizations/`, `vertical=salon`)
2. Seed KB: `python scripts/seed_datalake.py --org <UUID> --ensure-org`
3. Cadastrar serviços/profissionais no catálogo
4. `python scripts/create_salon_user.py --email ... --password ... --org <UUID>`

## Supabase migrations

```bash
supabase link --project-ref <PROD_REF>
supabase db push
# ou: python scripts/apply_migrations.py
```

17 migrations em [`supabase/migrations/`](../../supabase/migrations/) — ordem em [`CLAUDE.md`](../../CLAUDE.md) §15.
