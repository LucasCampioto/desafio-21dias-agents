"""Contexto legacy usado antes do pipeline dinâmico.

Preferir `services.aurora_context.build_aurora_context` + coberturas em chat.
Este módulo permanece apenas para chamadas pontuais/compatibilidade.
"""

from datetime import datetime, timezone

from bson import ObjectId

from db.mongo import get_collection
from tools.backend_tools import fetch_day_answers, fetch_today_lesson, fetch_today_status, get_day_by_id


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_context_pack(user_id: str, session_id: str | None) -> str:
    """Monta snapshot textual simples para instruções externas/debug."""
    if not session_id:
        return (
            f"Usuário: {user_id}\n"
            "Nenhuma jornada/campanha ativa no momento.\n"
            "Aurora pode conversar normalmente e, se fizer sentido, "
            "sugerir iniciar uma jornada em /jornada/iniciar."
        )

    status = fetch_today_status(user_id, session_id)
    lesson = fetch_today_lesson(user_id, session_id)
    day_id = lesson.get("dayId") or status.get("currentDayId") or 1

    answers = fetch_day_answers(user_id, session_id, int(day_id))
    day_meta = get_day_by_id(int(day_id)) or {}

    progress = get_collection("session_progress").find_one(
        {"userId": ObjectId(user_id), "sessionId": ObjectId(session_id)},
        {"_id": 0, "completedDays": 1, "startedAt": 1, "simulatedDaysOffset": 1},
    )

    lines = [
        f"Usuário: {user_id}",
        f"Sessão/campanha: {session_id}",
        f"Dia atual: {day_id}",
        f"Semana: {day_meta.get('weekTitle', lesson.get('weekTitle', ''))}",
        f"Título do dia: {day_meta.get('title', lesson.get('title', ''))}",
        f"Foco: {day_meta.get('focus', lesson.get('focus', ''))}",
        f"Status: {status}",
        f"Progresso: {progress or {}}",
        f"Respostas do dia: {answers}",
    ]
    return "\n".join(lines)
