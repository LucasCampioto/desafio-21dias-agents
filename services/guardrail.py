"""Guardrail temático pré-LLM: bloqueia conselho genérico quando o tema não está na jornada."""

from __future__ import annotations

from dataclasses import dataclass

from services.journey_coverage import JourneyCoverage

# Alinhado ao plano: abaixo disso consideramos tema **não coberto** pela jornada atual.
COVERAGE_THRESHOLD = 0.25
GUARDRAIL_COVERAGE_THRESHOLD = COVERAGE_THRESHOLD

_DOMAIN_LABEL_PT: dict[str, str] = {
    "finance": "finanças e decisões com o dinheiro",
    "relationships": "vínculos, família e relacionamentos",
    "self_worth": "autoestima e identidade",
    "behavior": "hábitos, decisões do dia a dia e compromissos",
    "journey_meta": "acompanhar sua evolução na campanha",
    "general": "reflexões gerais do que você já registrou",
}


def _no_journal_entries_reply() -> str:
    return (
        "Ainda não encontrei respostas suas salvas nesta campanha — então ficaria respondendo só com clichês externos.\n\n"
        "Se fizer sentido, registra o primeiro exercício disponível ou deixa algo no mural. "
        "Quando esse material existir, consigo ficar bem perto do seu texto.\n\n"
        "Se precisa recomeçar: /jornada/iniciar"
    )


@dataclass
class GuardrailResult:
    blocked: bool
    reply: str | None


def primary_journey_focus_label(primary: str) -> str:
    return _DOMAIN_LABEL_PT.get(primary, "o foco registrado nos seus exercícios")


def _no_session_reply() -> str:
    return (
        "Eu quero te acompanhar de um jeito que faça sentido — mas ainda não tenho uma jornada ativa "
        "sua para me ancorar.\n\n"
        "Quando você iniciar em /jornada/iniciar e for registrando os dias, consigo refletir com você "
        "a partir do que você mesma escreveu."
    )


def _invalid_session_reply() -> str:
    return (
        "Não encontrei esta campanha vinculada ao seu usuário. "
        "Confira se o app está na jornada certa ou inicie novamente em /jornada/iniciar.\n\n"
        "Assim eu consigo usar seus exercícios como base, sem chute."
    )


def _uncovered_reply(question_domain: str, coverage: JourneyCoverage) -> str:
    tema = _DOMAIN_LABEL_PT.get(question_domain, "esse tema específico")
    foco = primary_journey_focus_label(coverage.primary_domain)
    return (
        f"Sinto o peso por trás do que você trouxe sobre {tema} — obrigada por confiar aqui.\n\n"
        f"Pelo que você registrou nesta campanha, o centro tem sido mais sobre {foco}. "
        f"Ainda não tenho bastante material seus sobre {tema} para responder com segurança, "
        "e prefiro não te dar um conselho genérico de internet.\n\n"
        "O que pode ajudar agora:\n"
        "• Voltar aos exercícios do dia atual e registrar o que já está aparecendo para você;\n"
        "• Ou, quando existir uma campanha com esse foco no app, iniciar uma nova jornada alinhada a isso;\n"
        "• Ou anotar no mural uma frase sobre isso — quando esse tema fizer parte da sua jornada aqui, "
        "acompanho com base no seu texto.\n\n"
        "Posso sempre conversar sobre o que você já escreveu na campanha atual, se quiser."
    )


def evaluate_guardrail(
    question_domain: str,
    session_id: str | None,
    coverage: JourneyCoverage | None,
) -> GuardrailResult:
    """
    Se `blocked`, retorne resposta curta determinística (sem Aurora).
    Domínio `general` não dispara guardrail por cobertura (usa o que já existe na jornada).
    """
    if not session_id or not session_id.strip():
        return GuardrailResult(True, _no_session_reply())

    if coverage is None:
        return GuardrailResult(True, _invalid_session_reply())

    if getattr(coverage, "session_missing", False):
        return GuardrailResult(True, _no_session_reply())

    # Sessão informada pelo cliente mas não pertence ao usuário / não existe no Mongo.
    if not getattr(coverage, "session_exists", True):
        return GuardrailResult(True, _invalid_session_reply())

    # Campanha referenciada, porém não há respostas persistidas nos exercícios.
    if not getattr(coverage, "has_registered_journey_content", True):
        return GuardrailResult(True, _no_journal_entries_reply())

    if question_domain in ("general", "behavior"):
        # Decisões cotidianas e hábitos: libera se há qualquer registro na jornada.
        if getattr(coverage, "has_registered_journey_content", False) or question_domain == "general":
            return GuardrailResult(False, None)

    dc = coverage.domains.get(question_domain) or {}
    score = float(dc.get("score") or 0)

    # Evolução/meta: se há exercícios registrados, libera conversa mesmo sem session_metrics.
    if question_domain == "journey_meta":
        if getattr(coverage, "has_registered_journey_content", False) or score >= COVERAGE_THRESHOLD:
            return GuardrailResult(False, None)
        return GuardrailResult(
            True,
            (
                "Ainda não consigo montar uma leitura fiel da sua evolução — falta bastante histórico "
                "concluído ou as métricas ainda não estão suficientemente preenchidas.\n\n"
                "Complete mais exercícios e abra a seção de evolução no app quando ela aparecer; "
                "assim uso o que você já registrou, não um resumo genérico.\n\n"
                "Se quiser, podemos só refletir juntas sobre o último texto que você escreveu no dia atual."
            ),
        )

    if score < COVERAGE_THRESHOLD:
        return GuardrailResult(True, _uncovered_reply(question_domain, coverage))

    return GuardrailResult(False, None)
