import json
from datetime import datetime, timezone

from bson import ObjectId
from openai import OpenAI

from config import get_settings
from db.mongo import get_collection
from tools.backend_tools import get_day_by_id, load_days_content


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _extract_fields_for_day(day_id: int) -> list[dict]:
    day = get_day_by_id(day_id)
    if not day:
        return []
    fields = []
    for section in day.get("sections", []):
        for field in section.get("fields", []):
            fields.append(
                {
                    "id": field.get("id"),
                    "label": field.get("label"),
                    "kind": field.get("kind"),
                    "sectionTitle": section.get("title"),
                }
            )
    return fields


def _load_day_answers(user_id: str, session_id: str, day_id: int) -> dict:
    doc = get_collection("day_answers").find_one(
        {
            "userId": ObjectId(user_id),
            "sessionId": ObjectId(session_id),
            "dayId": day_id,
        },
        {"_id": 0, "answers": 1},
    )
    return (doc or {}).get("answers") or {}


DAY_SIGNALS_SCHEMA = {
    "type": "object",
    "properties": {
        "fieldSignals": {
            "type": "object",
            "properties": {
                "thoughts_recurring": {
                    "type": "object",
                    "properties": {
                        "destructiveCount": {"type": "integer"},
                        "themes": {"type": "array", "items": {"type": "string"}},
                        "tone": {"type": "string"},
                    },
                    "required": ["destructiveCount", "themes", "tone"],
                    "additionalProperties": False,
                },
                "emotions": {
                    "type": "object",
                    "properties": {
                        "dominant": {"type": "array", "items": {"type": "string"}},
                        "scores": {
                            "type": "object",
                            "properties": {
                                "negative": {"type": "number"},
                                "neutral": {"type": "number"},
                                "positive": {"type": "number"},
                            },
                            "required": ["negative", "neutral", "positive"],
                            "additionalProperties": False,
                        },
                    },
                    "required": ["dominant", "scores"],
                    "additionalProperties": False,
                },
            },
            "required": ["thoughts_recurring", "emotions"],
            "additionalProperties": False,
        }
    },
    "required": ["fieldSignals"],
    "additionalProperties": False,
}


def analyze_day(user_id: str, session_id: str, day_id: int) -> dict:
    """Extrai day_signals via OpenAI structured output e persiste no MongoDB."""
    settings = get_settings()
    answers = _load_day_answers(user_id, session_id, day_id)
    if not answers:
        raise ValueError(f"Sem respostas para dayId={day_id}")

    day = get_day_by_id(day_id)
    if not day:
        raise ValueError(f"Dia {day_id} não encontrado em content/days.json")

    field_map = _extract_fields_for_day(day_id)
    prompt = {
        "dayId": day_id,
        "week": day.get("week"),
        "title": day.get("title"),
        "fields": field_map,
        "answers": answers,
    }

    client = OpenAI(api_key=settings["openai_api_key"])
    response = client.responses.create(
        model=settings["analyze_day_model"],
        input=[
            {
                "role": "system",
                "content": (
                    "Você analisa respostas de journaling emocional. "
                    "Extraia sinais objetivos: contagem de pensamentos destrutivos, "
                    "temas recorrentes, tom geral, emoções dominantes e scores "
                    "normalizados (negative/neutral/positive somando ~1.0)."
                ),
            },
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "day_signals",
                "schema": DAY_SIGNALS_SCHEMA,
                "strict": True,
            }
        },
    )

    output_text = response.output_text
    parsed = json.loads(output_text)
    analyzed_at = _utc_now()

    doc = {
        "userId": ObjectId(user_id),
        "sessionId": ObjectId(session_id),
        "dayId": day_id,
        "week": day.get("week"),
        "fieldSignals": parsed["fieldSignals"],
        "analyzedAt": analyzed_at,
    }

    get_collection("day_signals").update_one(
        {"sessionId": ObjectId(session_id), "dayId": day_id},
        {"$set": doc},
        upsert=True,
    )

    return {
        "ok": True,
        "dayId": day_id,
        "sessionId": session_id,
        "analyzedAt": analyzed_at.isoformat(),
    }


def list_all_days() -> list[dict]:
    return load_days_content()
