# ROPA — Registro das Operações de Tratamento

> Inventário interno Gaussix / FlowIA. Atualizar ao adicionar nova feature que trate dados pessoais.

**Referência:** LGPD Art. 37 · **Versão:** 2026-06

| # | Operação | Dados | Titular | Finalidade | Base legal | Retenção | Medidas |
|---|----------|-------|---------|------------|------------|----------|---------|
| 1 | Cadastro cliente (dashboard) | Nome, tel, e-mail | Cliente do salão | CRM salão | Contrato (salão) | Contrato + legal | RLS, soft delete |
| 2 | Agendamento | Horário, serviço, profissional | Cliente | Agenda | Contrato | Idem agendamentos | Overlap guard, tenant |
| 3 | WhatsApp inbound/outbound | Mensagens, telefone | Cliente | Atendimento IA | Contrato + consentimento aviso | Checkpoints 90d; metrics 365d | Log mask, dedup 7d |
| 4 | Chat test (dev) | Mensagens, thread UUID | Operador dev | Testes | Legítimo interesse interno | Idem #3 | AdminDevRoute |
| 5 | LangGraph checkpoints | Histórico conversa | Cliente | Contexto IA | Contrato | 90 dias (purge job) | Internal RLS, backend-only |
| 6 | conversation_metrics | thread_id (`org:telefone`), sender_id **mascarado** (`***1234`), tokens | Cliente | Telemetria | Legítimo interesse | 365 dias | RLS tenant; `sender_id` minimizado na fonte (`mask_sender_id`); `thread_id` carrega `org:telefone` como **chave de correlação** do DSAR (export/erase/purge filtram por `thread_id`) — pseudônimo, eliminável via DSAR/retenção |
| 7 | Dashboard auth | E-mail, hash senha | Funcionário salão | Acesso painel | Contrato | Conta ativa | JWT HttpOnly, bcrypt |
| 8 | Data Lake upload | Docs KB | Salão | RAG | Contrato | Contrato tenant | PII mask query, sem anon browser |
| 9 | Lembretes WhatsApp | Tel, horário consulta | Cliente | Lembrete | Contrato | Até envio + logs | Scheduler tenant |
| 10 | Handoff humano | Motivo, timestamp | Cliente | Suporte | Contrato | Enquanto patient ativo | patients.handoff_* |
| 11 | Consentimento LGPD | Versão aviso, timestamps | Cliente | Conformidade | Obrigação legal | Enquanto patient + legal | patients.privacy_* |
| 12 | Notificação de handoff via Slack | Telefone **mascarado** (`***1234`), motivo truncado | Cliente | Alerta operacional (transferência humana) | Legítimo interesse | Conforme retenção do Slack (subprocessador) | Telefone mascarado antes do envio (`mask_sender_id`), motivo truncado |
| 13 | Fila inbound WhatsApp (`whatsapp_inbound_jobs`) | sender_id (telefone), payload da mensagem | Cliente | Processamento assíncrono/serialização do inbound | Contrato + consentimento aviso | **A definir** — sem purge automático hoje | Tabela interna RLS sem policies, backend-only |
| 14 | Lacunas de conhecimento (`knowledge_gaps`) | Pergunta do cliente (texto), tipo de agente | Cliente | Observabilidade RAG (perguntas sem resposta) | Legítimo interesse | **A definir** — sem purge automático hoje | RLS tenant, captura fail-soft |

**Responsável operacional:** equipe Gaussix · **Revisão:** a cada release com dados novos (ver [`LGPD_FEATURE_CHECKLIST.md`](LGPD_FEATURE_CHECKLIST.md))
