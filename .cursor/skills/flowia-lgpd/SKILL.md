---
name: flowia-lgpd
description: LGPD compliance for FlowIA — consent gate WhatsApp/chat, DSAR export/erase, retention jobs, ROPA updates, feature checklist. Use when implementing features with PII, privacy policy, data subject rights, or reviewing LGPD impact.
disable-model-invocation: true
---

# FlowIA LGPD

## Documentação

- [`docs/legal/PRIVACIDADE.md`](../../../docs/legal/PRIVACIDADE.md) — política (DRAFT)
- [`docs/legal/ROPA.md`](../../../docs/legal/ROPA.md) — registro operações
- [`docs/legal/DSR_RUNBOOK.md`](../../../docs/legal/DSR_RUNBOOK.md) — pedidos titular
- [`docs/legal/LGPD_FEATURE_CHECKLIST.md`](../../../docs/legal/LGPD_FEATURE_CHECKLIST.md) — gate PR

## Consentimento (WhatsApp / chat)

1. `packages/compliance/consent.py` — `build_privacy_notice`, `has_valid_consent`, `record_notice_shown`, `record_consent`
2. 1ª mensagem → aviso LGPD only (sem engine triage)
3. 2ª mensagem → `privacy_consent_at` + fluxo normal; `lgpd_shown: true` no state
4. Campos DB: `patients.privacy_notice_version`, `privacy_notice_shown_at`, `privacy_consent_at`, `privacy_consent_channel`

## DSAR (dashboard org_admin)

- `GET /api/v1/compliance/patients/{id}/export` — JSON bundle
- `POST /api/v1/compliance/patients/{id}/erase` — anonimiza + purge checkpoints/metrics
- UI: `apps/salon/dashboard/src/features/clients/Patients.tsx`

## Retenção

- `CONVERSATION_METRICS_RETENTION_DAYS` (default 365)
- `CHECKPOINT_RETENTION_DAYS` (default 90)
- Jobs: `packages/compliance/retention.py` via APScheduler

## Checklist nova feature

- [ ] ROPA atualizado?
- [ ] Retenção definida?
- [ ] Logs mascarados?
- [ ] Tenant scope?
- [ ] Erase alcança novos dados?
- [ ] Subprocessador listado?

## Env obrigatórias produção

- `PRIVACY_CONTACT_EMAIL`
- `PRIVACY_POLICY_URL` (site externo, ex.: `https://www.gaussix.com/privacidade`)
