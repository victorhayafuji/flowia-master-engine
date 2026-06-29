# Checklist de segurança — piloto + go-live corporativo

Registro da auditoria **2026-06-08/09**. Complementa [`PRODUCTION.md`](PRODUCTION.md) e [`legal/LGPD_ONBOARDING_CHECKLIST.md`](legal/LGPD_ONBOARDING_CHECKLIST.md).

**Objetivo:** não vazar dados entre tenants; resistir a ataques básicos antes do 1º cliente pagante.

---

## Resumo executivo

| Trilha | Status | Notas |
|--------|--------|-------|
| **A — Piloto atual** | **OK** (com ressalvas P0) | 46 testes pytest; RLS OK; gaps P1 corrigidos no código |
| **B — Go-live corporativo** | **Pendente** | Requer contas Gaussix + Supabase prod separado (ação humana) |

**Ressalvas P0 antes do 1º pagante:**

1. Supabase **dev + prod compartilhados** (`vwhsivwoiiicydanypmo`) — migrar Trilha B  
2. Contas **pessoais** (Render/Supabase/OpenAI) — migrar Trilha B  
3. **`WHATSAPP_APP_SECRET` ausente em prod** — webhook POST aceita payload sem HMAC até Meta (ver A4)

---

## Trilha A — Piloto (executado)

### A1. Secrets e repositório

| # | Verificação | Resultado | Data |
|---|-------------|-----------|------|
| A1.1 | `py scripts/check_env.py` | OK | 2026-06-09 |
| A1.2 | `.env` nunca commitado (`git log -- .env` vazio) | OK | 2026-06-09 |
| A1.3 | `.gitignore`: `.env`, `.cursor/mcp.json` | OK | 2026-06-09 |
| A1.4 | `.gitignore`: `deployments/**/.env` | OK (adicionado) | 2026-06-09 |
| A1.5 | Render prod sem `VITE_DEV_*` no build | Verificar manualmente no Dashboard | Pendente |
| A1.6 | `SIM_WHATSAPP_ORG_ID` ausente em prod | Verificar manualmente no Dashboard | Pendente |

Referência rotação: [`SECRET_ROTATION.md`](SECRET_ROTATION.md)

### A2. Pytest — isolamento tenant / webhook / compliance

```powershell
py -m pytest tests/test_tenant.py tests/test_patients_api.py tests/test_catalog_api.py `
  tests/test_scheduling_api.py tests/test_chat_rag.py tests/test_webhook.py `
  tests/test_webhook_tenant.py tests/test_compliance_export.py `
  tests/test_compliance_metrics.py tests/test_lakehouse_security.py -q
