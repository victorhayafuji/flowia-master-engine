# Produção — URLs, smoke e rollback

Registro operacional do deploy Render (Jun/2026). Detalhes de deploy: [`RENDER.md`](RENDER.md).

**Antes do 1º cliente pagante:** ler [`TENANCY_AND_SCALE.md`](TENANCY_AND_SCALE.md) (ambiente prod vs onboarding de salão) e [`SECURITY_GO_LIVE_CHECKLIST.md`](SECURITY_GO_LIVE_CHECKLIST.md) (auditoria piloto + Trilha B corporativa).

## Piloto atual vs recomendado

| Aspecto | Piloto atual (Jun/2026) | Recomendado antes de clientes pagantes |
|---------|-------------------------|----------------------------------------|
| Supabase | Mesmo projeto do dev local (`vwhsivwoiiicydanypmo`) | Projeto Supabase **separado** + secrets novos |
| Secrets | Copiados do `.env` local para Render | `generate_prod_secrets.py` — nunca reutilizar dev |
| WhatsApp | Não configurado | Credenciais Meta por org — ver [`WHATSAPP_SETUP.md`](WHATSAPP_SETUP.md) |

## URLs

| Serviço | URL | Notas |
|---------|-----|-------|
| API Render | https://flowia-api.onrender.com | Web Service `flowia-api` (`srv-d8if4437uimc73ammat0`) |
| Dashboard Render | https://flowia-dashboard.onrender.com | Static Site `flowia-dashboard` (`srv-d8if463tqb8s73b38rog`) |
| Landing FlowIA | https://flowia-landing.onrender.com | Static Site `flowia-landing` (`srv-d8jl0mhkh4rs73e8o0vg`) — **live** Jun/2026 |
| Supabase | https://vwhsivwoiiicydanypmo.supabase.co | Piloto: mesmo projeto do dev local |
| Webhook WhatsApp (futuro) | https://flowia-api.onrender.com/api/v1/webhook/whatsapp | Aguardando credenciais Meta |

## Monitoramento via Render MCP (Cursor)

Permite consultar deploys, logs e serviços sem abrir o Dashboard manualmente.

