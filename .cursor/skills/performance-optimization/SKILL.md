---
name: performance-optimization
description: Use ao otimizar performance — bundle do dashboard (dynamic imports / lazy loading) ou queries pesadas no backend (N+1, falta de filtro batch, lógica pesada em loop). Engatilhar quando o usuário falar em performance, otimizar, lento, bundle, N+1 ou query lenta.
disable-model-invocation: true
---

# Performance Optimization

Foco em duas frentes: **bundle frontend** (Vite/React) e **queries backend** (Supabase).

## Frontend (bundle / lazy)

1. Páginas de rota são carregadas com `React.lazy` + `Suspense` em `apps/salon/dashboard/src/App.tsx`. Toda página nova de rota entra como lazy, não import estático no topo.
2. Não faça trabalho síncrono pesado no render — memoize (`useMemo`/`useCallback`) ou mova para fora do componente.
3. Centralize chamadas de API em `@/shared/lib/api` (não recriar clients).
4. Mantenha libs pesadas (ex.: `@dnd-kit`, charts) dentro de páginas lazy para não inflar o chunk inicial.

### Certo

```tsx
const Agenda = lazy(() => import("./pages/Agenda").then(m => ({ default: m.Agenda })))

<Route path="/agenda" element={
  <Suspense fallback={<div className="p-8 font-mono">Carregando...</div>}>
    <Agenda />
  </Suspense>
} />
```

### Errado

```tsx
import { Agenda } from "./pages/Agenda"  // entra no chunk inicial, infla o bundle
<Route path="/agenda" element={<Agenda />} />
```

## Backend (queries)

1. Evite N+1: busque em lote com `.in_()` em vez de uma query por item.
2. Selecione só as colunas necessárias com `.select("col_a, col_b")` — evite `select("*")` em listagens.
3. Empurre filtros para o banco (`.eq`, `.in_`, range), não para loops em Python.
4. Lógica de acesso a dados fica no repository layer (`apps/salon/domain`), com `organization_id` do tenant atual.

### Certo

```python
ids = [a["patient_id"] for a in appointments]
patients = (
    client.table("patients")
    .select("id, name")
    .eq("organization_id", org_id)
    .in_("id", ids)            # uma query em lote
    .execute()
)
```

### Errado

```python
patients = []
for a in appointments:        # N+1: uma query por agendamento
    p = client.table("patients").select("*").eq("id", a["patient_id"]).execute()
    patients.append(p.data[0])
```

## Checklist

- [ ] Página de rota nova é lazy + Suspense?
- [ ] Sem `select("*")` em listagens; só colunas usadas?
- [ ] Sem N+1 — uso de `.in_()` para lotes?
- [ ] Filtro feito no banco, não em loop Python?
