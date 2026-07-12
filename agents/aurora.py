from __future__ import annotations

from openai import OpenAI

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


def build_aurora_system_prompt(
    context: str,
    *,
    readiness: str,
    question_domain: str,
) -> str:
    calibrated = (
        "### Calibragem atual\n"
        f"- readiness declarado pela engine: `{readiness}`\n"
        f"- domínio temático atual da mensagem (roteador): `{question_domain}`\n"
        "- Modulação esperada pelo produto:\n"
        f"  {_READINESS_VOICE.get(readiness, _READINESS_VOICE['cautious'])}\n"
    )

    return "\n".join(
        [
            "Você é Aurora, assistente reflexiva dentro do Quantum Journal.",
            calibrated,
            "Regras inegociáveis:",
            "1. Você só fala sobre o que estiver textualmente disponível no contexto abaixo.",
            "2. Nunca traga checklist genéricos de internet, recomendações de terapia/médico implícitas "
            'nem listas encyclopédicas — inclusive evite "você deve/tenha/compra X".',
            "3. Se faltar evidência suficiente, diga com transparência o que falta e convide para registrar nos exercícios.",
            "4. Ao conectar perguntas (ex.: sonhos materiais ou decisões cotidianas), amarre apenas aos registros já citados",
            '   usando linguagem delicada tipo "nos exercícios você descreveu...".',
            "5. Responda em português do Brasil, segunda pessoa, com respeito natural.",
            "6. Respostas curtas e humanas (ideal: 2–4 parágrafos curtos).",
            "### Contexto fornecido (fonte autoritativa desta conversa):\n",
            context,
        ]
    )


def run_aurora_chat(
    message: str,
    context: str,
    *,
    readiness: str,
    question_domain: str,
) -> str:
    """Uma única chamada OpenAI — sem Agno, sem tools, sem histórico pesado."""
    settings = get_settings()
    if not settings["openai_api_key"]:
        raise RuntimeError("OPENAI_API_KEY não configurada no serviço de agents")

    client = OpenAI(api_key=settings["openai_api_key"])

    completion = client.chat.completions.create(
        model=settings["aurora_model"],
        messages=[
            {
                "role": "system",
                "content": build_aurora_system_prompt(
                    context,
                    readiness=readiness,
                    question_domain=question_domain,
                ),
            },
            {"role": "user", "content": message},
        ],
        max_tokens=700,
        temperature=0.7,
    )

    content = completion.choices[0].message.content if completion.choices else None
    return content or "Desculpe, não consegui formular uma resposta agora."
