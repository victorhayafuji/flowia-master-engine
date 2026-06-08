# WhatsApp Business API — Setup por tenant

Runbook para conectar WhatsApp Cloud API (Meta) ao FlowIA Salão. **Capítulo 5** do [`ROADMAP.md`](ROADMAP.md).

**Status MVP:** infra pronta; credenciais Meta ainda não configuradas no piloto Beauty Express.

---

## URLs de produção

| Item | Valor |
|------|-------|
| Webhook (Meta → FlowIA) | `https://flowia-api.onrender.com/api/v1/webhook/whatsapp` |
| Verificação GET | Mesma URL — Meta envia `hub.mode`, `hub.verify_token`, `hub.challenge` |
| Código | [`packages/integrations/webhook/router.py`](../packages/integrations/webhook/router.py) |

> **Nota:** o path é `/webhook/whatsapp` (prefixo `/api/v1` no app_factory), **não** `/api/v1/whatsapp`.

---

## Pré-requisitos Meta

1. Conta [Meta Business](https://business.facebook.com/)
2. App em [Meta Developers](https://developers.facebook.com/) com produto **WhatsApp**
3. Número de telefone verificado (teste ou produção)
4. Anotar:
   - **Phone Number ID** (`phone_number_id`)
   - **WhatsApp Business Account ID** (opcional, `whatsapp_business_id`)
   - **Permanent access token** (System User ou token de longa duração)

---

## 1. Variáveis Render (API `flowia-api`)

| Variável | Onde obter | Obrigatória |
|----------|------------|-------------|
| `WHATSAPP_VERIFY_TOKEN` | String que você define (Meta webhook verification) | Sim |
| `WHATSAPP_APP_SECRET` | Meta App → Settings → Basic → App Secret | Recomendado (HMAC inbound) |

Redeploy da API após alterar.

---

## 2. Credenciais por organização (Supabase)

Atualizar a linha da org no SQL Editor ou dashboard:

```sql
UPDATE organizations
SET
  whatsapp_phone_id = 'SEU_PHONE_NUMBER_ID',
  whatsapp_access_token = 'SEU_ACCESS_TOKEN',
  whatsapp_business_id = 'SEU_WABA_ID'  -- opcional
WHERE id = '22222222-2222-2222-2222-222222222222';  -- Beauty Express piloto
```

**Segurança:** token só no backend (`SUPABASE_SERVICE_ROLE`); nunca no frontend.

Resolução de tenant inbound: [`packages/integrations/webhook/tenant_resolver.py`](../packages/integrations/webhook/tenant_resolver.py) — match `metadata.phone_number_id` ↔ `organizations.whatsapp_phone_id`.

---

## 3. Configurar webhook na Meta

1. Meta Developers → seu App → WhatsApp → Configuration
2. **Callback URL:** `https://flowia-api.onrender.com/api/v1/webhook/whatsapp`
3. **Verify token:** mesmo valor de `WHATSAPP_VERIFY_TOKEN` no Render
4. Assinar campo **messages**
5. Salvar — Meta faz GET de verificação; API responde com `hub.challenge`

---

## 4. Teste local (sem celular)

Requisitos: backend local + `.env`:

```env
SIM_WHATSAPP_ORG_ID=22222222-2222-2222-2222-222222222222
SIM_WHATSAPP_PHONE_ID=123456789
```

```powershell
py scripts/simulate_whatsapp_webhook.py --wait 12
```

- Inbound processado em background
- Outbound só funciona se `whatsapp_access_token` estiver na org
- Métricas: `conversation_metrics` com `channel=whatsapp`, `scheduling_path`

**Não** setar `SIM_WHATSAPP_ORG_ID` em produção Render.

---

## 5. Teste em produção (com Meta)

1. Enviar mensagem de texto para o número WhatsApp Business
2. Logs Render → `flowia-api` → buscar `Processing message from`
3. Supabase:

```sql
SELECT thread_id, agent_type, scheduling_path, triage_source, channel, tokens_total, created_at
FROM conversation_metrics
WHERE channel = 'whatsapp'
ORDER BY created_at DESC
LIMIT 10;
```

4. Fluxo esperado: `"Quero mechas sexta"` → `agent_type=scheduling`, `scheduling_path=deterministic`

---

## 6. Lembretes automáticos (Epic 1B)

[`packages/scheduling/reminder_service.py`](../packages/scheduling/reminder_service.py) envia lembretes via `WhatsAppService.send_text_message` em `process_pending_reminders`:

- Resolve telefone do paciente + contexto do agendamento (serviço, horário, nome do salão)
- Tenant context por `organization_id` antes do outbound
- Falha de envio → `mark_failed`; sucesso → `mark_sent`
- Tipos: `confirmation_24h`, `reminder_2h` (templates curtos em PT-BR)

**Requisito:** credenciais WhatsApp da org (seção 3). Sem token válido, lembretes falham com erro registrado no banco.

---

## Troubleshooting

| Sintoma | Causa provável | Ação |
|---------|----------------|------|
| Meta verification 403 | `WHATSAPP_VERIFY_TOKEN` diverge | Alinhar Render + Meta Console |
| Mensagem ignorada | `phone_number_id` não bate com org | Conferir `organizations.whatsapp_phone_id` |
| `ENGINE FAILURE` tenant | Org unresolved | Ver logs `Skipping message — organization unresolved` |
| Sem resposta outbound | Token ausente/placeholder | Preencher `whatsapp_access_token` |
| Métricas não gravam | Migration `sender_id` TEXT | Rodar `20260610050000_conversation_metrics_sender_text.sql` |

---

## Referências

- [`docs/PRODUCTION.md`](PRODUCTION.md) — smoke e rollback
- [`docs/SECRET_ROTATION.md`](SECRET_ROTATION.md) — rotação de tokens
- [`CLAUDE.md`](../CLAUDE.md) §4.2 Atendimento WhatsApp
