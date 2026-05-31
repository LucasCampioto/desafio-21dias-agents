from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    userId: str = Field(..., description="ID do usuário")
    sessionId: str | None = Field(None, description="ID da campanha/sessão ativa (opcional)")
    message: str = Field(..., min_length=1, description="Mensagem do usuário")


class ChatResponse(BaseModel):
    reply: str
