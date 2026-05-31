import json

from openai import OpenAI

from config import get_settings
from schemas.presence import PresenceGenerateRequest, PresenceGenerateResponse

PRESENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "slots": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "period": {"type": "string", "enum": ["morning", "afternoon", "evening"]},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "quote": {"type": "string"},
                    "source": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "dayId": {"type": ["integer", "null"]},
                            "fieldId": {"type": ["string", "null"]},
                            "field": {"type": ["string", "null"]},
                            "cardId": {"type": ["string", "null"]},
                        },
                        "required": ["type"],
                        "additionalProperties": True,
                    },
                },
                "required": ["period", "title", "body", "quote", "source"],
                "additionalProperties": False,
            },
            "minItems": 3,
            "maxItems": 3,
        }
    },
    "required": ["slots"],
    "additionalProperties": False,
}


def generate_presence_messages(body: PresenceGenerateRequest) -> PresenceGenerateResponse:
    settings = get_settings()
    payload = body.model_dump()

    client = OpenAI(api_key=settings["openai_api_key"])
    response = client.responses.create(
        model=settings["analyze_day_model"],
        input=[
            {
                "role": "system",
                "content": (
                    "Você escreve lembretes breves e acolhedores para o mural do Quantum Journal. "
                    "Gere exatamente 3 slots: morning, afternoon, evening. "
                    "Cada slot DEVE usar quote copiada VERBATIM de um candidato do pack. "
                    "title <= 40 caracteres, body <= 280 caracteres. "
                    "Tom positivo, reflexivo, nunca prescritivo. "
                    "Não invente fatos, métricas ou frases fora do pack. "
                    "Cada período deve soar diferente (estrutura e foco distintos). "
                    "source deve corresponder ao candidato escolhido."
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "presence_reminders",
                "schema": PRESENCE_SCHEMA,
                "strict": True,
            }
        },
    )

    parsed = json.loads(response.output_text)
    return PresenceGenerateResponse.model_validate(parsed)
