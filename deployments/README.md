# Deployments

Templates de ambiente por **instância da plataforma**, não por salão cliente SMB.

**Playbook completo:** [`docs/TENANCY_AND_SCALE.md`](../docs/TENANCY_AND_SCALE.md)

## Árvore de decisão

```text
Novo salão SMB assinou?
  → SaaS compartilhado: criar organization no Supabase prod (sem pasta nova aqui)
  → Guia: deployments/multi-tenant/ + docs/TENANCY_AND_SCALE.md

Cliente enterprise exige Supabase/host isolado?
  → deployments/tenants/{slug}/ + precificação premium
```

| Pasta | Uso | Quantidade em escala |
|-------|-----|----------------------|
| `multi-tenant/` | **Padrão** — 1 Render + 1 Supabase, N salões (`organization_id`) | 1 template plataforma |
| `tenants/{slug}/` | **Enterprise** — Supabase dedicado por contrato | 1 pasta por cliente premium |

**Produção SaaS:** [`render.yaml`](../render.yaml) + [`docs/RENDER.md`](../docs/RENDER.md)

```bat
start_flowia.bat
start_flowia.bat tenants\beauty-express
```

Ou execute `start.bat` dentro de cada pasta de deploy.
