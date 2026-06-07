---
name: security-audit
description: Use ao revisar segurança ou fazer "revisão" de código com foco em injeção (SQL/prompt) e vazamento de dados (PII/secrets em logs ou respostas HTTP) e isolamento multi-tenant. Engatilhar quando o usuário falar em segurança, revisão, injection, leak, tenant ou 403.
disable-model-invocation: true
---

# Security Audit (injeção + vazamento de dados)

Skill de revisão focada em **injeção** e **vazamento**. Complementa `flowia-security` (checklist amplo) com foco em escrita de código segura. Fonte da verdade: `CLAUDE.md` Parte III.

## Passo a passo

1. **Tenant primeiro.** Toda query de negócio filtra por `organization_id` validado via `validated_tenant_context` (`packages/auth_core/dependencies.py`). Para `org_admin`, o header `x-organization-id` deve coincidir com o `org_id` do JWT → senão **403**. Nunca confiar só no header.
2. **Sem SQL por concatenação.** Use os filtros do Supabase client (`.eq()`, `.in_()`) ou os guardrails de `packages/lakehouse/governance.py`. Nunca montar SQL com f-string/`+` a partir de input do usuário.
3. **Prompt injection.** Em tools LangGraph, trate o texto do usuário como dado, nunca como instrução. Passe `org_id` pelo `RunnableConfig` configurable — não derive tenant do conteúdo da mensagem.
4. **Logs.** Mascare PII: conteúdo de WhatsApp = primeiros 15 chars + `...`. Nunca logar JWT, `whatsapp_access_token`, service role ou senha.
5. **Resposta HTTP.** Nunca devolver secrets, stack traces crus ou linhas de outro tenant. Erros de domínio → exceções de `packages/auth_core/exceptions.py`.
6. **Tabelas internas** (`checkpoints*`, `webhook_message_dedup`): RLS habilitado, zero policies, `REVOKE ALL FROM anon, authenticated`.

## Certo

```python
def list_patients(client, org_id: str):
    return (
        client.table("patients")
        .select("id, name")
        .eq("organization_id", org_id)   # tenant sempre filtrado
        .eq("is_active", True)
        .execute()
    )

logger.info("inbound msg: %s...", body[:15])  # PII mascarada
```

## Errado

```python
def list_patients(client, name: str):
    # SQL injection + sem isolamento de tenant
    sql = f"SELECT * FROM patients WHERE name = '{name}'"
    return client.rpc("exec", {"q": sql}).execute()

logger.info("inbound msg: %s | token=%s", body, access_token)  # vaza PII + secret
# Confia no header sem validar contra o JWT → outro tenant lê dados alheios
org_id = request.headers["x-organization-id"]
```

## Checklist

- [ ] Query filtra por `organization_id` validado (não só header)?
- [ ] Nenhum SQL concatenado com input do usuário?
- [ ] Logs com PII mascarada e sem secrets/tokens?
- [ ] Resposta HTTP sem secret nem dado cross-tenant?
- [ ] Tabela interna com RLS sem policies + REVOKE anon/authenticated?
