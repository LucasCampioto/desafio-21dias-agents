"""Contexto Aurora: base leve + recorte dinâmico do domínio da pergunta (bullets curtos + citações)."""

from __future__ import annotations


from db.mongo import get_collection, try_object_id

from services.journey_coverage import JourneyCoverage
from tools.backend_tools import fetch_today_lesson, fetch_today_status


MAX_CHARS_QUOTE = 200


def _short(s: str, cap: int) -> str:
    s = s.replace("\n", " ").strip()
    if len(s) <= cap:
        return s
    return s[: cap - 1].rstrip() + "…"


def _quotes_for_theme(user_id: str, session_id: str, topic: str) -> list[str]:
    """Até duas falas suas (~200 caracteres cada) próximas do tema."""
    fk_checks: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
        "finance": (("financial", "money"), ("dinheir", "gast", "compr", "dívida", "divida", "invest")),
        "relationships": (("famil", "parent", "mother", "pai", "partner"), ("mãe", "mae", "pai", "parce")),
        "self_worth": (("self_", "comparison", "identity"), ("auto", "valor", "culpa", "vergonh")),
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
        did = doc.get("dayId")
        for fk, raw in blob.items():
            fk_l = str(fk).lower()
            if isinstance(raw, str):
                text = raw
            elif isinstance(raw, list):
                text = " ".join(str(x) for x in raw)
            else:
                text = str(raw)

            stripped = text.strip()
            if not stripped:
                continue

            if topic in ("journey_meta", "general"):
                minimum = 32 if topic == "general" else 40
                if len(stripped) < minimum:
                    continue
                score = len(stripped)
            else:
                groups = fk_checks.get(topic)
                if groups is None:
                    continue
                hits: list[str] = []
                for prefix_grp in groups[0]:
                    if prefix_grp and prefix_grp in fk_l:
                        hits.append(prefix_grp)
                t_l = text.lower()
                for kw_grp in groups[1]:
                    if kw_grp and kw_grp in fk_l:
                        hits.append(kw_grp)
                    if kw_grp and kw_grp in t_l:
                        hits.append(kw_grp)
                if not hits:
                    continue

                score = len(stripped) + sum(len(h) for h in hits) * 10
            phrase = f'Dia {did} — campo "{fk}": {_short(text, MAX_CHARS_QUOTE)}'
            weighted.append((score, phrase))

        if len(weighted) >= 14:
            break

    weighted.sort(reverse=True)

    dedup: list[str] = []
    for _, line in weighted:
        if line not in dedup:
            dedup.append(line)
        if len(dedup) >= 2:
            break
    return dedup


def _base_block(user_id: str, session_id: str | None, coverage: JourneyCoverage) -> list[str]:
    lines: list[str] = []
    lines.append(f"Usuário: {user_id}")
    if coverage.session_missing or not session_id:
        lines.append("Sem campanha ativa no backend — convide com gentileza a iniciar em /jornada/iniciar.")
        return lines

    status = fetch_today_status(user_id, session_id)
    lesson = fetch_today_lesson(user_id, session_id)
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


def _thematic_block(user_id: str, session_id: str | None, topic: str, coverage: JourneyCoverage) -> list[str]:
    if not session_id:
        return ["Recorte temático pausado — sem sessão."]
    lines = [
        f"Pergunta orientada pelo roteamento temático **`{topic}`**.",
        "",
        "**Bullets objetivos da jornada (6–8 itens):**",
    ]
    domain_bundle = coverage.domains.get(topic) or {}
    ev = list(domain_bundle.get("evidence") or [])
    bullets = [_short(str(x), 180) for x in ev][:8]
    if len(bullets) < 6:
        fillers = coverage.domains.get(coverage.primary_domain, {}).get("evidence") or []
        for f in fillers:
            s = _short(str(f), 180)
            if s not in bullets:
                bullets.append(s)
            if len(bullets) >= 6:
                break
    bullets = bullets[:8]
    for b in bullets:
        lines.append(f"- {b}")

    lines.append("")
    lines.append("**Trechos suas (no máximo 2, ~200 caracteres cada):**")
    quotes = _quotes_for_theme(user_id, session_id, topic)
    if topic == "journey_meta":
        fallback = []
        for kk in ("finance", "self_worth"):
            fallback.extend(_quotes_for_theme(user_id, session_id, kk))
        merged: list[str] = []
        for q in quotes + fallback:
            if q not in merged:
                merged.append(q)
            if len(merged) >= 2:
                break
        quotes = merged

    if not quotes:
        lines.append("- *(não havia texto longo o suficiente para citar literalmente aqui)*")
    else:
        for q in quotes[:2]:
            lines.append(f"- {q}")

    lines.append("")
    lines.append(f"Domínio principal já consolidado antes desta mensagem: **{coverage.primary_domain}**.")
    return lines


def build_aurora_context(user_id: str, session_id: str | None, topic: str, coverage: JourneyCoverage) -> str:
    """Texto combinado com base + tema; pode ser truncado se explodir de tamanho."""
    base_lines = ["## Contexto-base", "", *_base_block(user_id, session_id, coverage)]
    theme_header = ["", "## Recorte dinâmico da pergunta", ""]
    theme_lines = _thematic_block(user_id, session_id, topic, coverage)
    assembled = "\n".join(base_lines + theme_header + theme_lines)
    soft_cap = 10000
    if len(assembled) > soft_cap:
        assembled = assembled[: soft_cap - 1] + "\n…(truncado automaticamente pelo limite de segurança)"
    return assembled
