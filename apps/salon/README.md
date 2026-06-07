# Salon product line

White-label para salões de beleza e cabeleireiros.

**Handbook:** [`CLAUDE.md`](../../CLAUDE.md) · **Deploy:** [`docs/RENDER.md`](../../docs/RENDER.md)

## Estrutura

```
apps/salon/
├── api/app_factory.py   # composition root (via main.py)
├── dashboard/           # React SPA (Vite)
├── domain/              # catálogo + clientes
├── prompts.py           # recepcionista, agendamento, suporte
└── seeds/               # orgs de referência + mocks
```

## Desenvolvimento

```bat
start_flowia.bat
```

Ou manualmente:

```bash
python -m uvicorn main:app --reload
cd apps/salon/dashboard && npm run dev
```

## Produção

- Dashboard: https://flowia-dashboard.onrender.com
- API: https://flowia-api.onrender.com
- Ops: [`docs/PRODUCTION.md`](../../docs/PRODUCTION.md)
