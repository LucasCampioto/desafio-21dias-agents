import os
from functools import lru_cache

from dotenv import load_dotenv
from fastapi import Header, HTTPException

load_dotenv()


@lru_cache
def get_settings():
    settings = {
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "mongodb_uri": os.getenv("MONGODB_URI", "mongodb://localhost:27017/quantum-journal"),
        "backend_url": os.getenv("BACKEND_URL", "http://localhost:3000").rstrip("/"),
        "agents_api_key": os.getenv("AGENTS_API_KEY", ""),
        "aurora_model": os.getenv("AURORA_MODEL", "gpt-4o"),
        "analyst_model": os.getenv("ANALYST_MODEL", "gpt-4o"),
        "analyze_day_model": os.getenv("ANALYZE_DAY_MODEL", "gpt-4o-mini"),
    }

    if os.getenv("VERCEL"):
        if not settings["openai_api_key"]:
            print("WARNING: OPENAI_API_KEY is not set on Vercel — chat/evolution will fail")
        if not settings["agents_api_key"]:
            print("WARNING: AGENTS_API_KEY is not set on Vercel — API routes will reject requests")

    return settings


async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    settings = get_settings()
    if not settings["agents_api_key"] or x_api_key != settings["agents_api_key"]:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key
