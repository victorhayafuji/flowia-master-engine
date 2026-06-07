# Deployments

Templates de ambiente por **instância**, não por salão cliente.

| Pasta | Uso |
|-------|-----|
| `multi-tenant/` | SaaS compartilhado — vários salões, um Supabase |
| `tenants/{slug}/` | Cliente dedicado — Supabase e WhatsApp próprios, mesmo binário |

```bat
start_flowia.bat
start_flowia.bat tenants\beauty-express
```

Ou execute `start.bat` dentro de cada pasta de deploy.
