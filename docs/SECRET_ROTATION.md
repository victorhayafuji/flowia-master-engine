# Rotação de Secrets — Flowia Master Engine

Execute este checklist se o arquivo `.env` foi compartilhado, commitado por engano ou exposto em logs/chat.

## Prioridade crítica (rotacionar imediatamente)

| Secret | Onde rotacionar | Variável `.env` |
|--------|-----------------|-----------------|
| OpenAI API Key | [OpenAI Platform](https://platform.openai.com/api-keys) | `OPENAI_API_KEY` |
| Supabase anon key | Supabase → Settings → API | `SUPABASE_KEY`, `VITE_SUPABASE_KEY` |
| Supabase service role | Supabase → Settings → API | `SUPABASE_SERVICE_ROLE` |
| JWT secret | Gerar novo (32+ chars aleatórios) | `DASHBOARD_JWT_SECRET` |
| Dashboard API key | Gerar novo UUID/hex | `DASHBOARD_API_KEY` |
| WhatsApp verify token | Meta Developer Console | `WHATSAPP_VERIFY_TOKEN` |
| WhatsApp app secret | Meta Developer Console | `WHATSAPP_APP_SECRET` |
| DB password | Supabase → Database → Settings | `SUPABASE_DB_URL` |

## Após rotacionar

1. Atualize o `.env` na raiz do projeto com os novos valores.
2. Reinicie backend e frontend (`start_flowia.bat` ou uvicorn + `npm run dev`).
3. Todos os usuários precisarão fazer login novamente (JWT antigo invalida).
4. Atualize secrets no **Render Dashboard** → serviço `flowia-api` / `flowia-dashboard` → Environment (sync off). Redeploy após alterar `VITE_*` no Static Site.
5. Revogue as chaves antigas nos painéis (OpenAI, Supabase, Meta) — não apenas substitua.

## Gerar novos valores localmente

```bash
# JWT secret (Python)
python -c "import secrets; print(secrets.token_urlsafe(48))"

# Dashboard API key (Python)
python -c "import secrets; print(secrets.token_hex(32))"
```

## Verificar configuração

```bash
python scripts/check_env.py
```

## Prevenção

- `.env` está no `.gitignore` — nunca faça `git add .env`
- Use `.env.example` apenas com placeholders
- Em produção, use Render Environment (sync off) — nunca commitar secrets
- `VITE_DEV_EMAIL` / `VITE_DEV_PASSWORD` são **apenas para desenvolvimento local**
