# Tenant dedicado — Beauty Express

Deploy **isolado** para cliente **enterprise**: banco e WhatsApp próprios, **sem fork de código**.

> **Não é o padrão para salões SMB.** Para escala (200+ salões no mesmo prod), use SaaS compartilhado — [`docs/TENANCY_AND_SCALE.md`](../../docs/TENANCY_AND_SCALE.md).

## Uso

```bat
start_flowia.bat tenants\beauty-express
```

Isso copia este `.env.example` para a raiz (se `.env` não existir) e inicia backend + dashboard salão.

## Branding (opcional)

Coloque assets em `branding/` (logo, favicon). Integração com CSS vars pode ser feita na Fase 2.
