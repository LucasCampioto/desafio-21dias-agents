import os
from functools import lru_cache

from dotenv import load_dotenv
from fastapi import Header, HTTPException

load_dotenv()

DEFAULT_MODEL = "gpt-4o-mini"
_MODEL_PLACEHOLDERS = frozenset(
    {
        "AURORA_MODEL",
        "ANALYST_MODEL",
        "ANALYZE_DAY_MODEL",
        "chatgpt",
    }
)


def _is_local_mongo(uri: str) -> bool:
    return "localhost" in uri or "127.0.0.1" in uri


def _resolve_model(env_name: str, default: str = DEFAULT_MODEL) -> str:
    """Lê o modelo da env; ignora valores vazios ou iguais ao nome da variável."""
    raw = (os.getenv(env_name) or "").strip().strip("\"'")
    if not raw or raw in _MODEL_PLACEHOLDERS or raw == env_name:
        return default
    return raw


@lru_cache
def get_settings():
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/quantum-journal")
    settings = {
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "mongodb_uri": mongodb_uri,
        "backend_url": os.getenv("BACKEND_URL", "http://localhost:3000").rstrip("/"),
        "agents_api_key": os.getenv("AGENTS_API_KEY", ""),
        # gpt-4o-mini é o padrão em produção: menos latência (evita 504 na Vercel).
        # Use AURORA_MODEL/ANALYST_MODEL=gpt-4o se quiser qualidade máxima.
        "aurora_model": _resolve_model("AURORA_MODEL"),
        "analyst_model": _resolve_model("ANALYST_MODEL"),
        "analyze_day_model": _resolve_model("ANALYZE_DAY_MODEL"),
    }

    if os.getenv("VERCEL"):
        if not settings["openai_api_key"]:
            print("WARNING: OPENAI_API_KEY is not set on Vercel — chat/evolution will fail")
        if not settings["agents_api_key"]:
            print("WARNING: AGENTS_API_KEY is not set on Vercel — API routes will reject requests")
        if not os.getenv("MONGODB_URI") or _is_local_mongo(settings["mongodb_uri"]):
            print(
                "ERROR: MONGODB_URI missing or pointing to localhost on Vercel. "
                "Set Atlas mongodb+srv://... in the Agents project Environment Variables."
            )

    return settings


def require_production_mongo():
    """Levanta erro explícito se Mongo estiver apontando para localhost em produção."""
    settings = get_settings()
    if os.getenv("VERCEL") and (
        not os.getenv("MONGODB_URI") or _is_local_mongo(settings["mongodb_uri"])
    ):
        raise RuntimeError(
            "MONGODB_URI inválida no Agents (Vercel). "
            "Configure a URI do MongoDB Atlas (mongodb+srv://...) nas Environment Variables "
            "do projeto desafio-21dias-agents e faça Redeploy."
        )


async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    settings = get_settings()
    if not settings["agents_api_key"] or x_api_key != settings["agents_api_key"]:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key
