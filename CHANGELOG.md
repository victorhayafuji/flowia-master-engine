# Changelog

Todas as mudanças relevantes do FlowIA Master Engine. Formato baseado em
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versionamento
[SemVer](https://semver.org/lang/pt-BR/). Processo: [`docs/RELEASING.md`](docs/RELEASING.md).

## [Unreleased]

## [1.2.0] - 2026-06-21

Dashboard financeiro + KPI por profissional, agente híbrido guiado (chat dev + WhatsApp) e uma rodada de robustez ("quebrar no meio").

### Added
- **Visão financeira** (`GET /dashboard/financial`): Faturado / A Faturar / Perda por Dia / Mês / Ano, com a regra status→categoria centralizada em `packages/scheduling/financial.py` (fonte única).
- **KPI por profissional** (`GET /dashboard/professional-kpi?date=`): atendimentos + clientes únicos do dia selecionado vs anterior vs seguinte.
- **Agente híbrido guiado** (seleção por botões, channel-agnostic): menu de entrada (Agendar × FAQ), FAQ por tópicos respondido via LLM+RAG, consentimento LGPD por botões, Voltar/Cancelar e pós-agendamento; cliente resolvido fora da conversa (telefone no WhatsApp, seletor na tela de teste); adaptador WhatsApp interativo atrás de `GUIDED_BOOKING_WHATSAPP_ENABLED`.
- **Recuperação fail-soft** do fluxo guiado: se a sessão in-memory sumir no meio (ex.: hot-reload no dev) e o cliente responder nome+telefone, o guiado reinicia e consome a resposta em vez de vazar para o LLM de texto livre.

### Fixed
- **Timezone no dashboard:** `professional-kpi` agora classifica o dia do agendamento no fuso da org (antes fatiava a string UTC → erro na virada da meia-noite); `today-board` compara `datetime` aware em vez de strings ISO com offsets diferentes (contagem `upcoming`).
- **Timezone no guiado:** o passo de data usa o fuso da org para "Hoje/Amanhã" (antes `date.today()` do servidor → deslocava 1 dia em host UTC).
- **Webhook WhatsApp:** normaliza resposta multimodal (conteúdo em lista) para texto antes de enviar, igual ao chat dev — evita cair no fallback por `AttributeError`.
- **Agendamento guiado robusto:** o passo de horário só aceita um slot ISO válido (digitação livre não vira slot corrompido) e a criação do agendamento nunca levanta exceção crua (devolve mensagem amigável) — evita turno engolido em silêncio no WhatsApp.
- **Render interativo WhatsApp:** passo "buttons" com >3 opções cai para lista (Meta limita a 3 botões) em vez de descartar opções; aviso em log quando a lista excede 10.
- **Upsert de cliente:** o fallback de select+update agora é protegido (falha → `None`, refazendo o cadastro) em vez de propagar exceção.
- **Versão única:** `FastAPI(version=...)` passa a usar `_APP_VERSION` (OpenAPI/`/health` não divergem mais).

## [1.1.0] - 2026-06-17

Primeira versão etiquetada. Consolida o MVP salão (`PRODUCT_LINE=salon`) em produção piloto.

### Added
- Plataforma SaaS multi-tenant B2B para salões: dashboard React + assistente conversacional (LangGraph + OpenAI) + base de conhecimento RAG.
- Motor de agendamento dinâmico: deriva slots de `working_hours`, `break_times`, `appointment_buffer_minutes`, `timezone` e `schedule_blocks`; anti double-booking via constraint EXCLUDE (HTTP 409).
- Motor híbrido de agendamento *deterministic-first*: routing heurístico, `booking_executor`, `intent_extractor` (LLM estruturado) e `response_composer`; reduz tokens/custo e erros de data.
- Tools LangGraph `check_availability` / `book_time` (M:N serviço↔profissional via `service_professionals`); parsing PT-BR de datas coloquiais com fail-closed em ambiguidade.
- Data Lake Medallion (Bronze→Silver→Gold, pgvector) + RAG (`search_kb`) com OCR via OpenAI Vision.
- Integração WhatsApp **self-service**: `org_admin` configura credenciais Meta na tela Configurações, com teste real na Graph API; lembretes/no-show via `WhatsAppService`.
- RBAC: `org_admin`, `professional` (agenda da própria coluna via `professional_scope`) e `super_admin` (seletor de org).
- Agenda **Operacional** (timeline) + **Semana** (por profissional); Overview today-board; observabilidade do agente (lite + técnica).
- Identidade visual GAUSSIX (dark · glass · glow).
- LGPD: consentimento no 1º contato, DSAR export/erase, retenção com purge (APScheduler), masking de PII/conteúdo.
- Stub de pagamentos (contrato NoOp + schema, desativado por flag).

### Changed
- Toolchain frontend Vite 5 → **7** (Vitest 3, plugin-react 4.7); padronização **Node 24 LTS** (CI/Render/local).
- Auth JWT migrado de `python-jose` para **PyJWT** com `algorithms=["HS256"]` fixado (defesa contra algorithm confusion).
- Gate de cobertura backend elevado de 30 → **50** (cobertura real ~71%).

### Fixed
- Correção manual de status de agendamento no dashboard com ajuste consistente de `no_show_count`.
- Drag-and-drop na timeline Operacional atualiza o horário do card; modais acima dos cards.
- Grade Semana bloqueia sábado e domingo.

### Security
- Isolamento multi-tenant por `organization_id` em toda query de negócio + guard fail-closed `_require_org_id` no caminho do agente (nunca responde sem org concreta).
- Webhook WhatsApp fail-closed: org resolvida por `phone_number_id`, mensagem descartada se não resolver.
- Defense-in-depth do agente: allowlist de tools por agente, input guard (SQL/jailbreak), envelope anti-injection no RAG.
- Testes automatizados de no-leak cross-tenant (`tests/test_agent_tenant_isolation.py`).
- Tabelas internas (checkpoints, webhook dedup) com RLS sem policies + `REVOKE` de `anon`/`authenticated`; dedup persistente de inbound.

[Unreleased]: https://github.com/victorhayafuji/flowia-master-engine/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/victorhayafuji/flowia-master-engine/releases/tag/v1.1.0
