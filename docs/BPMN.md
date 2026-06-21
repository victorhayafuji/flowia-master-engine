# BPMN — Processos de Negócio (FlowIA Master Engine · MVP salão)

> Processos de negócio do produto ativo (`PRODUCT_LINE=salon`) em notação **BPMN-style**
> (Mermaid `flowchart` com *lanes* via `subgraph`: **Cliente · IA/Engine · Sistema/DB · Humano**).
> Não é BPMN 2.0 XML estrito — é a representação versionável no repositório.
>
> Fonte: [`CLAUDE.md`](../CLAUDE.md) §4, §6, §22–§24. Escopo: **MVP ativo**. Processos futuros
> (jornada do cliente, reagendamento inteligente) → [`CLAUDE.md` Parte VIII](../CLAUDE.md).

Convenção das lanes:
- **Cliente** — pessoa no WhatsApp / chat de teste.
- **IA/Engine** — LangGraph + motor híbrido determinístico (`packages/engine`, `packages/scheduling`).
- **Sistema/DB** — FastAPI, Supabase, APScheduler.
- **Humano** — dono/recepção do salão (handoff, dashboard).

---

## 1. Agendamento conversacional (WhatsApp / chat) — processo principal

```mermaid
flowchart TD
    subgraph Cliente
        A([Mensagem recebida]) --> B{1ª interação?}
        B -- sim --> Bc[Lê aviso LGPD]
        Bc --> Bd{Consente?}
        Bd -- "Discordo" --> Z([Encerra])
        R1[Responde: serviço / data / nome+telefone]
        Rfaq[Pergunta dúvida - FAQ]
    end

    subgraph IA/Engine
        T[Triagem: keyword / sticky / conversa / LLM]
        T --> RT{Intenção}
        RT -- agendar --> SC[Executor determinístico - booking]
        RT -- "dúvida/preço" --> RAG[Recepcionista + RAG search_kb]
        RT -- política --> SUP[Suporte + RAG]
        SC --> HY{Guiado x texto-livre}
        HY -- guiado --> GS[Passos por seleção - guided_booking]
        HY -- texto-livre --> EX[booking_executor + intent_extractor]
        CA[check_availability - motor de slots]
        BK[book_time - vincula sender_phone]
        AMB{Data ambígua?}
    end

    subgraph Sistema/DB
        GATE[evaluate_consent_gate] 
        SLOTS[(working_hours, breaks, blocks, appointments)]
        INS[(Insert appointment + upsert patient)]
        OVL{Conflito de horário?}
        OUT[Resposta enviada - WhatsApp/chat]
    end

    subgraph Humano
        HND[Atende handoff no dashboard]
    end

    A --> GATE
    Bd -- "Concordo / continua" --> T
    R1 --> T
    Rfaq --> T
    SC --> CA --> SLOTS
    GS --> CA
    EX --> CA
    CA --> AMB
    AMB -- sim --> OUT
    AMB -- não --> BK
    BK --> OVL
    OVL -- "sim (409)" --> OUT
    OVL -- não --> INS --> OUT
    RAG --> OUT
    SUP --> OUT
    OUT --> Cliente
    RAG -. "request_human_handoff" .-> HND
```

**Regras-chave:** consentimento antes de qualquer processamento ([§19](../CLAUDE.md)); `book_time`
vincula ao `sender_phone` (anti prompt-injection); ambiguidade temporal é fail-closed
(`needs_clarification`); conflito de horário → **HTTP 409**; guiado é opt-in (chat dev sempre;
WhatsApp atrás de `GUIDED_BOOKING_WHATSAPP_ENABLED`).

### 1a. Subprocesso — FAQ por tópicos (retorno ao fluxo determinístico)

```mermaid
flowchart LR
    M[Menu: Agendar x Tirar dúvida] --> F[Tópicos: preços/horário/cancelamento/pagamento]
    F --> Q[Pergunta canônica → LLM + RAG]
    Q --> Ans[Resposta + botões]
    Ans --> Back{Próximo passo}
    Back -- "Agendar serviço" --> M
    Back -- "Outra dúvida" --> F
```

---

## 2. Agendamento via dashboard (recepção / profissional)

```mermaid
flowchart TD
    subgraph Humano
        U([Abre /agenda]) --> S[Seleciona slot / modal / drag-drop]
        S --> C[POST /scheduling ou /scheduling/calendar/:id]
    end
    subgraph Sistema/DB
        C --> V{Overlap?}
        V -- "sim" --> E409[HTTP 409 DoubleBookingError]
        V -- não --> P[(Persiste appointment)]
        P --> RM[Cria lembretes em background]
        P --> UI[Atualiza calendário]
    end
    E409 --> Humano
    UI --> Humano
```

Reagendamento (`POST /scheduling/calendar/{id}`) refaz a checagem de conflito antes de persistir e
atualiza os lembretes. Correção manual de status via `PATCH .../status`
(entra/sai de `no_show` ajusta `patients.no_show_count`).

---

## 3. Onboarding de tenant + conexão WhatsApp self-service

```mermaid
flowchart TD
    subgraph Humano
        OA([org_admin em Configurações]) --> Cred[Cola phone_id + access_token Meta]
        Cred --> Test[Clica Testar conexão]
        Pub[Copia webhook_url + verify_token p/ colar na Meta]
    end
    subgraph Sistema/DB
        Test --> Graph[POST /organizations/whatsapp/test → Graph API Meta]
        Graph --> OK{Credenciais válidas?}
        OK -- sim --> Save[(PATCH /organizations/whatsapp — token mascarado)]
        OK -- não --> Err[Erro amigável - sem vazar token]
        Save --> Pub
    end
    Err --> Humano
    Pub --> Humano
```

Modelo "cliente traz a própria conta" (credenciais Meta por org). Embedded Signup (1 clique) é
**futuro** ([§36](../CLAUDE.md)).

---

## 4. Pipeline RAG Medallion (Data Lake)

```mermaid
flowchart LR
    subgraph Humano
        D([dev/super_admin em /admin/data-lake]) --> Up[Upload documento]
    end
    subgraph Sistema/DB
        Up --> Br[(Bronze: docs_bronze + Storage)]
        Br --> OCR[OCR OpenAI Vision]
        OCR --> Si[(Silver: docs_silver)]
        Si --> Emb[Embeddings text-embedding-3-small]
        Emb --> Go[(Gold: docs_gold_vectors - pgvector)]
    end
    subgraph IA/Engine
        Go --> KB[search_kb - busca semântica tenant-aware]
    end
```

Dedup no Bronze por `content_hash`; concorrência de OCR limitada por `asyncio.Semaphore`.

---

## 5. Lembretes e detecção de no-show (APScheduler)

```mermaid
flowchart TD
    subgraph Sistema/DB
        J([Job APScheduler]) --> Due[Lembretes pendentes - 24h / 2h]
        Due --> Cred{Org tem credenciais Meta?}
        Cred -- sim --> Send[WhatsAppService envia] --> Mark[(status=sent)]
        Cred -- não --> Fail[(mark_failed)]
        NS([Job no-show]) --> Det[Detecta ausência] --> Inc[(no_show_count += 1)]
    end
```

---

## Processos fora do MVP (somente ponteiro)

Régua pós-atendimento (D+3/D+30/D+45), ficha pré-atendimento, áudio/transcrição, simulação por
selfie e **reagendamento inteligente / recuperação de no-show** são **futuros** —
[`CLAUDE.md` Parte VIII §42 e §49](../CLAUDE.md). Não fazem parte deste BPMN do MVP.
