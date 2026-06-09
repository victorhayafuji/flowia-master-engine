# FlowIA — Índice de documentação

> **Fonte da verdade:** [`CLAUDE.md`](../CLAUDE.md) na raiz do repositório.  
> Em caso de divergência entre este índice e outros docs temáticos, prevalece o `CLAUDE.md`.

## Documentação canônica

| Documento | Quando usar |
|-----------|-------------|
| [**CLAUDE.md**](../CLAUDE.md) | **Sempre** — contexto completo de negócio, arquitetura, segurança, IA e ops |
| Modelos IA | [`CLAUDE.md`](../CLAUDE.md) §9 · §33 · [`ARCHITECTURE.md`](ARCHITECTURE.md) §6 | OpenAI: `gpt-4o-mini`, `gpt-4o`, `text-embedding-3-small` |
| [**TENANCY_AND_SCALE.md**](TENANCY_AND_SCALE.md) | **Novo salão pagante**, isolamento RLS, escala 200+, tier enterprise |
| [AGENTS.md](../AGENTS.md) | Operação Cursor: comandos, rules, skills |
| [README.md](../README.md) | Quick start para humanos |

## Referência temática

| Categoria | Documento | Quando usar |
|-----------|-----------|-------------|
| Arquitetura | [ARCHITECTURE.md](ARCHITECTURE.md) | Detalhe técnico (CLAUDE prevalece) |
| Negócio MVP | [SALON_BUSINESS_AUDIT.md](SALON_BUSINESS_AUDIT.md) | Personas, regras, matriz funcional |
| Tenancy & escala | [TENANCY_AND_SCALE.md](TENANCY_AND_SCALE.md) | Onboarding salão, RLS, 200+ orgs, enterprise |
| Monorepo | [MONOREPO.md](MONOREPO.md) | Produto por diretório, deploys |
| Boundaries | [PACKAGE_BOUNDARIES.md](PACKAGE_BOUNDARIES.md) | Grafo de dependências |
| Data Lake | [data-lake.md](data-lake.md) | Pipeline Medallion |
| Ops / Deploy | [STAGING.md](STAGING.md) | Checklist staging |
| Render | [RENDER.md](RENDER.md) | Deploy API + dashboard no Render |
| Produção | [PRODUCTION.md](PRODUCTION.md) | URLs, smoke, rollback |
| WhatsApp | [WHATSAPP_SETUP.md](WHATSAPP_SETUP.md) | Meta Cloud API por tenant |
| Marketing | [marketing/FLOWIA_LANDING_COPY.md](marketing/FLOWIA_LANDING_COPY.md) | Copy landing FlowIA |
| Pitch sócio | [pitch/FLOWIA_SOCIO_OUTLINE.md](pitch/FLOWIA_SOCIO_OUTLINE.md) | Deck apresentação Gaussix/FlowIA |
| Auditoria docs | [DOC_AUDIT_2026-06.md](DOC_AUDIT_2026-06.md) | Gaps documentação (Jun/2026) |
| Segurança | [SECRET_ROTATION.md](SECRET_ROTATION.md) | Rotação de credentials |
| Go-live | [SECURITY_GO_LIVE_CHECKLIST.md](SECURITY_GO_LIVE_CHECKLIST.md) | Auditoria piloto + checklist corporativo |
| Observabilidade IA | [AGENT_OBSERVABILITY.md](AGENT_OBSERVABILITY.md) | Personas, métricas lite vs plataforma |
| **LGPD / Legal** | [legal/PRIVACIDADE.md](legal/PRIVACIDADE.md) | Política de privacidade (DRAFT) |
| LGPD | [legal/ROPA.md](legal/ROPA.md) | Registro operações de tratamento |
| LGPD | [legal/DSR_RUNBOOK.md](legal/DSR_RUNBOOK.md) | Pedidos titular (export/erase) |
| LGPD | [legal/LGPD_FEATURE_CHECKLIST.md](legal/LGPD_FEATURE_CHECKLIST.md) | Checklist antes de merge |
| Futuro | [ROADMAP.md](ROADMAP.md) | Capítulos 2+ (não MVP) |
| Histórico | [archive/PLAN.md](archive/PLAN.md) | Plano de implementação executado |

## Cursor

- Rules: [`.cursor/rules/`](../.cursor/rules/)
- Skills: [`.cursor/skills/`](../.cursor/skills/)
- MCP: copiar [`.cursor/mcp.json.example`](../.cursor/mcp.json.example) → `.cursor/mcp.json` (gitignored) — Supabase read-only + Render ops
