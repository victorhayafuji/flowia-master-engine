# Auditoria de documentação — Jun/2026

> Relatório da auditoria doc × runtime. **Correções aplicadas** na mesma rodada (Jun/2026).  
> Fonte da verdade: [`CLAUDE.md`](../CLAUDE.md) · Índice: [`README.md`](README.md)

## Resumo

| Métrica | Antes | Depois |
|---------|-------|--------|
| Arquivos `.md` + rules + skills auditados | 44 | 44 |
| Gaps P0 (CLAUDE) | 8 | **0** |
| Gaps P1 (ops/deploy) | 10 | **0** (smoke browser 5–6 ainda pendente operacionalmente) |
| Gaps P2 (Cursor) | 4 | **0** |
| Gaps P3 (legado) | 9 | **0** |

## Matriz por arquivo

| Arquivo | Status antes | Status depois |
|---------|--------------|---------------|
| `CLAUDE.md` | Gap menor | **OK** (v1.3) |
| `AGENTS.md` | Gap menor | **OK** |
| `README.md` | Desatualizado | **OK** |
| `docs/README.md` | Gap menor | **OK** |
| `docs/ARCHITECTURE.md` | Gap menor | **OK** |
| `docs/MONOREPO.md` | Gap menor | **OK** |
| `docs/PACKAGE_BOUNDARIES.md` | OK | OK |
| `docs/SALON_BUSINESS_AUDIT.md` | OK | OK |
| `docs/data-lake.md` | OK | OK |
| `docs/STAGING.md` | Gap menor | **OK** |
| `docs/RENDER.md` | Desatualizado | **OK** |
| `docs/PRODUCTION.md` | Gap menor | **OK** |
| `docs/SECRET_ROTATION.md` | Gap menor | **OK** |
| `docs/ROADMAP.md` | Legado parcial | **OK** (Cap. 5 webhook URL) |
| `docs/PLAN.md` | OK | OK |
| `deployments/README.md` | Gap menor | **OK** |
| `deployments/multi-tenant/README.md` | Gap menor | **OK** |
| `deployments/multi-tenant/RENDER_CHECKLIST.md` | Desatualizado | **OK** |
| `deployments/tenants/beauty-express/README.md` | OK | OK |
| `packages/README.md` + 6 filhos | Desatualizado | **OK** |
| `apps/salon/README.md` | Gap menor | **OK** |
| `apps/salon/dashboard/README.md` | Legado | **OK** |
| `apps/clinic/README.md` | OK | OK |
| `knowledge/flowia_knowledge.md` | Legado | **OK** (banner marketing) |
| `.cursor/rules/*.mdc` (5) | OK | OK |
| `.cursor/skills/*` (8) | Gap menor | **OK** |

## Gaps corrigidos por eixo

### API / auth

- CLAUDE §13: DELETE soft-delete documentados
- CLAUDE §16: `username`, `SameSite=None`, fluxo login frontend
- ARCHITECTURE + flowia-salon-domain: auth prod alinhado

### Deploy / produção

- URLs reais em RENDER, PRODUCTION, README
- Piloto vs Supabase separado documentado (STAGING, PRODUCTION, multi-tenant README)
- SECRET_ROTATION: passo Render Environment
- RENDER_CHECKLIST: status Jun/2026 concluído

### Scripts ops

- CLAUDE §35 + AGENTS + flowia-dev: `smoke_agent`, `test_rag_chat`, `list_db_migrations`, `mark_migration_applied`

### IA / LangGraph

- CLAUDE §39: dívida triage → scheduling registrada
- ROADMAP Cap. 5: webhook prod URL + nota setup futuro

### MCP / Cursor

- CLAUDE §38, AGENTS, docs/README: `mcp.json.example` (gitignored)

### Legado

- Removidas referências `src/*` dos READMEs de `packages/`
- Dashboard README substituído (Vite boilerplate → FlowIA)
- `knowledge/flowia_knowledge.md` marcado como marketing

## Pendências operacionais (não são gaps de doc)

| Item | Onde registrado |
|------|-----------------|
| Smoke browser CRUD + admin dev (#5–6) | `docs/PRODUCTION.md` |
| Supabase prod separado do dev | `docs/PRODUCTION.md`, RENDER_CHECKLIST |
| WhatsApp Meta API | ROADMAP Cap. 5, CLAUDE §36 — doc `WHATSAPP_SETUP.md` futuro |
| Triage agendamento via chat | CLAUDE §39 dívida aberta |

## Validação pós-correção

- [x] Grep: nenhum `packages/*/README.md` com `**Atual:** src/`
- [x] URLs consistentes: PRODUCTION = RENDER = `.env.production.example`
- [x] CLAUDE §40 versionamento 1.3 registrado
- [x] 13 migrations §15 = disco

## Recomendações futuras

1. Completar smoke manual browser (PRODUCTION #5–6)
2. Migrar para Supabase prod dedicado antes de clientes pagantes
3. Criar `docs/WHATSAPP_SETUP.md` quando credenciais Meta estiverem disponíveis
4. Corrigir dívida triage → scheduling no código (CLAUDE §39)

## Follow-up Jun/2026 — tenancy

- [x] [`docs/TENANCY_AND_SCALE.md`](TENANCY_AND_SCALE.md) — playbook multi-tenant, onboarding, escala 200+, tier enterprise
- [x] CLAUDE §2, §34, §37, ADR, v1.4

---

*Auditoria executada Jun/2026 — correções aplicadas no mesmo PR/sessão.*
