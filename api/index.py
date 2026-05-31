"""
Entrada Vercel — a variável `app` precisa existir neste arquivo.
Rotas do FastAPI continuam em main.py (chat, evolution, internal).
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from main import app  # noqa: E402

__all__ = ["app"]
