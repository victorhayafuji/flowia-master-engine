# Clinic product line (futuro)

Produto separado para clínicas médicas e odontológicas. **Não implementado no MVP salão.**

## Estrutura prevista

```
apps/clinic/
├── api/main.py
├── dashboard/
├── prompts/          # paciente, prontuário, convênio
└── seeds/            # KB clínica, mocks dental/medical
```

## Reutiliza

- `packages/engine` (LangGraph)
- `packages/lakehouse`
- `packages/scheduling`
- `packages/auth_core`

## Ativação futura

1. `PRODUCT_LINE=clinic`
2. Reativar `vertical` dental/medical na API de criação de org
3. Mover mocks legados de `scratch/mocks/dental` e `medical` para `apps/clinic/seeds`
