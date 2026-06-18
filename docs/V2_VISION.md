# FlowIA v2.0 — Visão Multicanal + Inbox Humano

> **Status:** Visão estratégica / **Futuro — pós-MVP**. Sujeito ao guardrail da
> [Parte VIII do `CLAUDE.md`](../CLAUDE.md#parte-viii--futuras-implementações-não-mvp): **nada
> aqui se implementa sem aprovação explícita por onda**. A v1.1.0 permanece a baseline estável.
>
> **Fonte da verdade** continua sendo o [`CLAUDE.md`](../CLAUDE.md); este doc é o blueprint dedicado
> da v2.0 para manter o CLAUDE.md enxuto.
>
> **Última revisão:** Jun/2026.

---

## 1. Contexto e decisões

O FlowIA está em **v1.1.0 estável** (MVP salão, `PRODUCT_LINE=salon`, em produção piloto). Como
referência para uma **v2.0**, o dono forneceu capturas de tela (em `refs/img/`, fora do git) de um
**Chatwoot v4.15.1 auto-hospedado, rebrandeado como "Gaussix"** — a plataforma de atendimento
omnichannel da empresa-mãe.

**Decisões de produto (Jun/2026):**

1. **Construir nativo no dashboard do FlowIA** — **não** integrar nem depender do Chatwoot. O Gaussix
   é **somente referência visual/funcional**.
2. **Prioridade nº 1: multicanal** além do WhatsApp.
3. **Canais no escopo:** chat de site (widget), Instagram/Messenger, e-mail. (Telegram fora.)
4. **Modelo:** IA responde em todos os canais **+ inbox humano** com *takeover* real (handoff de
   verdade, não apenas a flag `patients.handoff_*` atual).

**Sequenciamento macro:** a v2.0 começa **após** o WhatsApp live ser validado (ver
[`CLAUDE.md` §36](../CLAUDE.md#36-roadmap-futuro-não-mvp), Cap. 5 — bloqueado por número Meta de
teste). A Onda 1 (refactor interno) pode ser preparada em paralelo por não mudar comportamento externo.

---

## 2. O que já temos × Chatwoot (keep / add / discard)

| Capacidade (refs Chatwoot/Gaussix) | FlowIA hoje | Decisão v2.0 |
|---|---|---|
| Inbox humano omnichannel | ❌ (handoff só seta `patients.handoff_*`) | **ADD** — maior gap |
| Multicanal (site, IG/Messenger, e-mail) | ❌ (só WhatsApp + chat test) | **ADD** — prioridade |
| IA conversacional + agendamento + RAG | ✅ LangGraph (diferencial) | **KEEP** — cérebro, reusar em todo canal |
| Domínio salão (agenda/catálogo/clientes) | ✅ | **KEEP** — diferencial vs Chatwoot genérico |
| Contatos / CRM-lite | ✅ `patients` | **KEEP/estender** (identidade por canal) |
| Etiquetas, Macros, Respostas Prontas | ❌ | **ADD (fase tardia)** — produtividade do atendente |
| CSAT / SLA / relatórios de atendimento | ⚠️ observabilidade lite | **DEFER** — não priorizado agora |
| Mensagens agendadas / campanhas | ⚠️ só lembretes/no-show | **DEFER** — sobrepõe régua da Parte VIII |
| Central de Ajuda pública (KB portal) | ❌ (RAG é interno) | **DISCARD** para MVP salão |
| Chamadas (voz / Dyte) | ❌ | **DISCARD** |
| Times / Funções personalizadas / Auditoria | parcial (RBAC) | **DISCARD/DEFER** — RBAC atual basta |
| Robôs genéricos / OpenAI nativo Chatwoot | n/a | **DISCARD** — nosso "robô" é o LangGraph |

---

## 3. Arquitetura-alvo (nativa no monorepo)

Princípio: **o motor (LangGraph) já é channel-agnostic** — quem é WhatsApp-específico é o *wrapper* de
entrada/saída. A v2.0 generaliza o perímetro de canal e adiciona persistência de conversa + UI.

### 3.1 Camadas

**1) Abstração de canal — novo pacote `packages/messaging/`** (não importa `apps/salon`):

- `channels/base.py` — interface `ChannelAdapter` (normalização inbound) + `ChannelSender` (outbound).
- `channels/whatsapp.py` — adapta o que hoje vive em `packages/integrations/webhook/` + `whatsapp.py`.
- `channels/webchat.py`, `channels/meta_social.py` (IG/Messenger), `channels/email.py`.
- **Mensagem normalizada:** `{org_id, channel, channel_identity, text, message_id, attachments?}`.
- **Tenant resolution por canal** (generaliza `resolve_org_id_from_webhook_value` em
  `packages/integrations/webhook/tenant_resolver.py`): WhatsApp = `phone_number_id`; webchat =
  `widget_token`; Meta = `page_id`/`ig_account_id`; e-mail = endereço de destino.

**2) Núcleo de processamento channel-agnostic:**

