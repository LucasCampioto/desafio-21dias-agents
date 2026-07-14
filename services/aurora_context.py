"""Contexto Aurora: registros recentes da jornada ativa + recorte temático."""

from __future__ import annotations

import re

from db.mongo import get_collection, try_object_id
from services.journey_coverage import JourneyCoverage
from tools.backend_tools import fetch_today_lesson, fetch_today_status

MAX_CHARS_QUOTE = 220
RECENT_DAYS = 3
RECENT_FIELDS_PER_DAY = 6
SOFT_CAP = 5500


def _short(s: str, cap: int) -> str:
    s = s.replace("\n", " ").strip()
    if len(s) <= cap:
        return s
    return s[: cap - 1].rstrip() + "…"


def _normalize_text(raw) -> str:
    if raw is None:
        return ""
    if isinstance(raw, list):
        return " ".join(str(x) for x in raw if x).strip()
    return str(raw).strip()


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-zà-ü0-9]{3,}", (text or "").lower()) if t}


def _message_overlap_score(text: str, message: str) -> int:
    msg_tokens = _tokenize(message)
    if not msg_tokens:
        return 0
    text_tokens = _tokenize(text)
    return len(msg_tokens & text_tokens) * 25


def _recent_answers_block(user_id: str, session_id: str | None, message: str) -> list[str]:
    """Últimos dias respondidos da jornada ativa — fonte principal para decisões do dia a dia."""
    lines = [
        "## Registros recentes da jornada ativa (prioridade alta)",
        "",
        "Use estes trechos primeiro ao responder decisões cotidianas (sair, beber, gastar, relações, etc.).",
        "",
    ]
    uid = try_object_id(user_id)
    sid = try_object_id(session_id)
    if uid is None or sid is None:
        lines.append("- *(sem sessão ativa para consultar respostas)*")
        return lines

    cursor = (
        get_collection("day_answers")
        .find({"userId": uid, "sessionId": sid}, {"answers": 1, "dayId": 1, "updatedAt": 1})
        .sort([("dayId", -1), ("updatedAt", -1)])
        .limit(RECENT_DAYS)
    )
    docs = list(cursor)
    if not docs:
        lines.append("- *(ainda não há respostas salvas nesta jornada)*")
        return lines

    ranked: list[tuple[int, str]] = []
    for doc in docs:
        day_id = doc.get("dayId")
        answers = doc.get("answers") or {}
        for field_id, raw in answers.items():
            text = _normalize_text(raw)
            if len(text) < 12:
                continue
            score = len(text) + _message_overlap_score(text, message) + int(day_id or 0)
            # Boost forte para compromissos/comportamentos próximos da pergunta
            lower = text.lower()
            for kw in ("sair", "beber", "festa", "bar", "compromisso", "não vou", "nao vou", "parei", "jejum"):
                if kw in lower:
                    score += 40
            ranked.append(
                (
                    score,
                    f'- Dia {day_id} · `{field_id}`: "{_short(text, MAX_CHARS_QUOTE)}"',
                )
            )

    ranked.sort(reverse=True)
    picked = [line for _, line in ranked[: RECENT_DAYS * RECENT_FIELDS_PER_DAY]]
    if not picked:
        lines.append("- *(respostas found, mas muito curtas para citar)*")
        return lines

    lines.extend(picked)
    return lines


def _quotes_for_theme(user_id: str, session_id: str, topic: str, message: str = "") -> list[str]:
    """Até três falas próximas do tema / da pergunta, priorizando dias recentes."""
    fk_checks: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
        "finance": (("financial", "money"), ("dinheir", "gast", "compr", "dívida", "divida", "invest", "beber", "bar")),
        "relationships": (("famil", "parent", "mother", "pai", "partner"), ("mãe", "mae", "pai", "parce", "amigo")),
        "self_worth": (("self_", "comparison", "identity"), ("auto", "valor", "culpa", "vergonh")),
        "behavior": (
            ("behavior", "commitment", "decision", "habit", "jejum"),
            ("sair", "beber", "festa", "compromisso", "parei", "decisão", "decisao", "hábito", "habito"),
        ),
    }

    uid = try_object_id(user_id)
    sid = try_object_id(session_id)
    if uid is None or sid is None:
        return []

    weighted: list[tuple[int, str]] = []
    cursor = (
        get_collection("day_answers")
        .find({"userId": uid, "sessionId": sid}, {"answers": 1, "dayId": 1})
        .sort("dayId", -1)
    )
    for doc in cursor:
        blob = doc.get("answers") or {}
        did = int(doc.get("dayId") or 0)
        for fk, raw in blob.items():
            text = _normalize_text(raw)
            stripped = text.strip()
            if not stripped:
                continue

            fk_l = str(fk).lower()
            t_l = stripped.lower()
            score = _message_overlap_score(stripped, message) + did

            if topic in ("journey_meta", "general", "behavior"):
                if len(stripped) < 20:
                    continue
                score += len(stripped)
                for kw in ("sair", "beber", "festa", "compromisso", "não vou", "nao vou", "parei"):
                    if kw in t_l or kw in fk_l:
                        score += 50
            else:
                groups = fk_checks.get(topic)
                if groups is None:
                    continue
                hits: list[str] = []
                for prefix_grp in groups[0]:
                    if prefix_grp and prefix_grp in fk_l:
                        hits.append(prefix_grp)
                for kw_grp in groups[1]:
                    if kw_grp and (kw_grp in fk_l or kw_grp in t_l):
                        hits.append(kw_grp)
                if not hits and _message_overlap_score(stripped, message) == 0:
                    continue
                score += len(stripped) + sum(len(h) for h in hits) * 10

            phrase = f'Dia {did} — campo "{fk}": {_short(text, MAX_CHARS_QUOTE)}'
            weighted.append((score, phrase))

        if len(weighted) >= 24:
            break

    weighted.sort(reverse=True)
    dedup: list[str] = []
    for _, line in weighted:
        if line not in dedup:
            dedup.append(line)
        if len(dedup) >= 3:
            break
    return dedup


