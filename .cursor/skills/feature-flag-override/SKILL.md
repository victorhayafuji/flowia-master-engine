---
name: feature-flag-override
description: Use ao ligar/desligar funcionalidades ou aplicar padrões repetitivos do negócio — soft-delete via is_active, config por org em organizations.settings (JSONB), PRODUCT_LINE, gating de rota com AdminDevRoute, e scaffolding de UI Neo-Swiss Brutalism (card-brutal). Engatilhar quando o usuário falar em feature flag, toggle, ligar/desligar, ativar/desativar ou padronizar UI/CRUD.
disable-model-invocation: true
---

# Feature Flag / Override

FlowIA não tem um sistema formal de feature flags. Os "toggles" reais são: `is_active` (soft-delete), `organizations.settings` (JSONB por org), `PRODUCT_LINE` (env), e gating de rota via `AdminDevRoute`. Padrão de UI: Neo-Swiss Brutalism. Fonte: `CLAUDE.md` §14 (integridade), §4 (regras), §31 (design).

## Passo a passo

1. **Desligar entidade de negócio = soft-delete.** Nunca hard delete em `patients`, `professionals`, `service_catalog`, `organizations`. Set `is_active = false`. Listagens filtram `is_active=true` por padrão (`?include_inactive=true` para incluir); `DELETE` faz deactivate.
2. **Flag por org = `organizations.settings` (JSONB).** Leia sempre com default seguro; não quebre orgs sem a chave.
3. **Comportamento por produto = `PRODUCT_LINE`** (`salon` ativo; `clinic` futuro). Não fork de código; gate por env.
4. **Rota dev/admin = `AdminDevRoute`** (`super_admin` + `import.meta.env.DEV`). Toda rota de plataforma (Data Lake, Chat Test) fica dentro dela.
5. **UI nova** usa tokens Neo-Swiss Brutalism: `card-brutal`, `radius: 0`, alto contraste, ícones `lucide-react`. Tokens em `src/index.css`. Não introduzir cantos arredondados nem estilos ad-hoc.

## Certo

```sql
-- Desativar serviço (soft-delete), preservando histórico/FKs
UPDATE service_catalog SET is_active = false WHERE id = :id;
```

```python
# Flag por org com default seguro
settings = organization.get("settings") or {}
if settings.get("reminders_enabled", True):
    schedule_reminder(appointment)
```

```tsx
// Rota de plataforma gated + card no padrão do design system
<Route element={<AdminDevRoute />}>
  <Route path="/admin/data-lake" element={
    <Suspense fallback={<div className="p-8 font-mono">Carregando...</div>}>
      <DataLake />
    </Suspense>
  } />
</Route>

<div className="card-brutal p-6">...</div>
```

## Errado

```sql
-- Hard delete: viola política de integridade e quebra FKs (ON DELETE RESTRICT)
DELETE FROM patients WHERE id = :id;
```

```tsx
// Rota dev exposta sem gate → org_admin/produção enxergam Data Lake
<Route path="/admin/data-lake" element={<DataLake />} />

// Estilo fora do design system (cantos arredondados, baixo contraste)
<div className="rounded-xl shadow-md bg-gray-50">...</div>
```

## Checklist

- [ ] Desligar entidade usa `is_active=false`, nunca `DELETE`?
- [ ] Flag por org lida de `settings` com default seguro?
- [ ] Rota de plataforma dentro de `AdminDevRoute`?
- [ ] UI nova usa `card-brutal` / `radius:0` (sem arredondado)?
