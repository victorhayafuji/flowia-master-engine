# Observabilidade do agente — FlowIA Salão

> Fonte operacional e comercial (Jun/2026). Complementa [`PRODUCTION.md`](PRODUCTION.md), [`SECURITY_GO_LIVE_CHECKLIST.md`](SECURITY_GO_LIVE_CHECKLIST.md) e [`pitch/FLOWIA_SOCIO_OUTLINE.md`](pitch/FLOWIA_SOCIO_OUTLINE.md) slide 8.

## Em 30 segundos

| Pergunta | Resposta |
|----------|----------|
| O salão vê tokens/custo? | **Não** no MVP — só sinais operacionais |
| A Gaussix vê métricas técnicas? | **Sim** — `/admin/observability` (super_admin, prod) |
| Onde grava cada turno? | Tabela `conversation_metrics` (tenant + RLS) |
| Histórico completo da conversa? | LangGraph `checkpoints*` (backend-only, sem UI MVP) |

---

## Matriz persona × dados × tela

| Persona | Tela | Dados visíveis | LGPD |
|---------|------|----------------|------|
| **org_admin** | Overview — cards *Assistente IA* | Handoffs pendentes, agendamentos WhatsApp hoje, conversas na semana (contagem) | Sem conteúdo de chat |
| **super_admin** | `/admin/observability` | % path determinístico, tokens médios, triage, canal, thread truncada | Uso interno Gaussix; mascarar em demo |
| **Dev** | Chat Test + Observabilidade + SQL | Badges por turno + queries abaixo | Nunca exportar PII em pitch |

**Não expor ao org_admin:** `tokens_*`, custo R$, `thread_id`, `triage_source`, `tools_called`, replay de conversa.

---

## Camadas técnicas

```text
WhatsApp / Chat Test → LangGraph → save_conversation_metric → conversation_metrics
                                 → PostgresSaver → checkpoints* (sem UI)
```

Endpoints:

| Método | Path | Quem | Uso |
|--------|------|------|-----|
| GET | `/dashboard/agent-summary` | org_admin+ | Cards Overview (lite) |
| GET | `/metrics/scheduling-observability` | super_admin | KPI híbrido 7 dias |
| GET | `/metrics/conversations` | super_admin | Tabela técnica (`tokens_turn`, `tokens_thread_7d`) |
| GET | `/metrics/tokens-daily` | auth + tenant | Gráfico tokens (super_admin ops) |

Arquivos: [`packages/engine/metrics/service.py`](../packages/engine/metrics/service.py), [`apps/salon/api/routers/dashboard.py`](../apps/salon/api/routers/dashboard.py), [`apps/salon/dashboard/src/features/admin/AgentObservability.tsx`](../apps/salon/dashboard/src/features/admin/AgentObservability.tsx).

---

## Copy comercial (proposta / contrato)

**Incluído no MVP:**

- Dashboard com visão operacional do dia e indicadores do assistente (atendimentos que pediram humano, agendamentos via canal automático, volume de conversas na semana).
- Monitoramento interno Gaussix de qualidade e custo da IA.

**Não incluído (fase 2):**

- Painel de tokens/custo para o dono do salão.
- Exportação do histórico completo de chat para o cliente.
- SLA de tempo de resposta da IA (definir após WhatsApp Meta live).

---

## Queries SQL (operação Gaussix)

Conversas recentes com telemetria híbrida:

```sql
SELECT thread_id, agent_type, scheduling_path, triage_source, channel, tokens_total, created_at
FROM conversation_metrics
WHERE organization_id = '22222222-2222-2222-2222-222222222222'
ORDER BY created_at DESC
LIMIT 20;
```

Handoffs pendentes:

```sql
SELECT id, name, phone, handoff_requested_at, handoff_reason
FROM patients
WHERE organization_id = '22222222-2222-2222-2222-222222222222'
  AND handoff_requested_at IS NOT NULL
  AND is_active = true;
```

Agendamentos via WhatsApp hoje:

```sql
SELECT COUNT(*) FROM appointments
WHERE organization_id = '22222222-2222-2222-2222-222222222222'
  AND source = 'whatsapp'
  AND scheduled_at >= date_trunc('day', now() AT TIME ZONE 'America/Sao_Paulo')
  AND scheduled_at < date_trunc('day', now() AT TIME ZONE 'America/Sao_Paulo') + interval '1 day';
```

---

## Checklist manual (Beauty Express)

1. Login `dono@beauty-express.com` → Overview → cards *Assistente IA* carregam sem erro.
2. Link *Ver handoffs* → `/patients?handoff=1` filtra clientes com badge.
3. Login super_admin prod → nav *Observabilidade (plataforma)* → KPI determinístico.
4. Dev local: Chat Test `"Quero mechas sexta"` → badge `path=deterministic` + linha em `conversation_metrics`.

---

## Backlog pós-1º cliente

- Replay de conversa (checkpoints) com mascaramento LGPD.
- Alertas handoff > 24h, `knowledge_gaps`.
- LangSmith (`LANGCHAIN_TRACING_V2`) só staging — exige DPA se houver PII.
- Relatório mensual automatizado.

---

## Referências

- [`WHATSAPP_SETUP.md`](WHATSAPP_SETUP.md) — canal `whatsapp` em métricas após Meta.
- [`legal/ROPA.md`](legal/ROPA.md) — tratamento de dados de conversa.
