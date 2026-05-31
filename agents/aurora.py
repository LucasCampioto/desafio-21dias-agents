from __future__ import annotations

from agno.agent import Agent
from agno.models.openai import OpenAIChat

from config import get_settings


_READINESS_VOICE = {
    "ready": (
        "A usuária parece estar em momento de maior estabilidade emocional. "
        "Pode propor micro-passos gentis quando forem coerentes com o que ela já escreveu, "
        "sempre em tom convite (nunca ordem)."
    ),
    "cautious": (
        "Combine validação sincera + perguntas reflexivas bem pequenas. "
        "Destaque apenas passos triviais quando forem ancorados no texto dela."
    ),
    "not_ready": (
        "Prioridade absoluta é acolhimento. Não pressione decisões, compras nem mudanças profundas. "
        "Mantenha a presença, sem agendas escondidas."
    ),
}


def create_aurora_agent(
    tools: list,
    context: str,
    *,
    readiness: str,
    question_domain: str,
) -> Agent:
    settings = get_settings()

    calibrated = (
        "### Calibragem atual\n"
        f"- readiness declarado pela engine: `{readiness}`\n"
        f"- domínio temático atual da mensagem (roteador): `{question_domain}`\n"
        "- Modulação esperada pelo produto:\n"
        f"  {_READINESS_VOICE.get(readiness, _READINESS_VOICE['cautious'])}\n"
    )

    return Agent(
        name="Aurora",
        model=OpenAIChat(id=settings["aurora_model"]),
        instructions=[
            "Você é Aurora, assistente reflexiva dentro do Quantum Journal.",
            calibrated,
            "Regras inegociáveis:",
            "1. Você só fala sobre o que estiver textualmente disponível nos blocos de contexto/tooling.",
            "2. Nunca traga checklist genéricos de internet, recomendações de terapia/médico implícitas "
            'nem listas encyclopédicas — inclusive evite "você deve/tenha/compra X".',
            "3. Se faltar evidência suficiente, diga com transparência o que falta e convide para registrar nos exercícios.",
            "4. Ao conectar perguntas (ex.: sonhos materiais ou decisões cotidianas), amarre apenas aos registros já citados",
            '   (patterns financeiros listados etc.) usando linguagem delicada tipo "nos exercícios você descreveu...".',
            "5. Responda em português do Brasil, segundo pessoa verbal, plural de respeito natural para a usuária.",
            "### Contexto fornecido (fonte autoritativa desta conversa):\n",
            context,
            "\n(use tools apenas se algo objetivo ficou em aberto dentro do esperado pela jornada)",
        ],
        tools=tools,
        markdown=True,
        add_history_to_context=True,
    )
