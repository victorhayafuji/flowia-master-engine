# Releases, Fixes e Updates — passo-a-passo

> **Versão canônica do produto:** [SemVer](https://semver.org/lang/pt-BR/) a partir de `_APP_VERSION` em [`apps/salon/api/app_factory.py`](../apps/salon/api/app_factory.py).
> Registro de mudanças: [`CHANGELOG.md`](../CHANGELOG.md) na raiz. Deploy/rollback/smoke: [`PRODUCTION.md`](PRODUCTION.md).

Este doc define **como versionar, corrigir e atualizar** o FlowIA. O fluxo é manual e enxuto — adequado a um time pequeno. Sem ferramenta de release automatizada.

---

## 1. Fonte única de versão

| Onde | Papel |
|------|-------|
| `_APP_VERSION` em [`app_factory.py`](../apps/salon/api/app_factory.py) | **Número canônico** — exposto em `GET /health` e no `version=` do FastAPI (mesma função) |
| Tag git `vX.Y.Z` | **Deve casar** com `_APP_VERSION` |
| Seção do topo em [`CHANGELOG.md`](../CHANGELOG.md) | **Deve casar** com a tag |
| `apps/salon/dashboard/package.json` (`version`) | **Fora do versionamento** — fica `0.0.0`, não é o número do produto |

Regra de ouro: ao cortar uma release, `_APP_VERSION` == tag `vX.Y.Z` == topo do `CHANGELOG.md`.

---

## 2. SemVer + mapa de commits

O repositório usa **conventional commits em PT-BR** (`feat`, `fix`, `test`, `docs`, `chore`, `refactor`). O tipo do commit determina o bump:

| Commit | Bump na próxima release | Exemplo |
|--------|-------------------------|---------|
| `fix:` / `fix(escopo):` | **PATCH** — `X.Y.(Z+1)` | `fix(agenda): bloqueia sábado na grade` |
| `feat:` / `feat(escopo):` | **MINOR** — `X.(Y+1).0` | `feat(whatsapp): self-service org_admin` |
| Quebra de contrato (`feat!:` ou rodapé `BREAKING CHANGE:`) | **MAJOR** — `(X+1).0.0` | mudança de API/schema incompatível |
| `test:` / `docs:` / `chore:` / `refactor:` | **sem release próprio** — entra na próxima | `docs(release): processo de release` |

Rodapé de commit do projeto: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## 3. Fluxo UPDATE (nova feature)

```powershell
git checkout main; git pull
git checkout -b feat/minha-feature
# ... código + testes ...
git push -u origin feat/minha-feature
gh pr create --base main --fill
```

1. PR de `feat/*` → `main`. CI precisa passar (ver [§6](#6-gates-de-ci)).
2. Merge no GitHub → **Render faz auto-deploy** (`autoDeploy: true` em [`render.yaml`](../render.yaml)).
3. Rodar os smokes pós-deploy ([`PRODUCTION.md`](PRODUCTION.md)).
4. Adicionar 1 linha em `CHANGELOG.md` na seção `[Unreleased]` → **Added** (a release sai depois, em lote).

## 4. Fluxo FIX

Igual ao update, mas branch `fix/...` e a entrada vai em `[Unreleased]` → **Fixed**. Bump **PATCH** na próxima release.

## 5. Fluxo HOTFIX (urgente em produção)

Quando prod está quebrado e não dá para esperar o lote:

1. `git checkout -b fix/hotfix-xyz origin/main` → correção mínima → PR → merge.
2. Render auto-deploy → smoke imediato.
3. **Se não estabilizar:** rollback primeiro (Render → Deploys → *Rollback*; ver [`PRODUCTION.md`](PRODUCTION.md)).
4. Cortar **release PATCH imediata** (seção 7) com só esse fix no CHANGELOG.

---

## 6. Gates de CI

Antes de cortar release, CI verde em `main` ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)):

| Job | Gates |
|-----|-------|
| backend | `ruff check` · `pytest --cov-fail-under=50` |
| frontend | `eslint` · `vitest` · `vite build` |

Local (opcional, antes do PR):

```powershell
py -3.12 -m ruff check .
py -3.12 -m pytest -m "not llm_behavior" -q
cd apps/salon/dashboard; npm run lint; npm run test; npm run build
```

---

## 7. Fluxo RELEASE (cortar uma versão)

Checklist completo:

1. **CI verde** em `main` e smokes do último deploy OK.
2. **Bumpar a versão** em [`app_factory.py`](../apps/salon/api/app_factory.py): `_APP_VERSION` **e** o `version=` do `FastAPI(...)` (mesma função) para `X.Y.Z`.
3. **Atualizar `CHANGELOG.md`**: renomear `## [Unreleased]` para `## [X.Y.Z] - AAAA-MM-DD` e abrir uma nova `## [Unreleased]` vazia no topo.
4. **Commit** `chore(release): vX.Y.Z` (via branch `chore/release-vX.Y.Z` + PR, ou direto em `main` se sozinho).
5. **Tag** (anotada) e push:
   ```powershell
   git checkout main; git pull
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```
   > A tag deve apontar para um commit **de `main`** (após o merge).
6. **GitHub Release** (notas = seção do CHANGELOG):
   ```powershell
   gh release create vX.Y.Z --title "vX.Y.Z" --notes-file release-notes.md
   ```
   Fallback se a API do GitHub bloquear: GitHub → *Releases* → **Draft a new release** → escolher a tag → colar as notas.
7. **Validar:** Render deploy `live`, smokes ([`PRODUCTION.md`](PRODUCTION.md)) e `GET /health` retornando `version: X.Y.Z`.

---

## 8. Rollback

Procedimento completo (API, Dashboard, Supabase PITR, CORS/cookie) em [`PRODUCTION.md`](PRODUCTION.md) § Rollback. Resumo:

- **API/Dashboard:** Render → serviço → *Deploys* → *Rollback* para o último deploy estável.
- **Supabase:** Point-in-time recovery se uma migration corrompeu dados. **Nunca** rodar `seed_salon.py` em prod sem backup.

---

## 9. Comandos prontos (copiar)

```powershell
# Cortar release vX.Y.Z (após bump + CHANGELOG mergeados em main)
git checkout main; git pull
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z" --notes-file release-notes.md

# Conferir tags
git tag -l
git ls-remote --tags origin

# Validar versão em produção
curl https://flowia-api.onrender.com/health
```
