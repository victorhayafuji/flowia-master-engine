# Auditoria de negócio — MVP Salão

Produto white-label para salões de beleza e cabeleireiros. Multi-tenant por `organization_id`.

## Personas

| Persona | Papel | O que vê |
|---------|-------|----------|
| Dono / funcionário | `org_admin` | Agenda, Clientes, Catálogo, Visão Geral — **sem** Data Lake, Chat Test, seletor de salão |
| Operador plataforma | `super_admin` | Mesmo dashboard salão + seletor de org (só `vertical=salon`) |
| Dev local | `super_admin` + `import.meta.env.DEV` | Rotas extras `/admin/data-lake`, `/admin/chat-test` |

## Regras de negócio aceitas

### Agendamento
- Serviço tem nome, duração e preço; profissional executa (vínculo `service_catalog.professional_id`).
- Cliente identificado por nome + telefone (tabela `patients`, UI "Clientes").
- Horário comercial 09:00–18:00; slots de 30 min; conflito → erro 409.
- Criação via dashboard ou agente `scheduling` (`check_availability` → `book_time`).
- Reagendamento (drag) passa por checagem de conflito.

### Atendimento WhatsApp / chat
- **Recepcionista:** preços, serviços, horários — sempre `search_kb` antes de inventar.
- **Suporte:** políticas (cancelamento, atraso, pagamento).
- **Agendamento:** fluxo obrigatório com ferramentas; handoff humano via `request_human_handoff`.
- Sem CRM B2B / leads BANT no MVP salão.

### Base de conhecimento
- Upload e pipeline Data Lake alimentam RAG (`search_kb`).
- Dono do salão não gerencia pipeline — operador/dev em `/admin/data-lake`.

### Multi-tenant
- Isolamento por `organization_id` + RLS (`dashboard_users.organization_id`).
- `org_admin` não pode trocar tenant via header.

## Matriz funcionalidade × ação

| Funcionalidade | Dono salão | Super admin | Ação |
|----------------|------------|-------------|------|
| Visão Geral (agenda hoje, clientes, próximos) | Sim | Sim | Manter |
| Agenda | Sim | Sim | Manter |
| Clientes | Sim | Sim | Manter (API `/patients`) |
| Catálogo | Sim | Sim | Manter |
| Data Lake | Não | Dev only | Esconder da nav |
| Chat Test | Não | Dev only | Esconder da nav |
| KPIs tokens/custo IA | Não | Dev only | Removido da Overview |
| CRM leads / SDR | Não | Não | Desativado (`PRODUCT_LINE=salon`) |
| Prontuário clínico | Não | Não | Removido da UI |

## Arquivos principais

| Área | Caminho |
|------|---------|
| Prompts salão | `apps/salon/prompts.py` |
| Agentes / LangGraph | `packages/engine/` |
| Agendamento | `packages/scheduling/` |
| Dashboard | `apps/salon/dashboard/` |
| Seeds | `scripts/seed_salon.py`, `scripts/seed_dev.py` |
| Config produto | `PRODUCT_LINE=salon` em `.env` |

## Checklist de validação manual

1. [x] Login `org_admin` — sem seletor "Salão ativo", nav sem Data Lake/Chat Test _(E2E: `e2e/auth-nav.spec.ts`)_
2. [x] Criar cliente em Clientes _(E2E: `e2e/patients.spec.ts`; API: `tests/test_patients_api.py`)_
3. [x] Criar agendamento na Agenda _(E2E: `e2e/agenda.spec.ts`; API: `tests/test_scheduling_api.py`)_
4. [x] Catálogo: serviço com profissional vinculado _(E2E: `e2e/catalog.spec.ts`; API: `tests/test_catalog_api.py`)_
5. [x] Dev: Chat Test — "quanto custa corte feminino" retorna preço da KB _(E2E: `e2e/chat-test-rag.spec.ts`)_
6. [x] Dev: Chat Test — "quero agendar…" → horários + confirmação _(E2E: `e2e/chat-test-scheduling.spec.ts`)_
7. [x] `pytest` e `npm test` verdes _(CI: `.github/workflows/ci.yml`)_

## Legado fora do MVP salão

- Tabela `leads`, tool `save_lead_to_db` — desativados (`PRODUCT_LINE=salon`)
- Endpoint `/dashboard/crm-leads` — removido
- Agentes `sdr`, `lakehouse_query` (normalizados para recepcionista)
- Verticals `dental`, `medical` no banco (futuro `apps/clinic`)
- Handoff WhatsApp persiste em `patients.handoff_requested_at` / `handoff_reason` (via `legacy_sender_id`)
