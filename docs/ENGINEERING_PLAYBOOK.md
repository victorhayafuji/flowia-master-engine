# Engineering Playbook — Erros, Mudanças e Metodologia

> Registro **resumido** dos erros cometidos e das mudanças feitas no ciclo
> **dashboard financeiro + KPI + agente guiado (release 1.2.0)** — para **não repetirmos os mesmos
> erros** e para os próximos agentes construírem de forma **uniforme**.
>
> Escopo: este ciclo (branch `feat/dashboard-financial-guided-booking`). Detalhe versionado:
> [`CHANGELOG.md`](../CHANGELOG.md). Fonte da verdade do projeto: [`CLAUDE.md`](../CLAUDE.md).

---

## 1. Registro de erros & correções

| # | Erro / sintoma | Causa-raiz | Correção | Lição |
|---|----------------|-----------|----------|-------|
| E1 | Slot ISO duplicado (`2026-..T2026-..T..`) → `Invalid isoformat` | `get_available_slots` já devolve ISO completo; o código reconcatenava data+hora | `datetime.fromisoformat(slot)` direto; option id = ISO, title = `HH:MM` | Não reconstruir datetime quando a fonte já entrega ISO completo |
| E2 | Fundir o guiado no dispatch quebrou **12 testes** `agent_flow` | O guiado passou a interceptar **toda** intenção de agendamento | Tornar opt-in: `guided_enabled=False` por padrão; só o chat dev liga | Mudança que altera **roteamento** entra **atrás de flag**, default = comportamento de produção |
| E3 | 2 testes: `fake_dispatch() got unexpected keyword` | Novo parâmetro na função real não refletido no mock | `**kwargs` no fake | Ao adicionar parâmetro, atualizar mocks com assinatura tolerante |
| E4 | FAQ "Horário" forçava triagem de **booking** | Texto canônico continha a keyword `horário` (gatilho de scheduling) | Reescrever para "Em quais dias e horas o salão funciona?" | Cuidado com **colisão de keywords de triagem** ao escrever textos canônicos |
| E5 | "Sim/Concordo" caía no LLM em vez de abrir o menu | `is_greeting` não reconhecia acks de consentimento | `_ACK_PHRASES` (match exato) em `is_greeting` | Acks determinísticos devem ter caminho determinístico |
| E6 | E2E falhava ao buscar `step.text` na tela | A UI renderiza `response` + botões, **não** o texto do passo | Assert por `data-testid` do botão | Testar pelo que a UI **renderiza** (testids), não por estado interno |
| E7 | Sessão guiada perdida (hot-reload) vazava p/ o LLM de texto livre | Estado in-memory volátil; sem recuperação | Recuperação fail-soft: resposta nome+telefone (`is_booking_data_reply`) reinicia o guiado | Estado in-memory é volátil → **recuperação graciosa**, nunca vazar em silêncio |
| E8 | **Timezone** (3 focos): KPI fatiava string UTC (`sa[:10]`); today-board comparava strings ISO; guiado usava `date.today()` do servidor | Lógica de "dia" no fuso errado (UTC/servidor ≠ org) | Converter para o **fuso da org**: `_appt_day_in_tz`, `datetime` aware, `now_local_naive(tzname)` | **Nunca** usar `date.today()` nem slice de string UTC para lógica de dia — sempre fuso da org |
| E9 | Slot não validado → exceção **fora** do try → turno engolido no WhatsApp (sem resposta) | `fromisoformat(slot)` antes do bloco protegido + seleção não validada | Validar ISO no STEP_SLOT; `try` abrange a construção do appointment | Validar **toda** seleção do usuário; toda I/O/parse de canal dentro de `try` com erro amigável |
| E10 | WhatsApp: passo "buttons" com >3 opções truncava silenciosamente | Meta limita a 3 botões | `>3 opções → lista`; warning quando lista >10 | Respeitar limites do canal (Meta: 3 botões / 10 linhas de lista) |
| E11 | Fallback do upsert sem proteção | `except` fazia select+update sem `try` próprio | Envolver o fallback; falha → `None` (re-pergunta) | Todo **fallback de DB** também precisa de guarda |
| E12 | Versão divergia (`FastAPI(version="1.1.0")` vs `_APP_VERSION`) | Dois lugares com o mesmo valor | `version=_APP_VERSION` (fonte única) | Um valor = **uma** fonte de verdade |
| E13 | Webhook caía no fallback com resposta multimodal | `content` em **lista** não normalizado (`.strip()` quebrava) | Reusar `routing.message_text` (normaliza str/lista) | Normalizar conteúdo de mensagem de forma **consistente entre canais**; reusar util existente |
| E14 | Consentimento "Discordo" é anulado pela próxima msg (LGPD) | Sem coluna `privacy_declined_at`; cai no tácito | Documentado como **limitação** + fast-follow (migration) | Opt-out precisa ser **persistido**; decisão LGPD antes do código |
| E15 | Código morto `iter_text_messages` | Troca para `iter_messages` deixou o antigo órfão | Removido | Ao trocar um util, **remover o órfão** na mesma mudança |
| E16 | `test-results/.last-run.json` versionado | Artefato de teste trackeado antes da regra de ignore | `git rm --cached` no commit (regra já existe no `.gitignore`) | Não versionar artefatos; **conferir `git status`** antes do commit |

