# FlowIA — Índice de documentação

> **Fonte da verdade:** [`CLAUDE.md`](../CLAUDE.md) na raiz do repositório.  
> Em caso de divergência entre este índice e outros docs temáticos, prevalece o `CLAUDE.md`.

## Documentação canônica

| Documento | Quando usar |
|-----------|-------------|
| [**CLAUDE.md**](../CLAUDE.md) | **Sempre** — contexto completo de negócio, arquitetura, segurança, IA e ops |
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
| Auditoria docs | [DOC_AUDIT_2026-06.md](DOC_AUDIT_2026-06.md) | Gaps documentação (Jun/2026) |
| Segurança | [SECRET_ROTATION.md](SECRET_ROTATION.md) | Rotação de credentials |
| Futuro | [ROADMAP.md](ROADMAP.md) | Capítulos 2+ (não MVP) |
| Histórico | [archive/PLAN.md](archive/PLAN.md) | Plano de implementação executado |

## Cursor

- Rules: [`.cursor/rules/`](../.cursor/rules/)
- Skills: [`.cursor/skills/`](../.cursor/skills/)
- MCP: copiar [`.cursor/mcp.json.example`](../.cursor/mcp.json.example) → `.cursor/mcp.json` (gitignored) — Supabase read-only + Render ops