```

| Resultado | Data |
|-----------|------|
| **46 passed** | 2026-06-09 |

### A3. RLS Supabase (SQL)

| Tabela | `rowsecurity` |
|--------|---------------|
| patients | true |
| appointments | true |
| organizations | true |
| professionals | true |
| service_catalog | true |

| Tabela interna | Grants anon/authenticated |
|----------------|---------------------------|
| webhook_message_dedup | **nenhum** (OK) |

Spoof manual coberto por pytest (`403` em header org ≠ JWT).

### A4. Superfície de ataque HTTP (prod)

Script: `py scripts/security_audit_http.py`

| Teste | Esperado | Resultado |
|-------|----------|-----------|
| `GET /health` | OK, sem secrets | OK |
| `GET /compliance/privacy-notice` | 200, version | OK (`2026-06`) |
| `GET /patients/` sem cookie | 401 | OK |
| `GET /webhook/whatsapp` token inválido | 403 | OK |
| `POST /webhook/whatsapp` assinatura inválida | 403 | **FAIL → 200** (sem `WHATSAPP_APP_SECRET`) |
| `POST /auth/login` 6× | 429 em alguma | OK |
| Security headers | DENY + nosniff | OK |

Render prod (confirmar no Dashboard):

- [ ] `COOKIE_SECURE=true`
- [ ] `ALLOWED_ORIGINS` = URL exata HTTPS do dashboard
- [ ] `ALLOWED_HOSTS` = hostname da API

### A5. Gaps auditados e remediação

| Gap | Antes | Depois | Status |
|-----|-------|--------|--------|
| `/metrics/tokens-daily` cross-tenant | Sem filtro org | Filtro `organization_id` via `validated_tenant_context` | **Corrigido** |
| `/lakehouse/query` cross-tenant SQL | Qualquer auth | **`admin_required`** (super_admin) | **Corrigido** |
| `/lakehouse/generate-sql` | Qualquer auth | **`admin_required`** | **Corrigido** |
| `/chat/test` abuso/custo | Sem rate limit | **30/min** por IP | **Corrigido** |
| `/chat/test` org_admin em prod | Endpoint exposto | Mitigado por rate limit; UI só DEV | **Aceito** |

Arquivos alterados:

- [`packages/engine/metrics/service.py`](../packages/engine/metrics/service.py)
- [`packages/engine/metrics_router.py`](../packages/engine/metrics_router.py)
- [`packages/lakehouse/router.py`](../packages/lakehouse/router.py)
- [`packages/engine/chat_router.py`](../packages/engine/chat_router.py)
- [`tests/test_compliance_metrics.py`](../tests/test_compliance_metrics.py)
- [`tests/test_lakehouse_security.py`](../tests/test_lakehouse_security.py)

### A5. LGPD / logs

| # | Item | Status |
|---|------|--------|
| A5.1 | Export DSAR (`flowia-dsar-v1`) | OK (fix `appointments.notes` em prod) |
| A5.2 | `PRIVACY_CONTACT_EMAIL` placeholder | Aceito no piloto; trocar antes pagante |
| A5.3 | Logs Render sem JWT/tokens | Verificação manual recomendada |

---

## Trilha B — Go-live corporativo (pendente)

Executar **após** Trilha A; **não** reutilizar secrets pessoais.

### B1. Contas Gaussix

- [ ] Render workspace corporativo + billing empresa
- [ ] Supabase org corporativa
- [ ] [OpenAI Platform](https://platform.openai.com/) — projeto/org Gaussix + billing
- [ ] (Opcional) GitHub org + transferir repo

### B2. Supabase prod

- [ ] Projeto **`flowia-prod`** (separado do dev)
- [ ] Plano **Pro**
- [ ] pgvector habilitado
- [ ] `py scripts/apply_migrations.py` → **24 migrations**
- [ ] `py scripts/generate_prod_secrets.py` → secrets novos
- [ ] Security Advisors no Dashboard Supabase

### B3. Render corporativo

- [ ] Recriar `flowia-api` (Starter), `flowia-dashboard`
- [ ] Env prod: ver tabela em [`PRODUCTION.md`](PRODUCTION.md) § LGPD
- [ ] **`WHATSAPP_APP_SECRET`** definido antes de Meta
- [ ] **`SIM_WHATSAPP_ORG_ID`** ausente
- [ ] Rotacionar `DASHBOARD_JWT_SECRET`, `DASHBOARD_API_KEY`, `OPENAI_API_KEY`

### B4. Validação pós-migração

- [ ] `py scripts/smoke_prod.py`
- [ ] `py scripts/security_audit_http.py` → webhook POST **403** com assinatura inválida
- [ ] Repetir pytest suite (46 tests)
- [ ] Desativar piloto pessoal + revogar keys antigas

---

## Critério “pronto o suficiente” (1º cliente)

```text
[x] Trilha A: pytest tenant/webhook 46/46 pass
[x] Trilha A: RLS + tabelas internas OK
[x] Trilha A: gaps P1 metrics/lakehouse/chat rate limit corrigidos
[ ] Trilha A: WHATSAPP_APP_SECRET em prod (bloqueado até Meta)
[ ] Trilha B: Supabase prod isolado + secrets corporativos novos
[ ] Trilha B: smokes + security_audit_http OK pós-migração
```

---

## Referências

- Skill Cursor: `@flowia-security`, `@security-audit`
- Tenancy: [`TENANCY_AND_SCALE.md`](TENANCY_AND_SCALE.md)
- WhatsApp: [`WHATSAPP_SETUP.md`](WHATSAPP_SETUP.md)
