# Monorepo — produto por diretório

## Princípio

| Escopo | Onde vive | Exemplo |
|--------|-----------|---------|
| Motor compartilhado | `packages/` | LangGraph, lakehouse, scheduling |
| Produto salão | `apps/salon/` | prompts, seeds, dashboard, api |
| Produto clínica | `apps/clinic/` (futuro) | prompts clínicos, UI pacientes |
| Deploy compartilhado | `deployments/multi-tenant/` | SaaS multi-tenant |
| Cliente dedicado | `deployments/tenants/{slug}/` | só `.env` + branding |

**Não** duplicar código por salão cliente — usar `organization_id` + RLS.

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
# Deploy padrão (multi-tenant)
start_flowia.bat

# Instância dedicada demo
start_flowia.bat tenants\beauty-express
```

## Entrypoints

- API raiz: `main.py`
- API salão: `apps/salon/api/main.py`
- Dashboard salão: `apps/salon/dashboard/` (único frontend; não existe `dashboard/` na raiz)
