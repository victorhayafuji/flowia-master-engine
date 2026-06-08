# FlowIA Salão — Deck sócio (conteúdo completo)

> Exportar para PDF: abrir no Google Slides (importar de [`FLOWIA_SOCIO_OUTLINE.md`](FLOWIA_SOCIO_OUTLINE.md)) ou `pandoc FLOWIA_SOCIO_DECK.md -o FlowIA-Socio.pdf`  
> Roteiro de fala: [`FLOWIA_SOCIO_ROTEIRO.md`](FLOWIA_SOCIO_ROTEIRO.md)

---

## 1. Capa

**FlowIA Salão**  
Gestão inteligente + recepcionista IA para salões de beleza  

Produto **Gaussix** · Junho 2026

---

## 2. Problema

Salões perdem **tempo e receita** todos os dias:

- WhatsApp manual consome recepção; fora do horário, lead esfria
- **No-show** e conflito de agenda = cadeira vazia
- Chatbots genéricos **inventam** preço e horário
- Dono opera no escuro — sem visão do dia por profissional

*Pergunta para o sócio:* quanto custa uma cadeira vazia por semana no salão que vocês conhecem?

---

## 3. Solução FlowIA

Plataforma **SaaS multi-tenant**:

| Pilar | Entrega |
|-------|---------|
| Dashboard | Agenda Gantt, clientes, catálogo, visão operacional do dia |
| Assistente IA | Preços/políticas (RAG), agendamento conversacional |
| Infra | 1 codebase · N salões · isolamento RLS |

Não é só chatbot — é **operação + conversão**.

---

## 4. Diferencial — Agente Híbrido

**Insight:** agendamento não é conversa livre; é **transação com regras**.

```
Cliente → Triage → Executor determinístico → Resposta natural
                         ↓ (se ambíguo)
                    Fallback LLM
```

| | LLM puro | FlowIA híbrido |
|---|----------|----------------|
| Tokens agendar | Sempre | **≈0** no happy path |
| Double booking | Risco | Validado (Python + DB) |
| Prova ROI | Nenhuma | `scheduling_path` por org |

**Tagline:** *IA que sabe quando não usar IA.*

---

## 5. Demo visual

*(Inserir screenshots)*

1. Overview — today-board
2. Agenda — timeline operacional
3. Chat Test — `path=deterministic`, slots reais
4. Observabilidade — KPI 7 dias

Prod: flowia-dashboard.onrender.com

---

## 6. Arquitetura

- **Backend:** FastAPI + LangGraph + Gemini
- **Frontend:** React (Neo-Swiss Brutalism)
- **Dados:** Supabase Postgres + RLS + pgvector (RAG)
- **Deploy:** Render (API + Static Sites)

WhatsApp: webhook pronto; aguardando credenciais Meta por org.

---

## 7. Status (Jun/2026)

| Entregue | Pendente |
|----------|----------|
| API + Dashboard prod | WhatsApp Meta live |
| Motor híbrido + smoke OK | 1º cliente pagante |
| RAG / Data Lake (dev) | Site Gaussix |
| Landing marketing | Pagamentos Fase 2 |

21 migrations Supabase aplicadas.

---

## 8. Métricas

Smoke 2026-06-08:

- `"Quero mechas sexta"` → `scheduling_path=deterministic`, `tokens=0`
- Métricas: `channel`, `triage_source`, `scheduling_path`
- Endpoint admin: `/metrics/scheduling-observability`

---

## 9. Roadmap 90 dias

1. Landing + apresentação sócio ← **agora**
2. Meta WhatsApp + piloto 1 salão
3. Supabase prod separado + onboarding script
4. Site Gaussix institucional
5. Comissões / Lei Salão Parceiro (com pagamentos)

---

## 10. Modelo de negócio

- **SaaS:** mensalidade por salão (tier padrão)
- **Enterprise:** Supabase dedicado (premium)
- Escala: centenas de orgs no mesmo deploy ([`TENANCY_AND_SCALE.md`](../TENANCY_AND_SCALE.md))

TAM Brasil: mercado fragmentado, milhares de salões — validar pricing com 3 entrevistas.

---

## 11. Ask

- Qual papel você quer assumir?
- Conhece 1 salão para piloto 30 dias?
- Capital vs tempo — o que entra primeiro?
- Prioridade: comercial ou produto até 1º pagante?

---

## 12. Próximos 30 dias

- Landing live
- Feedback sócio documentado
- Checklist prod (#7 #8)
- LOI ou piloto assinado
- Meta WhatsApp quando possível