- Extrair de `process_inbound_text_message` (`packages/integrations/webhook/processor.py`) um
  `process_inbound_message(channel, org_id, channel_identity, text, message_id)`:
  input guard → consent gate → engine `ainvoke` → persistência → outbound via `ChannelSender` do canal.
- Hoje `channel="whatsapp"` é fixo (≈linhas 92 e 185); vira parâmetro. Outbound deixa de ser exclusivo
  do `WhatsAppService`.
- **Thread ID:** generalizar `build_thread_id(org_id, sender_id)` → `{org_id}:{channel}:{identity}` em
  `packages/auth_core/conversation_thread.py` (manter fallback de leitura para threads legados
  `{org_id}:{phone}` por 1 release).

**3) Persistência de conversa (inbox) — novas tabelas Supabase + RLS:**

- `channels` (ou `inboxes`): config por org/canal (`type`, credenciais, `widget_token`, `is_active`).
- `conversations`: `org_id`, `channel`, `contact_id` (→ `patients`), `status`
  (`open|pending|resolved`), `assignee_user_id` (nullable), `ai_enabled` (bool), `last_message_at`.
- `messages`: `conversation_id`, `direction` (`inbound|outbound`), `author_type`
  (`contact|ai|human`), `content`, `channel_message_id`, `created_at`.
- **Por quê:** o checkpointer do LangGraph é memória da IA, não fonte para UI de humano. Confirmado que
  não existe tabela de conversa hoje (só `conversation_metrics` + `webhook_message_dedup`).
- **LGPD:** masking/retention/DSAR precisam cobrir `messages` (estender `packages/compliance/`).

**4) Handoff real (takeover):**

- Reaproveitar o estado `handoff_requested` + lógica de *silent mode*/`/resume` que já existe no
  processor (≈linhas 104–136) e em `session_store.py`.
- Novo: ao humano assumir no inbox, setar `conversations.ai_enabled=false` + `assignee_user_id`; a IA
  para de responder naquela conversa; humano envia pelo mesmo `ChannelSender`.

**5) UI — nova feature `apps/salon/dashboard/src/features/inbox/`:**

- Lista de conversas (filtros por canal/status/atribuição), thread view, composer, botão
  "assumir / devolver para IA", etiquetas. Estilo GAUSSIX (dark/glass/glow) já existente.
- Rota protegida; visível para `org_admin`/`super_admin`; `professional` vê só conversas atribuídas a si
  (reusar `professional_scope`).
- Tempo real: começar com **polling** (simples); WebSocket/SSE como melhoria posterior.

### 3.2 Boundaries (respeitar `CLAUDE.md` §10/§11)

`messaging` depende de `engine, auth_core, compliance`; **não** importa `apps/salon`. Routers novos
registrados só em `apps/salon/api/app_factory.py` com prefixo `/api/v1`. O `integrations/webhook` atual
passa a ser um adapter fino sobre `messaging`.

---

## 4. Ondas de implementação (what / when / how / steps)

