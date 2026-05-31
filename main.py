from fastapi import FastAPI

from routes import chat, evolution, internal

app = FastAPI(title="Quantum Journal Agents", version="0.1.0")

app.include_router(chat.router)
app.include_router(evolution.router)
app.include_router(internal.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "quantum-journal-agents"}
