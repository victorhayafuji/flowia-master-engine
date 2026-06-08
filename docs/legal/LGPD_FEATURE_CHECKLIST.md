# Checklist LGPD — Nova Feature

> **Obrigatório antes de merge** de qualquer feature que toque dados, auth, logs, IA ou integrações.

Copiar na descrição do PR:

```
## LGPD checklist
- [ ] Novo dado pessoal? Documentado em docs/legal/ROPA.md
- [ ] Base legal definida (contrato / consentimento / legítimo interesse)
- [ ] Retenção definida (env TTL ou política documentada)
- [ ] Logs sem PII completa / secrets (máx 15 chars WhatsApp)
- [ ] Queries com organization_id + validated_tenant_context
- [ ] Titular pode acessar/exportar/apagar via fluxo existente ou novo endpoint
- [ ] Subprocessador novo? docs/legal/SUBPROCESSORS.md + PRIVACIDADE.md
- [ ] Consentimento WhatsApp/chat impactado? packages/compliance/consent.py
- [ ] Testes cobrem isolamento tenant
```

## Perguntas rápidas

1. **Estou persistindo algo novo?** → ROPA + migration + retenção.
2. **Aparece em log ou métrica?** → Mascarar ou evitar.
3. **LLM vê o dado?** → Finalidade documentada; minimizar prompt.
4. **Cross-tenant possível?** → Bloquear com dependency tenant.
5. **Eliminação do titular alcança isso?** → Estender `packages/compliance/erasure.py`.

## Referências código

| Área | Path |
|------|------|
| Consent gate | `packages/compliance/consent.py` |
| DSAR export/erase | `packages/compliance/export.py`, `erasure.py` |
| Retention jobs | `packages/compliance/retention.py` |
| Cursor rule | `.cursor/rules/06-lgpd-compliance.mdc` |
| Skill | `.cursor/skills/flowia-lgpd/SKILL.md` |
