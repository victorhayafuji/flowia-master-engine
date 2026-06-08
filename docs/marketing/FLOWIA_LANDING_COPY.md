# FlowIA Landing — Copy PT-BR (MVP)

Fonte de verdade para [`apps/landing/`](../apps/landing/). Tom: direto, Neo-Swiss, sem jargão excessivo.

---

## Meta / SEO

| Campo | Texto |
|-------|-------|
| `title` | FlowIA — Recepcionista IA para salões de beleza |
| `description` | Automatize WhatsApp e agenda com Agente Híbrido: conversa natural, agendamento preciso, zero alucinação de horário. |
| `og:title` | FlowIA Salão |
| `og:description` | IA que sabe quando não usar IA. |

---

## Hero

**Headline:** Recepcionista IA que conversa como humano. Agenda com precisão de sistema.

**Subheadline:** FlowIA combina inteligência conversacional com motor determinístico de agendamento — menos custo de tokens, zero double booking, resposta em segundos.

**CTA primário:** Agendar demo → `mailto:contato@gaussix.com.br?subject=Demo%20FlowIA`

**CTA secundário:** Ver como funciona → `#como-funciona`

**Badge:** Agente Híbrido · Multi-tenant · Salões de beleza

---

## Problema (3 bullets)

1. **WhatsApp caótico** — recepção manual, mensagens perdidas, horário comercial limitado
2. **Chatbots que inventam** — preço errado, horário inexistente, “confirmado” sem registro
3. **Agenda cega** — dono sem visão do dia por profissional, no-show sem prevenção

---

## Diferencial — Agente Híbrido

**Título:** Conversa generativa. Agendamento determinístico.

| | Chatbot tradicional | FlowIA |
|---|---------------------|--------|
| Agendamento | 100% LLM | Executor + regras de negócio |
| Custo por turno | Alto (tokens sempre) | **~0 tokens** no fluxo determinístico |
| Confiabilidade | Alucinação possível | Overlap validado, M:N profissional↔serviço |
| Fallback | — | LLM quando a conversa foge do script |

**Frase de apoio:** A IA explica. O motor de agenda decide.

---

## Features (4 cards)

1. **Agenda operacional** — timeline por profissional, reagendamento drag-and-drop, visão do dia
2. **Base de conhecimento (RAG)** — preços e políticas oficiais; a IA consulta antes de responder
3. **Multi-tenant SaaS** — cada salão isolado; credenciais WhatsApp white-label por organização
4. **Observabilidade** — métricas `scheduling_path` — prove ROI do híbrido vs LLM puro

---

## Como funciona (#como-funciona)

1. Cliente envia mensagem (WhatsApp ou chat)
2. **Triage** classifica intenção (preço, política, agendar)
3. **Executor determinístico** consulta catálogo + disponibilidade real
4. **Composer** responde em linguagem natural (sem gastar LLM no happy path)
5. **Fallback LLM** só quando necessário

Diagrama na landing: fluxo visual em 5 passos.

---

## Prova social / técnica (MVP)

- Badge demo: `path=deterministic` · `tokens=0` · slots reais do catálogo
- Screenshot dashboard (Overview + Agenda) — sem PII
- Nota: WhatsApp Meta em rollout; demo disponível via chat test / simulação

---

## CTA final

**Título:** Pronto para ver na prática?

**Texto:** Agende uma demo de 20 minutos. Mostramos agenda, agente híbrido e métricas ao vivo.

**Botão:** Agendar demo → mesmo mailto

---

## Footer

**FlowIA** — um produto [Gaussix](#)  
Links: Dashboard app · [Documentação técnica](https://github.com/victorhayafuji/flowia-master-engine) (opcional, dev)

© 2026 Gaussix. Todos os direitos reservados.
