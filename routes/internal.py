from fastapi import APIRouter, Depends, HTTPException

from config import verify_api_key
from schemas.evolution import AnalyzeDayRequest, AnalyzeDayResponse
from schemas.presence import PresenceGenerateRequest, PresenceGenerateResponse
from services.analyze_day import analyze_day
from services.presence_generate import generate_presence_messages

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/analyze-day", response_model=AnalyzeDayResponse)
async def analyze_day_route(body: AnalyzeDayRequest, _: str = Depends(verify_api_key)):
    try:
        result = analyze_day(body.userId, body.sessionId, body.dayId)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AnalyzeDay error: {exc}") from exc

    return AnalyzeDayResponse(**result)


@router.post("/presence/generate", response_model=PresenceGenerateResponse)
async def presence_generate_route(body: PresenceGenerateRequest, _: str = Depends(verify_api_key)):
    try:
        return generate_presence_messages(body)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Presence generate error: {exc}") from exc
