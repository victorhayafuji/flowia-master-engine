# DER — Modelo de Dados (FlowIA Master Engine · MVP salão)

> Diagrama Entidade-Relacionamento e dicionário de dados do produto ativo
> (`PRODUCT_LINE=salon`). Fonte canônica: [`CLAUDE.md` §14](../CLAUDE.md) + as migrations em
> [`supabase/migrations/`](../supabase/migrations/). Em divergência, **o CLAUDE.md prevalece**.
>
> Escopo: **MVP ativo**. Tabelas de stub/futuro (`appointment_payments`, `anamnesis_*`) aparecem
> marcadas. Visão pós-MVP: [`CLAUDE.md` Parte VIII](../CLAUDE.md).

## 1. Visão geral

Banco **PostgreSQL (Supabase)**, multi-tenant por `organization_id` + **Row Level Security (RLS)**.
O backend usa `SERVICE_ROLE` (ignora RLS) — o isolamento no caminho do agente é reforçado em
aplicação (ver [`SOLUTION_ARCHITECTURE.md`](SOLUTION_ARCHITECTURE.md) §Segurança). Três grupos de
tabelas:

- **Negócio** (têm `organization_id` + RLS): organizations, professionals, service_catalog,
  service_professionals, patients, appointments, reminders, schedule_blocks, appointment_payments (stub).
- **Data Lake** (RAG Medallion): docs_bronze, docs_silver, docs_gold_vectors.
- **Internas** (sem `organization_id`, RLS sem policies, backend-only): checkpoints\*,
  webhook_message_dedup, whatsapp_inbound_jobs.

## 2. DER — entidades de negócio

```mermaid
erDiagram
    organizations ||--o{ professionals : tem
    organizations ||--o{ service_catalog : tem
    organizations ||--o{ patients : tem
    organizations ||--o{ appointments : tem
    organizations ||--o{ schedule_blocks : tem
    organizations ||--o{ dashboard_users : tem

    patients ||--o{ appointments : "agenda (patient_id)"
    professionals ||--o{ appointments : "executa (professional_id)"
    service_catalog ||--o{ appointments : "serviço (service_id)"

    service_catalog ||--o{ service_professionals : elegibilidade
    professionals ||--o{ service_professionals : elegibilidade

    professionals ||--o{ schedule_blocks : "folga/feriado"
    dashboard_users }o--|| professionals : "login funcionário (professional_id)"

    appointments ||--o{ reminders : dispara
    appointments ||--o| appointments : "rescheduled_from (self)"
    appointments ||--o{ appointment_payments : "cobrança (stub)"

    organizations {
        uuid id PK
        text name
        text slug
        text vertical "salon|dental|medical"
        text whatsapp_phone_id "UNIQUE parcial (NOT NULL/não vazio)"
        text whatsapp_access_token
        text whatsapp_business_id
        jsonb settings "scheduling, integrations.payments, journey(futuro)"
        text timezone
        bool is_active
    }
    professionals {
        uuid id PK
        uuid organization_id FK
        text name
        text specialty
        jsonb working_hours "por dia da semana"
        jsonb break_times
        int appointment_buffer_minutes
        bool is_active "soft delete"
    }
    service_catalog {
        uuid id PK
        uuid organization_id FK
        text name
        int duration_minutes
        numeric price
        uuid professional_id FK "legado/compat (nullable)"
        bool requires_anamnesis "futuro"
        int recall_days "futuro"
        bool is_active "UNIQUE(org, lower(name)) WHERE is_active"
    }
    service_professionals {
        uuid organization_id FK
        uuid service_id FK "PK, ON DELETE CASCADE"
        uuid professional_id FK "PK, ON DELETE CASCADE"
    }
    patients {
        uuid id PK
        uuid organization_id FK
        text name
        text phone "UNIQUE(organization_id, phone)"
        text email
        jsonb tags
        int no_show_count
        int total_appointments
        timestamptz last_visit_at
        text legacy_sender_id "vínculo WhatsApp"
        timestamptz handoff_requested_at
        text handoff_reason
        timestamptz privacy_notice_shown_at "LGPD"
        timestamptz privacy_consent_at "LGPD"
        text privacy_consent_channel "whatsapp|chat_test|dashboard"
        text privacy_notice_version
        bool is_active "soft delete"
    }
    appointments {
        uuid id PK
        uuid organization_id FK
        uuid patient_id FK
        uuid professional_id FK
        uuid service_id FK
        timestamptz scheduled_at
        int duration_minutes
        text status "pending|confirmed|arrived|in_progress|completed|no_show|cancelled|rescheduled"
        text source "whatsapp|dashboard|api|phone"
        uuid rescheduled_from FK "self, futuro"
        text cancellation_reason "futuro"
        text notes
    }
    reminders {
        uuid id PK
        uuid organization_id FK
        uuid appointment_id FK
        text type "confirmation_24h|reminder_2h|post_service|recall|satisfaction|reactivation"
        text status "pending|sent|delivered|failed|cancelled"
        timestamptz scheduled_for
        jsonb metadata
    }
    schedule_blocks {
        uuid id PK
        uuid organization_id FK
        uuid professional_id FK "nullable = org inteira"
        timestamptz starts_at
        timestamptz ends_at "CHECK ends_at > starts_at"
        text block_type "time_off|manual|holiday"
        text reason
    }
    dashboard_users {
        uuid id PK
        uuid organization_id FK "nullable p/ super_admin"
        text email
        text password_hash
        text role "super_admin|org_admin|professional"
        uuid professional_id FK "obrigatório se role=professional"
    }
    appointment_payments {
        uuid id PK "STUB / deferido"
        uuid organization_id FK
        uuid appointment_id FK
        int amount_cents
        text currency
        text status "pending|synced|failed|refunded"
        text provider
        text external_id
        jsonb metadata
    }
```

