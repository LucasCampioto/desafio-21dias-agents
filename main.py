import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from routes import chat, evolution, internal

        app.include_router(chat.router)
        app.include_router(evolution.router)
        app.include_router(internal.router)
        app.state.routes_loaded = True
        app.state.routes_error = None
        logger.info("Agent routes loaded")
    except Exception as exc:
        app.state.routes_loaded = False
        app.state.routes_error = str(exc)
        logger.exception("Failed to load agent routes: %s", exc)
    yield


app = FastAPI(title="Quantum Journal Agents", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "quantum-journal-agents"}


@app.get("/health/deep")
async def health_deep():
    result = {"status": "ok", "routes_loaded": getattr(app.state, "routes_loaded", None)}

    if getattr(app.state, "routes_error", None):
        result["routes_error"] = app.state.routes_error

    try:
        import openai

        result["openai"] = "ok"
        result["openai_version"] = getattr(openai, "__version__", "unknown")
    except Exception as exc:
        result["status"] = "degraded"
        result["openai"] = "error"
        result["openai_error"] = str(exc)

    return result
