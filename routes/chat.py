import logging
import time

from fastapi import APIRouter, Depends, HTTPException

from agents.aurora import create_aurora_agent
from config import verify_api_key
from schemas.chat import ChatRequest, ChatResponse
from services.aurora_context import build_aurora_context
from services.guardrail import GUARDRAIL_COVERAGE_THRESHOLD, evaluate_guardrail
from services.journey_coverage import build_journey_coverage
from services.topic_router import classify_topic
from tools import create_aurora_tools

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

CHAT_CONTEXT_TTL_SECONDS = 24 * 60 * 60


def aurora_session_id(user_id: str, session_key: str) -> str:
    """Bucket de 24h — contexto da Aurora reinicia a cada período."""
    bucket = int(time.time() // CHAT_CONTEXT_TTL_SECONDS)
    return f"aurora-{user_id}-{session_key}-{bucket}"


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, _: str = Depends(verify_api_key)):
    topic = classify_topic(body.message)
    coverage = build_journey_coverage(body.userId, body.sessionId)
    guardrail = evaluate_guardrail(topic, body.sessionId, coverage)

    logger.info(
        "chat.pipeline topic=%s blocked=%s readiness=%s primary=%s thresh=%s",
        topic,
        guardrail.blocked,
        coverage.readiness,
        coverage.primary_domain,
        GUARDRAIL_COVERAGE_THRESHOLD,
    )

    if guardrail.blocked:
        reply = guardrail.reply or "Estou aqui com você — podemos tentar mais tarde assim que houver registros suficientes."
        return ChatResponse(reply=reply)

    context_text = build_aurora_context(body.userId, body.sessionId, topic, coverage)
    logger.debug("chat.aurora_context chars=%s topic=%s", len(context_text), topic)

    tools = create_aurora_tools(body.userId, body.sessionId)
    agent = create_aurora_agent(
        tools,
        context_text,
        readiness=coverage.readiness,
        question_domain=topic,
    )

    session_key = body.sessionId or "no-session"
    try:
        response = agent.run(
            body.message,
            session_id=aurora_session_id(body.userId, session_key),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Aurora error: {exc}") from exc

    reply = response.content or "Desculpe, não consegui formular uma resposta agora."
    return ChatResponse(reply=reply)