**Onda 0 — Documentação** (este doc + ponteiro no `CLAUDE.md`): **concluída** ao publicar este arquivo.
Sem migrations, endpoints ou UI. Mantém v1.1.0 intacta.

**Onda 1 — Abstração de canal** (refactor interno, comportamento idêntico):
- `packages/messaging/channels/base.py` (interfaces) + mover WhatsApp para `channels/whatsapp.py`.
- Extrair `process_inbound_message(channel=...)`; WhatsApp vira chamador.
- Generalizar `build_thread_id` → `{org_id}:{channel}:{identity}` com fallback de leitura.
- **Verificação:** suíte adversarial + smokes WhatsApp/chat-test verdes; nenhum comportamento muda.

**Onda 2 — Persistência + Inbox** (núcleo do valor):
- Migrations `channels`, `conversations`, `messages` + RLS por `organization_id`.
- Persistir toda inbound/outbound (inclusive o WhatsApp atual) em `messages`.
- Feature `features/inbox/` no dashboard (lista + thread + polling, read-only primeiro).
- Estender `packages/compliance/` (export/erase/retention) para `messages`.

**Onda 3 — Takeover humano:**
- `conversations.ai_enabled` + atribuição; botão assumir/devolver; humano responde pelo `ChannelSender`.
- Reusar `handoff_requested`/`/resume`/`session_store`.

**Onda 4 — Canal Chat de Site (widget):**
- `channels/webchat.py` + endpoint público de ingestão por `widget_token` (rate-limited, fail-closed).
- Snippet embutível + identidade por sessão anônima (vira `patients` ao coletar contato).
- Primeiro canal 100% nosso, sem aprovação de terceiros — valida a stack ponta a ponta.

**Onda 5 — Instagram / Messenger (Meta):**
- `channels/meta_social.py`; webhook Meta (page/IG), assinatura HMAC, resolução por
  `page_id`/`ig_account_id`. Reusa o ecossistema Meta do WhatsApp; requer permissões adicionais.

**Onda 6 — E-mail:**
- `channels/email.py` (IMAP/SMTP ou provedor tipo Postmark/SES); threading por `Message-ID`/`In-Reply-To`.
- Fluxo assíncrono (não tempo-real); bom para suporte.

**Ondas posteriores (DEFER, só se pedido):** etiquetas/macros/respostas prontas; CSAT/SLA; campanhas.

---

## 5. Riscos e mitigação

- **Regressão no MVP estável** → Onda 1 é refactor com comportamento idêntico, guardado por suíte
  adversarial + smokes; nada de UI/schema nas Ondas 0–1.
- **LGPD (mensagens = PII)** → masking nos logs (padrão 15 chars já existe); retention/DSAR cobrindo
  `messages` antes de produção; revisar [`legal/ROPA.md`](legal/ROPA.md) antes da Onda 2.
- **Escala / tempo-real** → polling primeiro; rate limiting hoje é in-process
  ([`CLAUDE.md` §48.3](../CLAUDE.md#483-rate-limiting-distribuído-pré-requisito-de-scale1)) —
  reavaliar antes de `scale>1`.
- **Custo de IA multicanal** → `conversations.ai_enabled` permite desligar IA por conversa/canal;
  métricas por `channel` já existem em `conversation_metrics`.
- **Webhooks de terceiros (Meta/e-mail)** → fail-closed na resolução de tenant (padrão atual do WhatsApp).

## 6. Verificação (por onda, ao executar)

- **Onda 1:** `py -3.12 -m pytest -m "not llm_behavior" -q` + `scripts/run_adversarial_matrix.py` +
  smokes WhatsApp/chat-test verdes.
- **Onda 2+:** testes de RLS/tenant nas tabelas novas (espelhar `tests/test_agent_tenant_isolation.py`),
  E2E Playwright do inbox, DSAR export/erase incluindo `messages`.
- **Canais novos:** simulador de webhook por canal (espelhar `scripts/simulate_whatsapp_webhook.py`).

---

*FlowIA Master Engine — blueprint v2.0 (futuro). Prevalece o [`CLAUDE.md`](../CLAUDE.md).*
