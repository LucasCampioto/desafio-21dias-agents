from typing import Any

from pydantic import BaseModel, Field


class EvolutionGenerateRequest(BaseModel):
    userId: str = Field(..., description="ID do usuário")


class EmotionalProgressWeek(BaseModel):
    week: int
    negativePct: float | None = None
    positivePct: float | None = None
    negative: float | None = None
    positive: float | None = None
    destructiveAvg: float | None = None
    label: str | None = None


class EmotionalProgress(BaseModel):
    title: str
    weeks: list[EmotionalProgressWeek]
    narrative: str


class Patterns(BaseModel):
    title: str
    items: list[str]


class CrossCampaignInsight(BaseModel):
    title: str
    metric: str
    narrative: str


class EvolutionReport(BaseModel):
    emotionalProgress: EmotionalProgress
    patterns: Patterns
    crossCampaignInsights: list[CrossCampaignInsight]
    auroraMessage: str


class EvolutionGenerateResponse(BaseModel):
    userId: str
    report: EvolutionReport
    generatedAt: str


class AnalyzeDayRequest(BaseModel):
    userId: str
    sessionId: str
    dayId: int = Field(..., ge=1, le=21)


class AnalyzeDayResponse(BaseModel):
    ok: bool
    dayId: int
    sessionId: str
    analyzedAt: str | None = None
    detail: str | None = None
