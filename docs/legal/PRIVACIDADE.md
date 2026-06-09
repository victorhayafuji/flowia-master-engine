# Política de Privacidade — FlowIA

> **DRAFT — rascunho técnico.** Não substitui assessoria jurídica. Revisar com advogado antes de publicação comercial.

**Versão:** 2026-06 · **Última atualização:** Jun/2026  
**Controladora do produto:** Gaussix Tecnologia (operadora SaaS)  
**Contato privacidade:** configurável via `PRIVACY_CONTACT_EMAIL` (ex.: privacidade@gaussix.com.br)

---

## 1. Quem somos

O **FlowIA** é uma plataforma SaaS multi-tenant operada pela **Gaussix**, destinada a salões de beleza. Cada salão cliente (`organization`) é **controlador** dos dados de seus clientes finais (titulares). A Gaussix atua como **operadora**, processando dados em nome do salão conforme instruções contratuais e esta política.

## 2. Dados que tratamos

| Categoria | Exemplos | Origem |
|-----------|----------|--------|
| Identificação | Nome, telefone, e-mail | WhatsApp, chat, dashboard |
| Agendamento | Horários, serviços, profissional | Dashboard, agente IA |
| Conversas | Mensagens trocadas via WhatsApp/chat | Webhook Meta, LangGraph |
| Operadores | E-mail, perfil de acesso ao dashboard | Cadastro do salão |
| Telemetria | Tokens, agente ativo, thread_id (sem corpo completo em métricas) | Sistema |
| Documentos KB | PDFs/textos enviados pelo salão | Data Lake (dev/admin) |

## 3. Finalidades e bases legais (LGPD Art. 7)

| Finalidade | Base legal |
|------------|------------|
| Agendamento e atendimento via IA | Execução de contrato / legítimo interesse do controlador (salão) |
| Suporte e handoff humano | Execução de contrato |
| Segurança, anti-fraude, logs operacionais | Legítimo interesse / obrigação legal |
| Melhoria do serviço (métricas agregadas) | Legítimo interesse |
| Cumprimento de obrigações fiscais/contábeis do salão | Obrigação legal do controlador |

## 4. Compartilhamento e subprocessadores

Dados podem ser processados por:

- **Supabase** — banco de dados e storage (PostgreSQL)
- **OpenAI** — processamento de linguagem natural, OCR e embeddings
- **Meta (WhatsApp Cloud API)** — mensagens
- **Render** — hospedagem da API e dashboard

Lista detalhada: [`SUBPROCESSORS.md`](SUBPROCESSORS.md).

Transferências internacionais podem ocorrer (ex.: OpenAI, Meta). Garantias contratuais padrão dos provedores aplicam-se conforme contrato SaaS.

## 5. Retenção

| Dado | Prazo padrão |
|------|--------------|
| Dedup webhook | 7 dias (`WEBHOOK_DEDUP_RETENTION_DAYS`) |
| Checkpoints de conversa | 90 dias (`CHECKPOINT_RETENTION_DAYS`) |
| Métricas de conversa | 365 dias (`CONVERSATION_METRICS_RETENTION_DAYS`) |
| Cadastro de clientes | Enquanto contrato ativo + obrigações legais do salão |
| Agendamentos | Conforme política do salão; PII anonimizada após eliminação do titular |

## 6. Direitos do titular (Art. 18)

O titular (cliente do salão) pode solicitar:

- Confirmação e acesso aos dados
- Correção de dados incompletos ou desatualizados
- Anonimização, bloqueio ou eliminação
- Portabilidade
- Informação sobre compartilhamento
- Revogação do consentimento

**Canal:** entrar em contato com o salão (controlador) ou com `{PRIVACY_CONTACT_EMAIL}` quando a solicitação envolver a operação FlowIA.

O salão pode usar o dashboard FlowIA (exportação/eliminação de cliente) ou seguir o [`DSR_RUNBOOK.md`](DSR_RUNBOOK.md).

## 7. Consentimento no WhatsApp / chat

No primeiro contato, o titular recebe aviso sobre tratamento de dados. Ao continuar a conversa após o aviso, registra-se consentimento tácito (versão documentada em `privacy_notice_version`). O titular pode revogar entrando em contato conforme seção 6.

## 8. Segurança

Medidas incluem: isolamento multi-tenant (RLS), autenticação JWT HttpOnly, mascaramento de PII em logs, rate limiting, headers de segurança HTTP. Detalhes técnicos em `CLAUDE.md` Parte III.

## 9. Alterações

Alterações relevantes serão comunicadas aos salões clientes. Versão da política referenciada no aviso WhatsApp (`PRIVACY_NOTICE_VERSION`).

## 10. Contato

E-mail: valor de `PRIVACY_CONTACT_EMAIL` no ambiente de produção.
