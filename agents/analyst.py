import json

from agno.agent import Agent
from agno.models.openai import OpenAIChat

from config import get_settings
from schemas.evolution import EvolutionReport


def create_analyst_agent(evolution_input: dict) -> Agent:
    settings = get_settings()
    payload = json.dumps(evolution_input, ensure_ascii=False, indent=2)
    return Agent(
        name="Analista",
        model=OpenAIChat(id=settings["analyst_model"]),
        instructions=[
            "Você é o Analista de evolução emocional do Quantum Journal.",
            "Narre a evolução do usuário com base APENAS nos dados JSON fornecidos.",
            "Não invente métricas.",
            "negativePct e positivePct são PERCENTUAIS de 0 a 100 (média emocional da semana).",
            "destructiveAvg é MÉDIA de pensamentos destrutivos por dia (contagem, não percentual).",
            "Use % ao citar negatividade/positividade. Ex: '62% → 18%'.",
            "Use comparativos entre campanhas quando existirem.",
            "Responda SOMENTE com JSON válido no formato:",
            "{",
            '  "emotionalProgress": { "title": "...", "weeks": [{"week":1,"negativePct":62,"positivePct":15,"destructiveAvg":2,"label":"Semana 1"}], "narrative": "..." },',
            '  "patterns": { "title": "...", "items": ["..."] },',
            '  "crossCampaignInsights": [{ "title": "...", "metric": "62% → 18%", "narrative": "..." }],',
            '  "auroraMessage": "..."',
            "}",
            "Dados do usuário:",
            payload,
        ],
        markdown=False,
    )


def run_analyst(evolution_input: dict) -> EvolutionReport:
    agent = create_analyst_agent(evolution_input)
    response = agent.run(
        "Gere o relatório de evolução emocional completo em JSON.",
        session_id=f"analyst-{evolution_input.get('userId', 'unknown')}",
    )
    content = response.content if response.content else "{}"
    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    data = json.loads(content)
    return EvolutionReport.model_validate(data)
