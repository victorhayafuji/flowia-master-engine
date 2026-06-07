---
name: flowia-security
description: Audits multi-tenant isolation, JWT/cookie auth, RLS, secrets rotation, WhatsApp credential handling, and rate limiting. Use when reviewing security, tenant bugs, 403 org mismatch, exposed secrets, webhook auth, or LGPD logging.
disable-model-invocation: true
---

# FlowIA Security Audit

## Secrets

- Nunca commitar `.env`, tokens ou service roles
- Validar: `python scripts/check_env.py`
- Exposição: seguir `docs/SECRET_ROTATION.md`
- Não logar tokens WhatsApp ou JWT em produção

## Multi-tenant

- Dados segmentados por `organization_id` + RLS Supabase
- Header `x-organization-id` em requisições autenticadas
- `super_admin`: pode usar `ALL` ou qualquer org
- `org_admin`: header deve coincidir com `org_id` do JWT → 403 se divergir
- Resolver tenant via `validated_tenant_context` — **nunca** confiar no header sem validação

## WhatsApp

- Credenciais por org: `organizations.whatsapp_phone_id`, `whatsapp_access_token`
- Webhook resolve org via `whatsapp_phone_id`
- Outbound: `packages/integrations/webhook/whatsapp.py`
- Falha silenciosa se credenciais ausentes — não logar tokens
- Dedup inbound por `message_id` (tabela `webhook_message_dedup`; RLS interno sem policies)

## Rate limiting

Login, webhook e endpoints sensíveis: `packages/auth_core/limiter` (slowapi)

## LGPD / logging

- Mascarar conteúdo de mensagens WhatsApp nos logs (primeiros 15 chars)
- Service role só no backend; anon key no frontend via `VITE_SUPABASE_KEY`

## Checklist de auditoria

- [ ] Endpoint filtra por `organization_id` validado?
- [ ] RLS policy ativa na tabela afetada?
- [ ] Tabela interna (checkpoints*, webhook dedup) tem RLS sem policies + REVOKE anon/authenticated?
- [ ] Header org bate com JWT para `org_admin`?
- [ ] Nenhum secret em código, logs ou resposta HTTP?
- [ ] Webhook verifica token Meta (`WHATSAPP_VERIFY_TOKEN`)?
