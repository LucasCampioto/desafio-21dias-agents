import logging

from fastapi import APIRouter, Depends, HTTPException

from agents.aurora import run_aurora_chat
from config import verify_api_key
from schemas.chat import ChatRequest, ChatResponse
from services.aurora_context import build_aurora_context
from services.guardrail import GUARDRAIL_COVERAGE_THRESHOLD, evaluate_guardrail
from services.journey_coverage import build_journey_coverage
from services.topic_router import classify_topic

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


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
    logger.info("chat.aurora_context chars=%s topic=%s", len(context_text), topic)

    try:
        reply = run_aurora_chat(
            body.message,
            context_text,
            readiness=coverage.readiness,
            question_domain=topic,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Aurora error: {exc}") from exc

    return ChatResponse(reply=reply)
