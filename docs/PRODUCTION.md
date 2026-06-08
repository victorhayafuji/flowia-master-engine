# Produção — URLs, smoke e rollback

Registro operacional do deploy Render (Jun/2026). Detalhes de deploy: [`RENDER.md`](RENDER.md).

**Antes do 1º cliente pagante:** ler [`TENANCY_AND_SCALE.md`](TENANCY_AND_SCALE.md) (ambiente prod vs onboarding de salão).

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
| 7 | CRUD cliente + agendamento drag | Manual browser | | Pendente |
| 8 | Chat Test badges (super_admin DEV) | Manual browser | | Pendente |
| 9 | `conversation_metrics` observability | Supabase SQL | 2026-06-08 | Sim |

### Última execução registrada

Ver seção **Resultado smoke 2026-06-08** abaixo (preenchida após rodar scripts).

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

**21 migrations** sincronizadas via `scripts/apply_migrations.py` (Jun/2026), incluindo:

- `20260610040000_conversation_metrics_observability.sql`
- `20260610050000_conversation_metrics_sender_text.sql`

Verificar: `python scripts/list_db_migrations.py`

## Pré-requisito 1º cliente pagante (backlog)

Documentado em [`TENANCY_AND_SCALE.md`](TENANCY_AND_SCALE.md):

- Supabase projeto **separado** prod vs dev
- Rotação secrets (`docs/SECRET_ROTATION.md`, `scripts/check_env.py`)
- Cron TTL `webhook_message_dedup` (retenção 7 dias)

## Contatos / credenciais

- org_admin piloto: `dono@beauty-express.com` (Beauty Express org)
- super_admin plataforma: `admin@flowia.com` (setup local)

Secrets: Render Environment (sync off) — nunca commitar.

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

**Pendente manual:** checklist #7 (CRUD agenda) e #8 (Chat Test badges no browser DEV).

---

## WhatsApp Meta — checklist Semana 1

Pré-requisito: conta Meta Business + número WhatsApp Business API. Runbook: [`WHATSAPP_SETUP.md`](WHATSAPP_SETUP.md).

| # | Onde | Ação | Status |
|---|------|------|--------|
| W1 | Render `flowia-api` | `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` | Pendente credenciais |
| W2 | Supabase `organizations` | Beauty Express: `whatsapp_phone_id`, `whatsapp_access_token` | Pendente |
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

Esperado: pelo menos 1 linha com `scheduling_path=deterministic` após fluxo de agendamento no celular.
