# Deploy na Vercel — Agents (FastAPI)

## Por que dava erro `api/index.py doesn't match`

O bloco `functions` no `vercel.json` só vale para **funções legadas** em `api/*.js` (ou handlers Python antigos).

O Quantum Journal usa o **preset FastAPI** da Vercel: um único app em `main.py` com `app = FastAPI()`.  
**Não use `vercel.json` com `functions`** — isso gera [Unmatched function pattern](https://vercel.com/docs/errors/error-list#unmatched-function-pattern).

## Por que dava `FUNCTION_INVOCATION_FAILED` no cold start

`main.py` importava `routes` (e `agno`) no topo do módulo. Qualquer falha de dependência ou env na importação derrubava **todas** as rotas, inclusive `/health`.

Agora `/health` é registrado sem imports pesados; routers são montados no `lifespan` com try/except — se `agno` falhar, `/health` ainda responde.

## Configuração do projeto na Vercel

| Campo | Valor |
|-------|--------|
| Repositório | `desafio-21dias-agents` (raiz do repo) |
| Root Directory | *(vazio)* |
| Framework Preset | **FastAPI** (deixe a Vercel detectar) |
| Build Command | *(vazio)* |
| Output Directory | *(vazio)* |
| Install Command | `pip install -r requirements.txt` *(se precisar)* |

## Variáveis de ambiente (Production)

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `OPENAI_API_KEY` | Sim (chat/IA) | Chave OpenAI |
| `MONGODB_URI` | Sim | URI Atlas (`mongodb+srv://...`) |
| `AGENTS_API_KEY` | Sim | Mesma chave do backend (`X-API-Key`) |
| `BACKEND_URL` | Sim | URL do backend (ex.: `https://seu-backend.vercel.app`) |
| `AURORA_MODEL` | Não | Padrão `gpt-4o` |
| `ANALYST_MODEL` | Não | Padrão `gpt-4o` |
| `ANALYZE_DAY_MODEL` | Não | Padrão `gpt-4o-mini` |

Ver também `../vercel-env.template.md`.

### MongoDB Atlas

Em **Network Access**, permita `0.0.0.0/0` para conexões serverless.

## Duração máxima (chat / IA)

Chat e evolução fazem cold start + Mongo + OpenAI. O fluxo é:

`Frontend → Backend (Node) → Agents (Python) → OpenAI`

Se o **backend** ou o **agents** cortar antes, o browser vê **504**.

O repo inclui `vercel.json` com:

```json
{ "functions": { "main.py": { "maxDuration": 60 } } }
```

(chave = entrypoint FastAPI `main.py`, não `api/index.py`)

No **backend**, `api/index.js` também precisa de `maxDuration` ≥ 60s (já configurado).

Alternativa no painel: **Project → Settings → Functions → Function Max Duration** → `60` ou `300`.

Para respostas mais rápidas, nas envs do agents:

```
AURORA_MODEL=gpt-4o-mini
ANALYST_MODEL=gpt-4o-mini
```

## Arquivos necessários no repo

- `main.py` — exporta `app`
- `pyproject.toml` — **obrigatório** com `dependencies = [...]` (FastAPI, etc.) e `[tool.vercel] entrypoint = "main:app"`
- `requirements.txt` — espelho das deps (útil localmente; a Vercel prioriza `pyproject.toml`)
- `runtime.txt` — `python-3.11` *(opcional; remova se a Vercel ignorar)*
- `index.py` — fallback que reexporta `main:app` se o preset não achar `main.py`

**Não** é necessária pasta `api/` para deploy.

### Erro `No module named 'fastapi'`

O preset FastAPI da Vercel instala deps a partir do `pyproject.toml`. Se o arquivo existe **sem** a lista `dependencies`, o `fastapi` não é instalado e a função crasha no import de `main.py`.

Solução: garanta `dependencies = ["fastapi>=...", ...]` em `pyproject.toml`, commit, push e **Redeploy**.

## Teste após deploy

1. **Primeiro:** `https://SEU-PROJETO.vercel.app/health`

```json
{"status":"ok","service":"quantum-journal-agents"}
```

2. **Debug (opcional):** `GET /health/deep` — reporta se `agno` e os routers carregaram.

3. Depois teste rotas autenticadas com header `X-API-Key`.

## Se a Vercel ainda usar preset "Other"

1. Settings → General → Framework Preset → **FastAPI**
2. Remova Build Command customizado
3. Redeploy