---

## 2. Mudanças entregues (resumo por área)

- **Financeiro** — `GET /dashboard/financial` (Faturado/A Faturar/Perda por Dia/Mês/Ano); regra
  status→categoria **single source** em `packages/scheduling/financial.py`.
- **KPI por profissional** — `GET /dashboard/professional-kpi?date=` (atendimentos + clientes únicos,
  dia vs anterior vs seguinte).
- **Agente híbrido guiado** — seleção por botões channel-agnostic (`guided_booking.py` /
  `guided_session_store.py`): menu (Agendar × FAQ), FAQ por tópicos via LLM+RAG, consentimento LGPD
  por botões, Voltar/Cancelar, pós-booking; cliente resolvido fora da conversa; adaptador WhatsApp
  interativo atrás de `GUIDED_BOOKING_WHATSAPP_ENABLED`; **recuperação fail-soft** (E7).
- **Robustez** — fixes de timezone (E8), validação de slot (E9), render WhatsApp (E10), upsert (E11),
  versão única (E12), normalização multimodal (E13).
- **Documentação** — `docs/SOLUTION_ARCHITECTURE.md`, `docs/BPMN.md`, `docs/TECH_STACK.md`,
  `docs/DER.md` e este playbook.
- **Release 1.2.0** — `_APP_VERSION`, `CHANGELOG.md`. (Tag/Release no momento do commit pelo dono.)

Verificação ao longo do ciclo: **696 testes** (`-m "not llm_behavior"`), cobertura **~70%** (gate 50),
tenant/adversarial verdes (**17** + **49**), ruff/ESLint limpos, build + vitest (46) ok.

---

## 3. Metodologia de construção (checklist uniforme p/ agentes)

> Antes de codar, leia [`CLAUDE.md`](../CLAUDE.md) (fonte da verdade) e siga estes princípios.

**Roteamento & flags**
- [ ] Mudança que altera roteamento/triagem entra **atrás de flag**; default = comportamento de produção.
- [ ] Não tocar `booking_executor` nem o grafo LangGraph (`compile.py`) sem necessidade — caminho estável.

**Tempo & dados**
- [ ] **Sempre** fuso da org (`now_local_naive(tzname)` / converter para aware). Nunca `date.today()`
      do servidor nem `sa[:10]` de string UTC para lógica de dia.
- [ ] **Uma fonte de verdade** por regra/valor (ex.: `financial.py`, `_APP_VERSION`).

**Robustez (fail-closed)**
- [ ] Validar **toda** entrada/seleção do usuário antes de persistir.
- [ ] Toda I/O externa, parse (`fromisoformat`) e fallback de DB dentro de `try`; erro **amigável** ao
      usuário e detalhe só no log (sem vazar token/PII).
- [ ] Estado in-memory é volátil (sessão guiada, rate limit, cooldown) → **recuperação graciosa**,
      nunca vazar para outro caminho em silêncio.

**Reuso > reinvenção**
- [ ] Procurar util existente antes de criar: `routing.message_text`, `routing.is_booking_data_reply`,
      helpers de timezone (`timezone_utils`), `eligibility.*`, `guardrails.*`.

**Canais & compliance**
- [ ] WhatsApp interativo: ≤3 opções → botões, senão lista (≤10); títulos curtos (Meta).
- [ ] Mudança que toca dado pessoal → checar `packages/compliance/` + LGPD ([`CLAUDE.md` §19](../CLAUDE.md));
      opt-out precisa ser **persistido**.

**Testes**
- [ ] Mocks com `**kwargs` tolerante; E2E asserta por `data-testid` (não por texto interno).
- [ ] Sem datas hardcoded — congelar com o padrão `_FixedToday`.
- [ ] Rodar `ruff` + `pytest -m "not llm_behavior"` + (front) `build`/`vitest`/`eslint` antes de concluir.

**Higiene & processo**
- [ ] Remover código morto na mesma mudança que o tornou órfão.
- [ ] Não versionar artefatos (test-results, caches); conferir `git status` antes do commit.
- [ ] Fluxo: explorar → planejar → implementar → **verificar** → documentar na fonte da verdade
      (CLAUDE.md/CHANGELOG no mesmo PR).

---

## 4. Dívida conhecida em aberto

| Item | Onde | Referência |
|------|------|------------|
| Consentimento "Discordo" não persiste (E14) | `consent.py` — falta `privacy_declined_at` | [`CLAUDE.md` §20](../CLAUDE.md) |
| Deprecação OpenAI `gpt-4o`/`4o-mini` → 5.x | `MODEL_NAME`/`VISION_MODEL_NAME` | [`CLAUDE.md` §48.1](../CLAUDE.md) |
| Rate limit/cooldown in-process (bloqueia `scale>1`) | slowapi, guardrails, session_store | [`CLAUDE.md` §20, §48.3](../CLAUDE.md) |
| Drift de TZ no `booking_executor` (texto livre) | guardrails default `date.today()` (pré-existente) | [`CLAUDE.md` §48](../CLAUDE.md) |
| Financeiro do ano lê todas as linhas | `dashboard.py` (sem cap; agregação no banco = v2.0) | [`SOLUTION_ARCHITECTURE.md`](SOLUTION_ARCHITECTURE.md) |
