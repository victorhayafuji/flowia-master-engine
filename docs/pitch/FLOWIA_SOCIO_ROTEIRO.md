# FlowIA — Roteiro de fala (apresentação sócio)

**Duração total:** 25–30 min (+ 10 min demo opcional + Q&A)  
**Formato:** PDF deck + conversa; demo ao vivo opcional após slide 5.

---

## Bloco 1 — Abertura (3 min) · Slides 1–2

> "Obrigado por topar ouvir isso. Resumo em uma frase: estamos construindo a **recepção inteligente** do salão — não um chatbot genérico, mas operação + conversa."

- Apresente FlowIA como produto; Gaussix como empresa por trás.
- Problema: WhatsApp manual, no-show, bots que inventam horário.
- **Pergunta:** "Quanto você acha que um no-show custa por mês num salão médio?"

---

## Bloco 2 — Solução e diferencial (8 min) · Slides 3–4

> "A maioria vende IA como magia. Nós separamos **conversa** de **agendamento**."

- Dashboard: agenda Gantt, catálogo, clientes — dono vê o dia.
- **Agente Híbrido:** executor determinístico antes do LLM.
- Analogia: "O LLM é recepcionista que fala bonito; o executor é o sistema que **não deixa** double booking."
- Número matador: smoke prod com **tokens=0** no turno de agendamento.

---

## Bloco 3 — Prova visual (5 min) · Slide 5

Mostrar screenshots (ou demo live):

1. Overview today-board
2. Agenda operacional
3. Chat Test com badges `path=deterministic`

Se demo live: login Beauty Express → Chat Test → `"Quero mechas sexta"` → mostrar slots.

---

## Bloco 4 — Tecnologia e status (5 min) · Slides 6–8

> "Já está no ar. Não é slide de futuro."

- Stack em 30 segundos — confiança, não detalhe.
- Prod URLs Render.
- WhatsApp: infra pronta, credenciais Meta pendentes — simulate local funciona.
- Métricas observability — prova que o híbrido não é marketing.

---

## Bloco 5 — Negócio e ask (5 min) · Slides 9–11

> "Modelo é SaaS por salão. Escala sem 1 deploy por cliente."

- Roadmap 90 dias — landing, piloto, Gaussix depois.
- **Ask direto:** papel do sócio, indicação de piloto, tempo vs capital.
- Não fechar valuation agora — fechar **próximo passo concreto**.

---

## Bloco 6 — Fechamento (2 min) · Slide 12

> "Próximos 30 dias: landing no ar, seu feedback hoje, primeiro salão piloto."

- Agendar follow-up em 7 dias.
- Pedir intro a 1 dono de salão se possível.

---

## Demo opcional (10 min)

| Passo | Ação |
|-------|------|
| 1 | Login dashboard prod ou local |
| 2 | Overview → mostrar profissionais do dia |
| 3 | Agenda → criar/reagendar slot |
| 4 | Chat Test → agendamento híbrido |
| 5 | Observability → KPI determinístico |

**Fallback:** só screenshots se rede/login falhar.

---

## Perguntas difíceis (respostas sugeridas)

| Pergunta | Resposta |
|----------|----------|
| "Por que não usar ChatGPT puro?" | Custo, alucinação, sem agenda real integrada |
| "WhatsApp não funciona?" | Webhook pronto; Meta é burocracia, não gap técnico |
| "Concorrente X?" | Eles vendem chat; nós vendemos **operação + híbrido mensurável** |
| "Quanto custa?" | Definir após piloto — foco em valor (cadeira ocupada, horas recepção) |

---

## Pós-reunião

Preencher [`FEEDBACK_SOCIO.md`](FEEDBACK_SOCIO.md) no mesmo dia.
