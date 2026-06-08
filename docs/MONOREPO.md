# Monorepo — produto por diretório

## Princípio

| Escopo | Onde vive | Exemplo |
|--------|-----------|---------|
| Motor compartilhado | `packages/` | LangGraph, lakehouse, scheduling |
| Produto salão | `apps/salon/` | prompts, seeds, dashboard, api |
| Landing marketing | `apps/landing/` | site público FlowIA (sem auth) |
| Produto clínica | `apps/clinic/` (futuro) | prompts clínicos, UI pacientes |
| Deploy compartilhado | `deployments/multi-tenant/` | SaaS multi-tenant |
| Cliente dedicado | `deployments/tenants/{slug}/` | só `.env` + branding |

**Não** duplicar código por salão cliente — usar `organization_id` + RLS. Ver [`docs/TENANCY_AND_SCALE.md`](TENANCY_AND_SCALE.md).

## Mapa módulos → pacotes

| Escopo | Pacote |
|--------|--------|
| Auth, config, tenant | `packages/auth_core` |
| LangGraph / chat | `packages/engine` |
| Data lake | `packages/lakehouse` |
| Agendamento | `packages/scheduling` |
| WhatsApp | `packages/integrations` |
| Catálogo / clientes | `apps/salon/domain` |
| Composition root | `apps/salon/api` |

## Configuração

```env
PRODUCT_LINE=salon
```

## Comandos

```bash
# Local (Windows)
start_flowia.bat
start_flowia.bat tenants\beauty-express

# Produção Render — Blueprint
# render.yaml na raiz; guia: docs/RENDER.md
```

## Deploy produção

| Ambiente | Como |
|----------|------|
| Local | `start_flowia.bat` |
| SaaS multi-tenant | [`render.yaml`](../render.yaml) + [`docs/TENANCY_AND_SCALE.md`](../docs/TENANCY_AND_SCALE.md) |
| Tenant dedicado | `deployments/tenants/{slug}/` + mesmo binário |

## Entrypoints

- API raiz: `main.py`
- API salão: `apps/salon/api/main.py`
- Dashboard salão: `apps/salon/dashboard/` (único frontend; não existe `dashboard/` na raiz)
