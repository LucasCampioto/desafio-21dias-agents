"""Vercel entrypoint fallback — re-exports the FastAPI app from main."""
from main import app

__all__ = ["app"]
