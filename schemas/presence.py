from pydantic import BaseModel, Field


class PresenceCandidateSource(BaseModel):
    type: str
    dayId: int | None = None
    fieldId: str | None = None
    field: str | None = None
    cardId: str | None = None


class PresenceCandidate(BaseModel):
    candidateId: str
    period: str
    quote: str
    label: str | None = None
    source: PresenceCandidateSource | dict


class PresenceGenerateRequest(BaseModel):
    userId: str
    dateKey: str
    sessionId: str | None = None
    hasJourney: bool = True
    candidates: list[PresenceCandidate] = Field(default_factory=list)


class PresenceSlotSource(BaseModel):
    type: str
    dayId: int | None = None
    fieldId: str | None = None
    field: str | None = None
    cardId: str | None = None


class PresenceSlot(BaseModel):
    period: str
    title: str
    body: str
    quote: str
    source: PresenceSlotSource | dict


class PresenceGenerateResponse(BaseModel):
    slots: list[PresenceSlot]
