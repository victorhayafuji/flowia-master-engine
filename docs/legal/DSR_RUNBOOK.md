# Runbook — Direitos do Titular (DSR)

> Procedimento operacional para pedidos LGPD Art. 18.

## Papéis

| Pedido sobre | Responsável primário | FlowIA (operadora) |
|--------------|---------------------|-------------------|
| Dados do cliente do salão | Salão (controlador) | Executa tecnicamente via dashboard/API |
| Dados de operador dashboard | Salão / Gaussix | Gaussix |
| Infra / vazamento | Gaussix | Gaussix |

**Prazo orientativo:** 15 dias (LGPD Art. 18, §3) — confirmar com assessoria jurídica.

## Canais de entrada

- E-mail: `PRIVACY_CONTACT_EMAIL`
- Salão via dashboard: Clientes → Exportar / Eliminar
- WhatsApp: agente encaminha para e-mail de privacidade (prompt guardrails)

## Acesso / portabilidade

1. Validar identidade do titular (salão confirma telefone/nome).
2. Dashboard: `GET /api/v1/compliance/patients/{id}/export` (org_admin autenticado).
3. Entregar JSON ao titular via canal seguro (não e-mail não criptografado se volume alto).

Bundle inclui: cadastro patient, agendamentos, metadados de conversas (sem corpo completo de checkpoint).

## Correção

1. Salão edita via dashboard (`POST /patients/` ou futuro PUT) ou solicita à Gaussix.
2. Registrar data da correção.

## Eliminação / anonimização

1. Confirmar que não há obrigação legal de retenção (ex.: nota fiscal pendente — responsabilidade do salão).
2. Dashboard: `POST /api/v1/compliance/patients/{id}/erase` (confirmação modal).
3. Sistema executa:
   - Anonimiza PII em `patients` (`[Removido]`, phone hash, `is_active=false`)
   - Purga `conversation_metrics` do thread
   - Purga checkpoints LangGraph (`thread_id` = telefone WhatsApp)
4. Agendamentos históricos permanecem com vínculo anonimizado (estatística operacional do salão).

## Revogação de consentimento

- Registrar pedido; desativar processamento IA opcional (handoff humano).
- Se eliminação total desejada → seguir fluxo de eliminação.

## Registro

Manter log interno (ticket): data, tipo pedido, tenant, ação, responsável.