## 3. DER — Data Lake (RAG Medallion) + internas

```mermaid
erDiagram
    docs_bronze ||--o| docs_silver : "OCR (content_hash dedup)"
    docs_silver ||--o{ docs_gold_vectors : "embeddings (pgvector)"

    docs_bronze {
        uuid id PK
        uuid organization_id FK
        text status "PENDING|PROCESSING|COMPLETED|ERROR"
        text content_hash "dedup"
        text storage_path
    }
    docs_silver {
        uuid id PK
        uuid organization_id FK
        text status "SILVER_READY"
        text extracted_text
    }
    docs_gold_vectors {
        uuid id PK
        uuid organization_id FK
        vector embedding "pgvector (text-embedding-3-small)"
        text chunk
    }
    whatsapp_inbound_jobs {
        uuid id PK "interna (RLS sem policies)"
        uuid organization_id
        text message_id "UNIQUE (dedup)"
        text sender_id
        text thread_id
        jsonb payload
        text status "pending|processing|done|failed"
        int attempts
    }
    webhook_message_dedup {
        text message_id PK "interna; purge diário (retention 7d)"
    }
```

> **checkpoints / checkpoint_blobs / checkpoint_writes / checkpoint_migrations** — criadas
> automaticamente pelo `PostgresSaver.setup()` (memória do LangGraph). Internas, RLS sem policies.
> **conversation_metrics** — telemetria por thread (`organization_id`, `scheduling_path`,
> `triage_source`, `channel`, `tools_called`).

## 4. Constraints e integridade (resumo)

| Regra | Onde | Migration |
|-------|------|-----------|
| **Anti double-booking** | `EXCLUDE USING gist` (`appointments_no_overlap`, via `btree_gist`); exclui `cancelled`/`no_show` | `20260607010000_appointment_overlap_guard.sql` |
| **WhatsApp phone único** | UNIQUE parcial em `organizations.whatsapp_phone_id` (NOT NULL e não vazio) | `20260611000000_whatsapp_phone_id_unique.sql` |
| **Serviço ativo único por nome** | `UNIQUE(organization_id, lower(name)) WHERE is_active` | `20260609010000_soft_delete_and_integrity.sql` |
| **Telefone único por org** | `UNIQUE(organization_id, phone)` em `patients` | foundation |
| **M:N serviço↔profissional** | PK composta `(service_id, professional_id)` em `service_professionals` | `20260610010000_service_professionals.sql` |
| **Login funcionário** | `dashboard_users.professional_id` FK | `20260610000000_professional_user_link.sql` |
| **Soft delete** | `is_active=false` (patients, professionals, service_catalog, organizations); listagens filtram | `20260609010000` |
| **FK org = RESTRICT** | `organization_id ON DELETE RESTRICT` nas tabelas de negócio (anti-cascade acidental) | `20260609010000` |
| **updated_at trigger** | `set_updated_at()` + `BEFORE UPDATE` (organizations, patients, appointments, docs_bronze, anamnesis_responses) | `20260609000000_updated_at_triggers.sql` |
| **Dedup webhook** | `webhook_message_dedup` (insert-before-process) + purge diário | `20260607020000` |
| **Fila inbound** | `whatsapp_inbound_jobs` (FIFO, `message_id` UNIQUE) | `20260611010000` |
| **RLS internas** | `ENABLE RLS` + zero policies + `REVOKE anon/authenticated` | `20260608000000_internal_tables_rls.sql` |

## 5. Stub / futuro (schema existe, fluxo não)

- **`appointment_payments`** — pagamentos/PDV (`integrations.payments.enabled=false`). Deferido (Fase 2).
- **`anamnesis_templates` / `anamnesis_responses`**, `service_catalog.requires_anamnesis`,
  `recall_days` — Customer Journey ([`CLAUDE.md` §42](../CLAUDE.md)). **Não implementado.**
- **`appointments.rescheduled_from` / `cancellation_reason`** — Reagendamento Inteligente
  ([`CLAUDE.md` §49](../CLAUDE.md)). Colunas existem; fluxo é futuro.
- Enums `ReminderType.post_service/recall/reactivation/satisfaction` — existem, **ociosos**.

Migrations completas e ordem de aplicação: [`CLAUDE.md` §15](../CLAUDE.md).
