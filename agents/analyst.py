import json

from openai import OpenAI

from config import get_settings
from schemas.evolution import EvolutionReport


def run_analyst(evolution_input: dict) -> EvolutionReport:
    """Relatório via OpenAI direto (JSON) — sem Agno."""
    settings = get_settings()
    if not settings["openai_api_key"]:
        raise RuntimeError("OPENAI_API_KEY não configurada no serviço de agents")

    client = OpenAI(api_key=settings["openai_api_key"])
    payload = json.dumps(evolution_input, ensure_ascii=False, default=str)

    # Payload enxuto: evita estouro de tokens e latência
    if len(payload) > 12000:
        payload = payload[:11999] + "…"

    completion = client.chat.completions.create(
        model=settings["analyst_model"],
        messages=[
            {
                "role": "system",
                "content": (
                    "Você é o Analista de evolução emocional do Quantum Journal. "
                    "Narre a evolução do usuário com base APENAS nos dados JSON fornecidos. "
                    "Não invente métricas. "
                    "negativePct e positivePct são PERCENTUAIS de 0 a 100. "
                    "destructiveAvg é MÉDIA de pensamentos destrutivos por dia. "
                    "Use % ao citar negatividade/positividade. "
                    "Responda SOMENTE com JSON válido no formato: "
                    "{"
                    '"emotionalProgress": {"title":"...","weeks":[{"week":1,"negativePct":62,"positivePct":15,"destructiveAvg":2,"label":"Semana 1"}],"narrative":"..."}, '
                    '"patterns": {"title":"...","items":["..."]}, '
                    '"crossCampaignInsights": [{"title":"...","metric":"62% → 18%","narrative":"..."}], '
                    '"auroraMessage": "..."'
                    "}"
                ),
            },
            {
                "role": "user",
                "content": f"Gere o relatório de evolução emocional completo.\n\nDados:\n{payload}",
            },
        ],
        response_format={"type": "json_object"},
        max_tokens=1200,
        temperature=0.4,
    )

    content = completion.choices[0].message.content if completion.choices else "{}"
    data = json.loads(content or "{}")
    return EvolutionReport.model_validate(data)
