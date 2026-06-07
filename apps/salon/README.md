# Salon product line

White-label para salões de beleza e cabeleireiros.

## Estrutura

```
apps/salon/
├── api/main.py       # uvicorn apps.salon.api.main:app
├── dashboard/        # React SPA (Vite)
├── prompts.py        # recepcionista, agendamento, suporte
└── seeds/            # orgs de referencia + mocks
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
