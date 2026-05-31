# Deploy na Vercel — Agents (FastAPI)

## Por que dava erro `api/index.py doesn't match`

O bloco `functions` no `vercel.json` só vale para **funções legadas** em `api/*.js` (ou handlers Python antigos).

O Quantum Journal usa o **preset FastAPI** da Vercel: um único app em `main.py` com `app = FastAPI()`.  
**Não use `vercel.json` com `functions`** — isso gera [Unmatched function pattern](https://vercel.com/docs/errors/error-list#unmatched-function-pattern).

## Configuração do projeto na Vercel

| Campo | Valor |
|-------|--------|
| Repositório | `desafio-21dias-agents` (raiz do repo) |
| Root Directory | *(vazio)* |
| Framework Preset | **FastAPI** (deixe a Vercel detectar) |
| Build Command | *(vazio)* |
| Output Directory | *(vazio)* |
| Install Command | `pip install -r requirements.txt` *(se precisar)* |

## Variáveis de ambiente

Ver `../vercel-env.template.md` (seção Agents).

## Duração máxima (chat / IA)

Não configure `maxDuration` em `vercel.json` para este preset.

Use o painel: **Project → Settings → Functions → Function Max Duration** → `60` ou `300` segundos.

## Arquivos necessários no repo

- `main.py` — exporta `app`
- `requirements.txt`
- `pyproject.toml` — `[tool.vercel] entrypoint = "main:app"`
- `runtime.txt` — `python-3.12` *(opcional)*

**Não** é necessária pasta `api/` para deploy.

## Teste após deploy

`https://SEU-PROJETO.vercel.app/health`

```json
{"status":"ok","service":"quantum-journal-agents"}
```

## Se a Vercel ainda usar preset "Other"

1. Settings → General → Framework Preset → **FastAPI**
2. Remova Build Command customizado
3. Redeploy
