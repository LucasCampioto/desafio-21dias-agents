# Quantum Journal — Agents (FastAPI + Agno)

Serviço Python de agentes IA para o Quantum Journal: **Aurora** (chat), **AnalyzeDay** (métricas por dia) e **Analista** (relatório de evolução).

## Pré-requisitos

- Python 3.11+
- MongoDB rodando (mesmo banco do backend Node)
- Chave OpenAI (`OPENAI_API_KEY`)
- Backend Node em `:3000` (opcional; as tools do chat já leem **Mongo direto**, pois não há `GET /internal/users/*` compatível neste projeto)

## Setup — Windows (PowerShell)

```powershell
cd desafio-21dias-agents
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# Edite .env: OPENAI_API_KEY, AGENTS_API_KEY, MONGODB_URI
uvicorn main:app --reload --port 8000
```

## Setup — Mac / Linux

```bash
cd desafio-21dias-agents
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edite .env: OPENAI_API_KEY, AGENTS_API_KEY, MONGODB_URI
uvicorn main:app --reload --port 8000
```

Docs interativas: [http://localhost:8000/docs](http://localhost:8000/docs)

## Deploy na Vercel

Configuração pronta: `vercel.json` (usa `main.py` na raiz) e `runtime.txt`.

**Importante:** conecte o projeto Vercel ao repo **`desafio-21dias-agents`** (raiz do repo). Root Directory só é necessário se tudo estiver em um monorepo único.

Guia completo (3 projetos + envs): [`../DEPLOY-VERCEL.md`](../DEPLOY-VERCEL.md)

## Variáveis de ambiente

| Variável | Descrição |
|----------|-----------|
| `OPENAI_API_KEY` | Chave da OpenAI |
| `MONGODB_URI` | URI do MongoDB (ex.: `mongodb://localhost:27017/quantum-journal`) |
| `BACKEND_URL` | URL do backend Node (padrão `http://localhost:3000`) |
| `AGENTS_API_KEY` | Chave compartilhada com o backend (header `X-API-Key`) |
| `AURORA_MODEL` | Modelo Aurora (padrão `gpt-4o`) |
| `ANALYST_MODEL` | Modelo Analista (padrão `gpt-4o`) |
| `ANALYZE_DAY_MODEL` | Modelo AnalyzeDay (padrão `gpt-4o-mini`) |

## Rotas

Todas as rotas POST exigem header `X-API-Key` (mesmo valor de `AGENTS_API_KEY`).

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Health check |
| POST | `/chat` | Chat com Aurora |
| POST | `/internal/analyze-day` | Pipeline AnalyzeDay → grava `day_signals` |
| POST | `/evolution/generate` | Gera relatório do Analista → cache em `evolution_reports` |

### Exemplos

```bash
# Chat Aurora
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me-shared-with-backend" \
  -d '{"userId":"USER_ID","sessionId":"SESSION_ID","message":"Como estou hoje?"}'

# AnalyzeDay (chamado pelo backend ao completar dia)
curl -X POST http://localhost:8000/internal/analyze-day \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me-shared-with-backend" \
  -d '{"userId":"USER_ID","sessionId":"SESSION_ID","dayId":1}'

# Relatório de evolução
curl -X POST http://localhost:8000/evolution/generate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me-shared-with-backend" \
  -d '{"userId":"USER_ID"}'
```

## Estrutura

```
desafio-21dias-agents/
├── main.py                 # FastAPI app
├── config.py               # env vars + verify_api_key
├── db/mongo.py             # helpers MongoDB
├── agents/                 # Aurora + Analista (Agno)
├── tools/backend_tools.py  # HTTP → backend Node
├── services/               # context_pack, analyze_day, evolution_input
├── schemas/                # Pydantic request/response
├── routes/                 # chat, evolution, internal
└── content/days.json       # 21 dias da jornada
```

## Integração com backend

O backend Node faz proxy para este serviço usando `AGENTS_URL=http://localhost:8000` e o mesmo `AGENTS_API_KEY`. Ao completar um dia, o backend chama `POST /internal/analyze-day` e agrega `session_metrics` deterministicamente.
