# FlowIA Salão — Outline deck sócio (10–12 slides)

> Fonte para PDF/Google Slides. Marca: **FlowIA** (produto) · **Gaussix** (empresa).
> Exportar: copiar cada slide para Slides ou `pandoc docs/pitch/FLOWIA_SOCIO_DECK.md -o FlowIA-Socio.pdf`

---

## Slide 1 — Capa

**FlowIA Salão**  
Plataforma SaaS de gestão + recepcionista IA para salões de beleza  

Um produto **Gaussix** · Jun/2026  

Victor [sobrenome] · [contato]

---

## Slide 2 — Problema

Salões perdem receita e tempo com:

- Recepção manual no WhatsApp (horário comercial limitado)
- **No-show** e agenda desorganizada
- Chatbots genéricos que **inventam** preço/horário ou confirmam sem registrar
- Dono sem visão operacional do dia (equipe, fila, conflitos)

---

## Slide 3 — Solução

**FlowIA** = dashboard multi-tenant + assistente conversacional

| Camada | O que entrega |
|--------|----------------|
| Dashboard | Agenda operacional, clientes, catálogo, visão do dia |
| IA | Preços/políticas via KB (RAG), agendamento guiado |
| Plataforma | 1 codebase, N salões isolados por `organization_id` + RLS |

---

## Slide 4 — Diferencial: Agente Híbrido

> *Conversa generativa. Agendamento determinístico.*

| Chatbot 100% LLM | FlowIA híbrido |
|------------------|----------------|
| Tokens em todo turno | **path=deterministic → tokens≈0** |
| Risco de alucinação | Executor valida overlap, M:N, upsert cliente |
| Lento | Resposta imediata nos fluxos repetitivos |
| Sem prova de ROI | Métricas `scheduling_path` por org/canal |

**Frase:** a IA sabe quando **não** usar IA.

---

## Slide 5 — Demo visual (screenshots)

Inserir capturas anonimizadas:

1. **Overview** — today-board por profissional
2. **Agenda** — timeline operacional (Gantt)
3. **Chat Test** — badges `path=deterministic`, slots reais
4. **Observabilidade** — KPI % determinístico (dev)

URLs prod: dashboard + API em [`PRODUCTION.md`](../PRODUCTION.md)

---

## Slide 6 — Arquitetura (simples)

```text
WhatsApp / Chat → FastAPI (LangGraph) → Supabase (Postgres + RLS)
                      ↓
              Gemini (triage, RAG, fallback)
                      ↓
              Executor determinístico (agenda)
```

Stack: Python 3.12 · React · Supabase · Render · Google Gemini

---

## Slide 7 — Status hoje (prod)

| Item | Status |
|------|--------|
| API + Dashboard Render | **Live** |
| Motor híbrido agendamento | **Live** — smoke 2026-06-08 OK |
| RAG / Data Lake | Dev + pipeline ativo |
| WhatsApp Meta real | **Pendente** credenciais |
| 1º cliente pagante | Checklist pronto (`onboard_tenant.py`) |

---

## Slide 8 — Métricas (prova)

Smoke híbrido registrado:

- Turno `"Quero mechas sexta"` → `scheduling_path=deterministic`, `tokens=0`
- `conversation_metrics` com `channel`, `triage_source`, `scheduling_path`
- Endpoint `/metrics/scheduling-observability` — KPI últimos 7 dias

---

## Slide 9 — Roadmap (90 dias)

1. **Landing FlowIA** + apresentação sócio (este mês)
2. **WhatsApp Meta** — outbound/inbound por org
3. **1º salão piloto pagante** — Supabase prod separado
4. **Site Gaussix** — institucional (ciclo seguinte)
5. **Fase 2** — pagamentos, comissões (Lei Salão Parceiro)

---

## Slide 10 — Modelo de negócio

| Tier | Descrição |
|------|-----------|
| **SaaS padrão** | Mensalidade por salão · 1 Render + 1 Supabase · N tenants |
| **Enterprise** | Supabase dedicado · precificação premium |

Referência: [`TENANCY_AND_SCALE.md`](../TENANCY_AND_SCALE.md)

TAM: ~500k salões BR (ordem de grandeza — validar com pesquisa comercial)

---

## Slide 11 — Ask (sócio)

- **Papel desejado:** operação, comercial, capital, produto?
- **Piloto:** indicar 1 salão para teste 30 dias?
- **Compromisso:** X h/semana até 1º cliente pagante
- **Decisões:** domínio, pricing inicial, prioridade WhatsApp vs landing

---

## Slide 12 — Próximos 30 dias

- [ ] Landing https://flowia-landing.onrender.com no ar
- [ ] Apresentação sócio + feedback documentado
- [ ] Checklist manual prod (#7 agenda, #8 observability)
- [ ] Meta WhatsApp quando credenciais disponíveis
- [ ] Primeiro LOI ou piloto assinado
