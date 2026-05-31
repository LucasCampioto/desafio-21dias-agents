from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from agents.analyst import run_analyst
from config import verify_api_key
from db.mongo import get_collection
from schemas.evolution import EvolutionGenerateRequest, EvolutionGenerateResponse
from services.evolution_input import build_evolution_input

router = APIRouter(prefix="/evolution", tags=["evolution"])


@router.post("/generate", response_model=EvolutionGenerateResponse)
async def generate_evolution(body: EvolutionGenerateRequest, _: str = Depends(verify_api_key)):
    evolution_input = build_evolution_input(body.userId)
    if not evolution_input.get("campaigns"):
        raise HTTPException(
            status_code=404,
            detail="Nenhuma métrica de sessão encontrada para este usuário.",
        )

    try:
        report = run_analyst(evolution_input)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analista error: {exc}") from exc

    generated_at = datetime.now(timezone.utc)
    doc = {
        "userId": ObjectId(body.userId),
        "report": report.model_dump(),
        "generatedAt": generated_at,
    }
    get_collection("evolution_reports").update_one(
        {"userId": ObjectId(body.userId)},
        {"$set": doc},
        upsert=True,
    )

    return EvolutionGenerateResponse(
        userId=body.userId,
        report=report,
        generatedAt=generated_at.isoformat(),
    )
