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
| 6 | conversation_metrics | thread_id, sender_id, tokens | Cliente | Telemetria | Legítimo interesse | 365 dias | RLS tenant |
| 7 | Dashboard auth | E-mail, hash senha | Funcionário salão | Acesso painel | Contrato | Conta ativa | JWT HttpOnly, bcrypt |
| 8 | Data Lake upload | Docs KB | Salão | RAG | Contrato | Contrato tenant | PII mask query, sem anon browser |
| 9 | Lembretes WhatsApp | Tel, horário consulta | Cliente | Lembrete | Contrato | Até envio + logs | Scheduler tenant |
| 10 | Handoff humano | Motivo, timestamp | Cliente | Suporte | Contrato | Enquanto patient ativo | patients.handoff_* |
| 11 | Consentimento LGPD | Versão aviso, timestamps | Cliente | Conformidade | Obrigação legal | Enquanto patient + legal | patients.privacy_* |

**Responsável operacional:** equipe Gaussix · **Revisão:** a cada release com dados novos (ver [`LGPD_FEATURE_CHECKLIST.md`](LGPD_FEATURE_CHECKLIST.md))