def _base_block(user_id: str, session_id: str | None, coverage: JourneyCoverage) -> list[str]:
    lines: list[str] = []
    lines.append(f"Usuário: {user_id}")
    if coverage.session_missing or not session_id:
        lines.append("Sem campanha ativa no backend — convide com gentileza a iniciar em /jornada/iniciar.")
        return lines

    try:
        status = fetch_today_status(user_id, session_id)
    except Exception:
        status = {"error": "status indisponível"}
    try:
        lesson = fetch_today_lesson(user_id, session_id)
    except Exception:
        lesson = {"error": "lição indisponível"}

    arcs = coverage.emotional_arc or {}
    lines.append(f"Sessão: {session_id} — rótulo: {coverage.session_label or 'campanha'}")
    lines.append(f"Tom geral (readiness atual): **{coverage.readiness}**")
    lines.append(
        f"Arco simplificado nos percentuais agregados → neg inicial {arcs.get('startNeg')}%, "
        f"neg final {arcs.get('endNeg')}%, pos final {arcs.get('endPos')}%."
    )
    lines.append(f"Snapshot técnico do dia atual: {status}")
    lines.append(f"Lição destacada pelo sistema: {lesson}")
    return lines


def _thematic_block(
    user_id: str,
    session_id: str | None,
    topic: str,
    coverage: JourneyCoverage,
    message: str,
) -> list[str]:
    if not session_id:
        return ["Recorte temático pausado — sem sessão."]
    lines = [
        f"Pergunta orientada pelo roteamento temático **`{topic}`**.",
        "",
        "**Trechos alinhados à pergunta (priorize estes):**",
    ]
    quotes = _quotes_for_theme(user_id, session_id, topic, message)
    if topic == "journey_meta":
        fallback = []
        for kk in ("finance", "self_worth", "behavior"):
            fallback.extend(_quotes_for_theme(user_id, session_id, kk, message))
        merged: list[str] = []
        for q in quotes + fallback:
            if q not in merged:
                merged.append(q)
            if len(merged) >= 3:
                break
        quotes = merged

    if not quotes:
        lines.append("- *(não havia texto suficientemente relevante para citar literalmente aqui)*")
    else:
        for q in quotes[:3]:
            lines.append(f"- {q}")

    lines.append("")
    lines.append("**Bullets objetivos da jornada:**")
    domain_bundle = coverage.domains.get(topic) or {}
    ev = list(domain_bundle.get("evidence") or [])
    bullets = [_short(str(x), 180) for x in ev][:6]
    if len(bullets) < 4:
        fillers = coverage.domains.get(coverage.primary_domain, {}).get("evidence") or []
        for f in fillers:
            s = _short(str(f), 180)
            if s not in bullets:
                bullets.append(s)
            if len(bullets) >= 4:
                break
    if not bullets:
        lines.append("- *(sem bullets temáticos consolidados)*")
    else:
        for b in bullets[:6]:
            lines.append(f"- {b}")

    lines.append("")
    lines.append(f"Domínio principal já consolidado antes desta mensagem: **{coverage.primary_domain}**.")
    return lines


def build_aurora_context(
    user_id: str,
    session_id: str | None,
    topic: str,
    coverage: JourneyCoverage,
    message: str = "",
) -> str:
    """Texto combinado: recentes primeiro, depois base + tema."""
    recent = _recent_answers_block(user_id, session_id, message)
    base_lines = ["## Contexto-base", "", *_base_block(user_id, session_id, coverage)]
    theme_header = ["", "## Recorte dinâmico da pergunta", ""]
    theme_lines = _thematic_block(user_id, session_id, topic, coverage, message)
    assembled = "\n".join([*recent, "", *base_lines, *theme_header, *theme_lines])
    if len(assembled) > SOFT_CAP:
        # Mantém o bloco recente intacto; corta só o restante
        recent_text = "\n".join(recent)
        rest_budget = max(800, SOFT_CAP - len(recent_text) - 40)
        rest = "\n".join([*base_lines, *theme_header, *theme_lines])
        assembled = recent_text + "\n\n" + rest[: rest_budget - 1] + "\n…(truncado)"
    return assembled
