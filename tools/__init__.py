from agno.tools import tool

from tools.backend_tools import (
    fetch_day_answers,
    fetch_mural_affirmations,
    fetch_today_lesson,
    fetch_today_status,
)


def create_aurora_tools(user_id: str, session_id: str | None) -> list:
    """Cria tools Agno — leem Mongo/`days.json`, sem `/internal/users` no Node."""

    @tool
    def get_today_status() -> str:
        """Retorna o status do dia atual (progresso sintético) lido direto no Mongo."""
        if not session_id:
            return "Nenhuma jornada ativa. O usuário ainda não iniciou uma campanha."
        data = fetch_today_status(user_id, session_id)
        return str(data)

    @tool
    def get_today_lesson() -> str:
        """Retorna título/foco/intros do dia usando o dia atual calculado + days.json."""
        if not session_id:
            return "Nenhuma jornada ativa — não há lição do dia disponível."
        data = fetch_today_lesson(user_id, session_id)
        return str(data)

    @tool
    def get_day_answers(day_id: int) -> str:
        """Respostas do usuário num dia específico (coleção day_answers)."""
        if not session_id:
            return "Nenhuma jornada ativa — não há respostas salvas."
        data = fetch_day_answers(user_id, session_id, day_id)
        return str(data)

    @tool
    def get_mural_affirmations() -> str:
        """Cards do mural vindos direto da coleção mural_cards."""
        data = fetch_mural_affirmations(user_id)
        return str(data)

    return [get_today_status, get_today_lesson, get_day_answers, get_mural_affirmations]
