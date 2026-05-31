import json
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId

from db.mongo import get_collection

DAYS_PATH = Path(__file__).resolve().parent.parent / "content" / "days.json"


def load_days_content() -> list[dict]:
    with open(DAYS_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_day_by_id(day_id: int) -> dict | None:
    for day in load_days_content():
        if day.get("id") == day_id:
            return day
    return None


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _start_of_calendar_day(dt: datetime) -> datetime:
    utc = _as_utc(dt)
    assert utc is not None
    return utc.replace(hour=0, minute=0, second=0, microsecond=0)


def _days_between_calendar(a: datetime, b: datetime) -> int:
    sa = _start_of_calendar_day(a)
    sb = _start_of_calendar_day(b)
    return max(0, int((sb - sa).total_seconds() // 86400))


def _fallback_current_day_id(user_id: str, session_id: str) -> int:
    progress = get_collection("session_progress").find_one(
        {"userId": ObjectId(user_id), "sessionId": ObjectId(session_id)},
        {"completedDays": 1},
    )
    completed = (progress or {}).get("completedDays") or []
    if not completed:
        return 1
    return min(max(completed) + 1, 21)


def _effective_day_index(session: dict | None, progress: dict | None, now: datetime | None = None) -> int:
    if session is None or progress is None:
        return 1
    if session.get("status") == "completed":
        return 22

    started = progress.get("startedAt")
    if isinstance(started, datetime):
        start_day = started
    else:
        start_day = datetime.now(timezone.utc)

    today = now or datetime.now(timezone.utc)
    elapsed = _days_between_calendar(start_day, today) + int(progress.get("simulatedDaysOffset") or 0)
    start_from = int(progress.get("startDay") or session.get("startDay") or 1)
    return start_from + elapsed


def _current_active_day(session: dict | None, progress: dict | None, now: datetime | None = None) -> int | None:
    if session is None or progress is None:
        return None
    if session.get("status") == "completed":
        return 21
    return min(max(1, _effective_day_index(session, progress, now)), 21)


def fetch_today_status(user_id: str, session_id: str) -> dict:
    """Progresso atual e dia desbloqueado — somente Mongo (sem rotas `/internal`)."""
    oid_user = ObjectId(user_id)
    oid_sess = ObjectId(session_id)

    sess = get_collection("sessions").find_one(
        {"_id": oid_sess, "userId": oid_user},
        {"status": 1, "startDay": 1},
    )
    progress = get_collection("session_progress").find_one({"sessionId": oid_sess})

    if not sess or not progress:
        return {
            "error": "sessão ou progresso não encontrado",
            "userId": user_id,
            "sessionId": session_id,
        }

    completed = progress.get("completedDays") or []
    current_day = _current_active_day(sess, progress)
    unlocked = sorted({*(completed or []), *( [current_day] if current_day else [])})

    return {
        "userId": user_id,
        "sessionId": session_id,
        "sessionStatus": sess.get("status"),
        "startDay": progress.get("startDay") or sess.get("startDay"),
        "completedDays": completed,
        "currentDayId": current_day,
        "completedCount": len(completed),
        "simulatedDaysOffset": progress.get("simulatedDaysOffset") or 0,
        "effectiveDayHint": _effective_day_index(sess, progress),
        "recentUnlockedDaysSample": unlocked[-8:] if unlocked else [],
    }


def fetch_today_lesson(user_id: str, session_id: str) -> dict:
    """Replica o fallback local do conteúdo do dia usando IDs derivados da sessão."""
    oid_user = ObjectId(user_id)
    oid_sess = ObjectId(session_id)

    sess = get_collection("sessions").find_one(
        {"_id": oid_sess, "userId": oid_user},
        {"status": 1, "startDay": 1},
    )
    progress = get_collection("session_progress").find_one({"sessionId": oid_sess})

    if not sess or not progress:
        return {"error": "sessão ou progresso ausente"}

    completed = progress.get("completedDays") or []
    current_day_id = _current_active_day(sess, progress) or _fallback_current_day_id(user_id, session_id)

    day = get_day_by_id(int(current_day_id))
    payload = {
        "dayId": int(current_day_id),
        "sessionStatus": sess.get("status"),
        "completedHighest": max(completed) if completed else None,
        "completedCount": len(completed),
        "progressDayHint": progress.get("startDay"),
    }

    if not day:
        return {**payload, "error": "Lesson not found"}

    merged = {
        **payload,
        "week": day.get("week"),
        "weekTitle": day.get("weekTitle"),
        "title": day.get("title"),
        "focus": day.get("focus"),
        "declaration": day.get("declaration"),
        "intro": day.get("intro"),
        "source": "local_days_json_via_mongo",
    }
    return merged


def fetch_day_answers(user_id: str, session_id: str, day_id: int) -> dict:
    oid_user = ObjectId(user_id)
    oid_sess = ObjectId(session_id)
    doc = get_collection("day_answers").find_one(
        {"userId": oid_user, "sessionId": oid_sess, "dayId": day_id},
        {"_id": 0, "answers": 1, "updatedAt": 1},
    )
    return {
        "dayId": day_id,
        "answers": (doc or {}).get("answers") or {},
        "updatedAt": (doc or {}).get("updatedAt"),
        "mongo": True,
    }


def fetch_mural_affirmations(user_id: str) -> dict:
    cards = []
    for doc in get_collection("mural_cards").find({"userId": ObjectId(user_id)}).limit(40):
        cards.append(
            {
                "id": str(doc.get("_id")),
                "text": doc.get("text", ""),
                "color": doc.get("color"),
            }
        )

    return {"userId": user_id, "count": len(cards), "cards": cards}