1. Criar API key: [Render → Settings → API Keys](https://dashboard.render.com/u/*/settings#api-keys)
2. Adicionar em `~/.cursor/mcp.json` ( **nunca commitar** a key):

```json
{
  "mcpServers": {
    "render": {
      "url": "https://mcp.render.com/mcp",
      "headers": {
        "Authorization": "Bearer SUA_API_KEY"
      }
    }
  }
}
```

3. Reiniciar Cursor → selecionar **workspace** na primeira consulta MCP
4. Validar: serviços `flowia-api` e `flowia-dashboard` listados; último deploy **live**

Consultas úteis ao agente: status do deploy pós-merge, logs de startup (`Supabase conectado`), erros webhook.

---

## Rotina semanal de manutenção

Cadência fixa (~1–2h) enquanto o produto amadurece sem WhatsApp Meta. Detalhes em [`STAGING.md`](STAGING.md) § Manutenção mensal.

| Dia sugerido | Ação |
|--------------|------|
| Pós-deploy | Smokes automatizados (bloco abaixo) |
| Semanal | Checklist manual #7 e #8 (procedimento abaixo) |
| Semanal | Revisar CI GitHub Actions — backend, dashboard, E2E, landing |

### Checklist manual #7 — CRUD cliente + agenda (prod)

1. Login em https://flowia-dashboard.onrender.com como `dono@beauty-express.com`
2. **Clientes** → criar cliente teste (nome + telefone único) → editar → desativar ou manter
3. **Agenda** → criar agendamento no slot livre → arrastar para reagendar → confirmar sem 409
4. Marcar #7 OK na tabela abaixo com data

### Checklist manual #8 — Chat Test + Observabilidade (DEV local)

Requer `super_admin` + `npm run dev` (ou build preview):

1. `/admin/chat-test` → enviar `"Quero mechas sexta"` → badges `path=deterministic`, `triage=keyword`
2. `/admin/observability` → KPI determinístico + tabela conversas carrega (super_admin; **prod e dev**)
3. Overview como `org_admin` → cards *Assistente IA* (handoffs, WhatsApp hoje, conversas semana) — ver [`AGENT_OBSERVABILITY.md`](AGENT_OBSERVABILITY.md)
4. Marcar #8 OK na tabela abaixo com data

---

## Health check Render

O probe HTTP exige resposta em menos de **5s** em `/health`. A API sobe o listener imediatamente e aquece checkpointer/Supabase/scheduler em **background** (`apps/salon/api/startup_warmup.py`). Rotas de negócio retornam **503** até `ready=true` no JSON de `/health`.

## Smoke pós-deploy (comandos)

Ordem recomendada após cada deploy em `main`:

```powershell
# 1. Health + dashboard estático
venv\Scripts\python.exe scripts\smoke_prod.py `
  --api-url https://flowia-api.onrender.com `
  --dashboard-url https://flowia-dashboard.onrender.com

# 2. Motor híbrido (login + chat/test + today-board)
$env:PROD_SMOKE_PASSWORD = "sua-senha-piloto"
venv\Scripts\python.exe scripts\smoke_hybrid_prod.py `
  --api-url https://flowia-api.onrender.com `
  --username dono@beauty-express.com

# 3. Agente genérico (RAG + hybrid scheduling)
venv\Scripts\python.exe scripts\smoke_agent.py `
  --api-url https://flowia-api.onrender.com/api/v1 `
  --password $env:PROD_SMOKE_PASSWORD

# 4. Migrações aplicadas no Supabase remoto
venv\Scripts\python.exe scripts\list_db_migrations.py
```

**Senha:** usar env `PROD_SMOKE_PASSWORD` — nunca commitar. Piloto local: seed `dono@beauty-express.com`.

### Validação Supabase (métricas híbrido)

Após `smoke_hybrid_prod.py`, no SQL Editor:

```sql
SELECT thread_id, agent_type, scheduling_path, triage_source, channel, tokens_total, created_at
FROM conversation_metrics
ORDER BY created_at DESC
LIMIT 5;
```

Esperado: `channel=chat_test`, `scheduling_path=deterministic`, `agent_type=scheduling`.

---

## Checklist smoke (pós-motor híbrido)

| # | Teste | Automatizado | Data | OK? |
|---|-------|--------------|------|-----|
| 1 | `/health` database connected | `smoke_prod.py` | 2026-06-08 | Sim |
| 2 | Login org_admin (API) | `smoke_hybrid_prod.py` | 2026-06-08 | Sim |
| 3 | Dashboard HTTP 200 | `smoke_prod.py` | 2026-06-08 | Sim |
| 4 | SPA `/agenda` rewrite | Manual browser | 2026-06-07 | Sim |
| 5 | Hybrid chat `"Quero mechas sexta"` → `path=deterministic` | `smoke_hybrid_prod.py` | 2026-06-08 | Sim |
| 6 | `GET /dashboard/today-board` | `smoke_hybrid_prod.py` | 2026-06-08 | Sim |
| 7 | CRUD cliente + agendamento drag | Manual browser + API smoke | 2026-06-07 | Sim (API create/reschedule; drag UI manual) |
| 8 | Chat Test badges (super_admin DEV) | API pós-consent + DEV UI | 2026-06-07 | Sim (API: path=deterministic; UI badges DEV local) |
| 9 | `conversation_metrics` observability | Supabase SQL | 2026-06-08 | Sim |
| 10 | Migration `20260610060000` aplicada | `list_db_migrations.py` | 2026-06-07 | Sim (22 total) |
| 11 | Landing `/privacidade` live | HTTP + browser | 2026-06-07 | Sim |
| 12 | Chat Test aviso LGPD (L1/L2) | API `/chat/test` | 2026-06-07 | Sim |
| 13 | Export/Erase Clientes (L3/L4) | API compliance | 2026-06-07 | Sim (após fix `717dda9`) |

### Última execução registrada

Ver seção **Resultado smoke 2026-06-07 (pós-merge LGPD)** abaixo.

---

## Rollback

### API (Render)

1. Dashboard → **flowia-api** → Deploys
2. Selecionar deploy anterior estável → **Rollback**
3. Verificar `/health`

### Dashboard (Render)

1. Dashboard → **flowia-dashboard** → Deploys → Rollback
2. Ou redeploy com `VITE_*` corrigidos

### Supabase

1. Point-in-time recovery (Dashboard → Database → Backups) se migration corrompeu dados
2. **Não** rodar `seed_salon.py` em prod sem backup — sobrescreve demo org

### CORS / cookie

Sintoma: login 401/403 ou CORS no browser.

1. `ALLOWED_ORIGINS` na API = URL **exata** do Static Site (HTTPS, sem trailing slash inconsistente)
2. `COOKIE_SECURE=true` na API (cookie `SameSite=None` + `Secure` para subdomínios Render distintos)
3. `VITE_API_URL` no build = `https://flowia-api.onrender.com/api/v1`
4. Redeploy dashboard após corrigir `VITE_*`

## Supabase migrations (aplicadas)

**22 migrations** sincronizadas via `scripts/apply_migrations.py` (Jun/2026), incluindo:

- `20260610050000_conversation_metrics_sender_text.sql`
- `20260610060000_lgpd_consent.sql` — colunas `patients.privacy_*`

Verificar: `python scripts/list_db_migrations.py` → **Total: 22**

Colunas LGPD confirmadas: `privacy_notice_version`, `privacy_notice_shown_at`, `privacy_consent_at`, `privacy_consent_channel`.

## Pré-requisito 1º cliente pagante (backlog)

Documentado em [`TENANCY_AND_SCALE.md`](TENANCY_AND_SCALE.md):

- Supabase projeto **separado** prod vs dev
- Rotação secrets (`docs/SECRET_ROTATION.md`, `scripts/check_env.py`)
- Cron TTL `webhook_message_dedup` (retenção 7 dias)

## Contatos / credenciais

- org_admin piloto: `dono@beauty-express.com` (Beauty Express org)
- super_admin plataforma: `admin@flowia.com` (setup local)

Secrets: Render Environment (sync off) — nunca commitar.

**LGPD (Jun/2026):**

| Variável | Valor prod | Notas |
|----------|------------|-------|
| `PRIVACY_POLICY_URL` | `https://flowia-landing.onrender.com/privacidade` | Configurado pós-deploy landing |
| `PRIVACY_CONTACT_EMAIL` | *(default código)* `privacidade@exemplo.com` | **Trocar antes do 1º cliente pagante** |
| `SCHEDULER_ENABLED` | `true` | Retenção LGPD + dedup webhook |
| `CONVERSATION_METRICS_RETENTION_DAYS` | default `365` | Opcional no Dashboard |
| `CHECKPOINT_RETENTION_DAYS` | default `90` | Opcional no Dashboard |

## Resultado smoke 2026-06-08

Pós-deploy motor híbrido (`feat/hybrid-scheduling-agent` → `main`).

```text
smoke_prod.py          → OK (health connected, dashboard HTTP 200)
smoke_hybrid_prod.py   → OK (login, auth/me org_admin, turno1 path=deterministic triage=conversation tokens=0, turno2 scheduling, today-board pros=2)
smoke_agent.py         → OK (RAG + hybrid scheduling path=deterministic)
list_db_migrations.py  → 21 migrations (incl. observability + sender_id TEXT)
```

**Thread smoke híbrido:** `29bcf654-21df-4070-8ac9-4ccd423ec936` — métricas gravadas com `scheduling_path=deterministic`.

**Nota:** primeira requisição após cold start Render pode timeout (~30s); repetir se `/health` falhar.

**Pendente manual:** drag-and-drop na Agenda (#7 UI) e badges visuais no browser DEV (#8 UI).

---

## Resultado smoke 2026-06-07 (pós-merge LGPD)

Pós-merge PR #7 + migration LGPD + landing + env Render.

```text
apply_migrations.py     → OK (20260610060000_lgpd_consent.sql aplicada; Total: 22)
list_db_migrations.py   → 22 migrations
privacy_* columns       → OK (4 colunas em patients)
Render flowia-api env   → PRIVACY_POLICY_URL + SCHEDULER_ENABLED=true; redeploy OK
flowia-landing          → CRIADO (srv-d8jl0mhkh4rs73e8o0vg); /, /privacidade, /termos HTTP 200
smoke_prod.py           → OK (health connected, dashboard HTTP 200)
smoke_hybrid_prod.py    → PARCIAL — turno1 agent=compliance (aviso LGPD esperado); turno2 scheduling OK quando API estável
smoke_agent.py          → OK (scheduling híbrido path=deterministic); 1ª msg RAG retorna aviso LGPD (esperado)
fix export DSAR         → commit 717dda9 — removido appointments.notes inexistente
L5 privacy-notice       → OK version=2026-06
L1/L2 consent chat      → OK (compliance → scheduling mesma thread)
L3/L4 export/erase      → OK format=flowia-dsar-v1 / status=erased (pós 717dda9)
#7 CRUD agenda (API)    → OK create patient + appointment + reschedule
#8 chat badges (API)    → OK path=deterministic triage=conversation (2º turno pós-consent)
```

**Consent no DB (amostra pós-smoke):** threads chat_test com `privacy_notice_shown_at` e `privacy_consent_at` preenchidos.

**Nota smoke híbrido:** após LGPD, `smoke_hybrid_prod.py` turno1 deve passar a esperar `agent=compliance` na 1ª mensagem de thread nova — atualizar script em follow-up.

**Pendente:** `PRIVACY_CONTACT_EMAIL` real antes do 1º cliente pagante; revisão jurídica DRAFTs em `docs/legal/`.

---

## WhatsApp Meta — checklist Semana 1

Pré-requisito: conta Meta Business + número WhatsApp Business API. Runbook: [`WHATSAPP_SETUP.md`](WHATSAPP_SETUP.md).

**Infra código (Jun/2026):** `thread_id` org-scoped, UNIQUE `whatsapp_phone_id`, fila `whatsapp_inbound_jobs` + worker Render (`WHATSAPP_QUEUE_MODE`). Ativar worker separado após W3.

### Migrations pendentes (aplicar antes do go-live WhatsApp)

Arquivos locais aplicados no Supabase remoto **`vwhsivwoiiicydanypmo`** via MCP plugin (Jun/2026):

| Migration | Conteúdo | Status remoto |
|-----------|----------|---------------|
| `whatsapp_phone_id_unique` | UNIQUE parcial em `organizations.whatsapp_phone_id` | **Aplicada** (`20260609200047`) |
| `whatsapp_inbound_jobs` | Fila FIFO + RLS interno | **Aplicada** (`20260609200106`) |

Validação: tabela `whatsapp_inbound_jobs` visível; índice `idx_organizations_whatsapp_phone_id_unique` ativo.

**Ordem (referência local):**

1. Pré-check: `py scripts/check_whatsapp_phone_duplicates.py` (ou SQL abaixo no Editor)
2. Aplicar: Supabase Dashboard → SQL Editor → colar conteúdo dos dois arquivos **ou** `py scripts/apply_pending_whatsapp_migrations.py` (requer `SUPABASE_DB_URL` acessível)
3. Validar: `SELECT to_regclass('public.whatsapp_inbound_jobs');` → não nulo

```sql
-- Pré-check duplicatas (deve retornar 0 linhas)
SELECT whatsapp_phone_id, COUNT(*)
FROM organizations
WHERE whatsapp_phone_id IS NOT NULL AND whatsapp_phone_id <> ''
GROUP BY whatsapp_phone_id HAVING COUNT(*) > 1;
```

Pré-check remoto (Jun/2026): **0 duplicatas** no projeto piloto.

| # | Onde | Ação | Status |
|---|------|------|--------|
| W1 | Render `flowia-api` | `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` | Pendente credenciais |
| W2 | Supabase ou API | Beauty Express: `PATCH /api/v1/organizations/{id}/whatsapp` ou SQL — `whatsapp_phone_id`, `whatsapp_access_token` | Pendente |
| W3 | Meta Developer Console | Webhook URL `https://flowia-api.onrender.com/api/v1/webhook/whatsapp` | Pendente |
| W4 | Celular real | 3 turnos agendamento → métricas `channel=whatsapp`, `scheduling_path=deterministic` | Pendente |
| W5 | Este doc | Registrar resultado na tabela smoke abaixo | Pendente |

Simulação local (sem Meta): `python scripts/simulate_whatsapp_webhook.py` + `SIM_WHATSAPP_ORG_ID` no `.env`.

### Critério done WhatsApp E2E

```sql
SELECT thread_id, scheduling_path, triage_source, channel, created_at
FROM conversation_metrics
WHERE channel = 'whatsapp'
ORDER BY created_at DESC
LIMIT 5;
```

Esperado: pelo menos 1 linha com `scheduling_path=deterministic` após fluxo de agendamento no celular. `thread_id` esperado: `{organization_id}:{telefone}` (ex.: `22222222-...:5511999999999`).

---

## Observabilidade — parsing de datas (`date_parse`)

O parser temporal em `packages/scheduling/date_parsing.py` emite logs estruturados (nível INFO, sem PII):

```
date_parse | outcome=resolved reason=- kind=weekday
date_parse | outcome=clarify reason=week_without_weekday kind=clarification
date_parse | outcome=none reason=- kind=-
```

| `outcome` | Significado |
|-----------|-------------|
| `resolved` | ISO futuro (booking) ou referência válida |
| `clarify` | Ambiguidade — booking fail-closed; bot deve perguntar dia |
| `none` | Sem data detectada |

**Alerta operacional:** após deploy, buscar nos logs da API Render `date_parse | outcome=clarify`. Taxa alta em frases como `semana que vem` ou `sexta ou sábado` indica UX de clarificação funcionando; taxa inesperada em mensagens já resolvidas sugere regressão no parser.

Razões de clarificação: `week_without_weekday`, `multiple_weekdays`, `past_this_week`, `week_hint_only`, `day_without_month`.

---

## Landing FlowIA (marketing)

| Campo | Valor |
|-------|-------|
| Serviço Render | `flowia-landing` (Static Site `srv-d8jl0mhkh4rs73e8o0vg`) |
| URL | https://flowia-landing.onrender.com |
| Código | [`apps/landing/`](../apps/landing/) |
| Deploy | Criado via Render API Jun/2026; auto-deploy `main` |
| Status | **Live** — `/`, `/privacidade`, `/termos` HTTP 200 |

Copy e SEO: [`docs/marketing/FLOWIA_LANDING_COPY.md`](marketing/FLOWIA_LANDING_COPY.md).
