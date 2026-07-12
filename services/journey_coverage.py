"""Mapa temático da jornada (Mongo direto): escores por domínio, readiness e evidências limitadas."""

from __future__ import annotations

from dataclasses import dataclass

from db.mongo import get_collection, try_object_id


def _safe_float(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


@dataclass
class JourneyCoverage:
    user_id: str
    session_id: str | None
    session_exists: bool
    session_missing: bool
    has_registered_journey_content: bool
    session_label: str | None
    domains: dict[str, dict[str, float | list]]
    primary_domain: str
    readiness: str
    emotional_arc: dict


def _finance_field_hit(field_key: str) -> float:
    k = field_key.lower()
    if "financial_" in k or k.startswith("financial"):
        return 0.55
    for token in ("money", "salary", "salário", "spend", "spending", "debt"):
        if token in k:
            return 0.15
    return 0.0


def _rel_field_hit(field_key: str) -> float:
    k = field_key.lower()
    for blob in ("family", "familia", "mother", "father", "parent", "partner", "relationship", "conjuge"):
        if blob in k:
            return 0.55
    return 0.0


def _self_field_hit(field_key: str) -> float:
    k = field_key.lower()
    for blob in ("self_", "comparison", "identity", "estima", "worth", "shame"):
        if blob in k:
            return 0.4
    return 0.0


def _scan_text_for_domains(text_lower: str) -> dict[str, float]:
    deltas = {"finance": 0.0, "relationships": 0.0, "self_worth": 0.0}
    fin_kw = (
        "dinheiro",
        "compr",
        "dívida",
        "divida",
        "invest",
        "gast",
        "salário",
        "salario",
        "consumo",
        "impuls",
        "extrato",
        "conta ",
        "poupan",
        "economia",
        "macbook",
    )
    rel_kw = (
        "família",
        "familia",
        "mãe",
        "mae",
        "pai",
        "parceiro",
        "namor",
        "espos",
        "marido",
        "conjuge",
        "cônjuge",
        "amigo ",
        "amiga ",
        "famili",
    )
    self_kw = (
        "autoestima",
        "compar",
        "identidade",
        "vergonha",
        "culpa",
        "inútil",
        "inutil",
        "incrível ",
        "medo ",
        "sou assim",
        "não sirvo",
        "nao sirvo",
    )
    if any(k in text_lower for k in fin_kw):
        deltas["finance"] += 0.12
    if any(k in text_lower for k in rel_kw):
        deltas["relationships"] += 0.14
    if any(k in text_lower for k in self_kw):
        deltas["self_worth"] += 0.13
    return deltas


def _theme_domain(theme: str) -> str | None:
    t = theme.lower()
    if any(k in t for k in ("dinheir", "compr", "consum", "finance", "invest", "dívida", "orcamento")):
        return "finance"
    if any(k in t for k in ("família", "parceiro", "mãe", "pai", "relacio", "vínculo", "afilha")):
        return "relationships"
    if any(k in t for k in ("auto", "valor", "compara", "identidade", "culpa", "medo")):
        return "self_worth"
    return None


def _accumulate_domains_from_answers(answers_blob: dict, day_id: int) -> tuple[dict[str, float], dict[str, list[str]]]:
    raw = {"finance": 0.0, "relationships": 0.0, "self_worth": 0.0}
    evidence_bucket: dict[str, list[str]] = {"finance": [], "relationships": [], "self_worth": []}

    def _push(kind: str, label: str) -> None:
        if len(evidence_bucket[kind]) < 12:
            evidence_bucket[kind].append(f"{label} (dia {day_id})")

    for field_key, value in (answers_blob or {}).items():
        fk = str(field_key)
        raw["finance"] += _finance_field_hit(fk)
        raw["relationships"] += _rel_field_hit(fk)
        raw["self_worth"] += _self_field_hit(fk)
        texts: list[str] = []
        if isinstance(value, str):
            texts.append(value)
        elif isinstance(value, list):
            texts.extend(str(x) for x in value)
        merged = "\n".join(texts).lower()
        deltas = _scan_text_for_domains(merged)
        for k, v in deltas.items():
            raw[k] += v
        excerpt = merged.replace("\n", " ").strip()
        excerpt_short = excerpt[:120] + ("..." if len(excerpt) > 120 else "")
        score_hit = False
        if _finance_field_hit(fk):
            score_hit = True
            _push("finance", f"Campo {fk}: \"{excerpt_short}\"")
        elif _rel_field_hit(fk):
            score_hit = True
            _push("relationships", f"Campo {fk}: \"{excerpt_short}\"")
        elif _self_field_hit(fk):
            score_hit = True
            _push("self_worth", f"Campo {fk}: \"{excerpt_short}\"")
        if not score_hit and excerpt_short:
            for kind in ("finance", "relationships", "self_worth"):
                chunk = deltas.get(kind, 0)
                if chunk > 0 and len(evidence_bucket[kind]) < 12:
                    _push(kind, excerpt_short[:90])

    return raw, evidence_bucket


def _merge_evidence(primary: dict[str, list[str]], extra: dict[str, list[str]]) -> None:
    for k in primary:
        for item in extra.get(k, []):
            if len(primary[k]) < 24:
                primary[k].append(item)


def _limit_evidence(kind_lists: dict[str, list[str]], max_total: int = 8) -> dict[str, list[str]]:
    """Extrai até `max_total` evidências com round-robin para não ficar só em um domínio."""
    queues = {k: list(v) for k, v in kind_lists.items()}
    keys_sorted = sorted(queues.keys())
    out = {k: [] for k in kind_lists}
    picked = 0
    rr = 0
    while picked < max_total and any(queues[k] for k in keys_sorted):
        k = keys_sorted[rr % len(keys_sorted)]
        rr += 1
        if not queues[k]:
            continue
        out[k].append(queues[k].pop(0))
        picked += 1
    return out


def _normalize_scores(raw: dict[str, float]) -> dict[str, float]:
    """Mapa raw → 0..1 usando saturação suave (~3 pontos crus ≈ alto)."""
    out = {}
    for k, pts in raw.items():
        # saturação: 4 pts crus ~ 100%
        out[k] = max(0.0, min(1.0, pts / 3.25))
    return out


def _compute_readiness(
    campaign_arc: dict,
    destructive_recent: float,
) -> str:
    end = campaign_arc.get("end") or {}
    end_neg = _safe_float(end.get("negativePct"))
    dest = _safe_float(destructive_recent)
    if end_neg >= 58 or dest >= 4:
        return "not_ready"
    if end_neg >= 40 or dest >= 2.4:
        return "cautious"
    return "ready"


def _emotional_arc_from_metrics(metrics: dict | None) -> dict:
    if not metrics:
        return {}
    arc = metrics.get("campaignArc") or {}
    start = arc.get("start") or {}
    end = arc.get("end") or {}
    return {
        "startNeg": _safe_float((start.get("negativePct"))),
        "endNeg": _safe_float((end.get("negativePct"))),
        "endPos": _safe_float((end.get("positivePct"))),
    }


def _empty_coverage_payload(user_id: str | None, session_id: str | None) -> JourneyCoverage:
    blanks = {"score": 0.0, "evidence": []}
    domains = {
        "finance": dict(blanks),
        "relationships": dict(blanks),
        "self_worth": dict(blanks),
        "journey_meta": dict(blanks),
        "general": dict(blanks),
    }
    return JourneyCoverage(
        user_id=user_id or "",
        session_id=session_id,
        session_exists=False,
        session_missing=not session_id,
        has_registered_journey_content=False,
        session_label=None,
        domains=domains,
        primary_domain="general",
        readiness="cautious",
        emotional_arc={},
    )


def build_journey_coverage(user_id: str, session_id: str | None) -> JourneyCoverage:
    try:
        return _build_journey_coverage_unsafe(user_id, session_id)
    except Exception:
        # Mongo/Atlas indisponível não pode derrubar o chat com 500 opaco.
        return _empty_coverage_payload(user_id, session_id)


def _build_journey_coverage_unsafe(user_id: str, session_id: str | None) -> JourneyCoverage:
    session_missing = not session_id
    sid = None
    session_exists = False
    has_content = False
    session_label: str | None = None

    domains_raw = {"finance": 0.0, "relationships": 0.0, "self_worth": 0.0, "journey_meta": 0.0}
    evidence_workspace: dict[str, list[str]] = {
        "finance": [],
        "relationships": [],
        "self_worth": [],
        "journey_meta": [],
    }

    destructive_recent = 0.0
    campaign_arc: dict = {}

    uid = try_object_id(user_id)
    if uid is None:
        return _empty_coverage_payload(user_id, session_id)

    evolution = get_collection("evolution_reports").find_one({"userId": uid}, {"report.patterns.items": 1})
    metrics_doc = None

    if not session_missing:
        sid = try_object_id(str(session_id).strip())

    if not session_missing and sid is None:
        session_exists = False

    elif not session_missing and sid is not None:
        sess = get_collection("sessions").find_one(
            {"_id": sid, "userId": uid},
            {"label": 1, "status": 1},
        )
        session_exists = bool(sess)
        session_label = (sess or {}).get("label")

        metrics_doc = get_collection("session_metrics").find_one({"sessionId": sid}, {"_id": 0})
        campaign_arc = (metrics_doc or {}).get("campaignArc") or {}
        by_week = (metrics_doc or {}).get("byWeek") or {}
        recent_week_key = sorted(by_week.keys(), key=lambda z: _safe_float(z))[-1] if by_week else None
        if recent_week_key:
            wd = by_week.get(recent_week_key) or {}
            destructive_recent = _safe_float(wd.get("destructiveAvg"))

        if metrics_doc:
            # Cobertura "como está minha evolução" precisa ficar alta quando há métricas reais
            domains_raw["journey_meta"] += 2.1
            completed = metrics_doc.get("completedDays") or []
            cmp = ",".join(str(x) for x in completed[-5:])
            evidence_workspace["journey_meta"].append(
                f"Métricas da campanha: {metrics_doc.get('overallTone')} — dias registrados até {completed[-1] if completed else '?'}"
            )
            if cmp:
                evidence_workspace["journey_meta"].append(f"Últimos dias completos próximos: {cmp}")

        if session_exists:
            answers_count = 0
            for doc in get_collection("day_answers").find({"userId": uid, "sessionId": sid}, {"answers": 1, "dayId": 1}):
                ans = doc.get("answers") or {}
                did = int(doc.get("dayId") or 0)
                if not did:
                    continue
                has_content |= bool(ans)
                if ans:
                    answers_count += 1
                extra_raw, evid = _accumulate_domains_from_answers(ans, did)
                for k in domains_raw:
                    if k != "journey_meta":
                        domains_raw[k] += extra_raw[k]
                _merge_evidence(evidence_workspace, evid)

            # Histórico de exercícios já conta como base para perguntas de evolução
            if answers_count > 0:
                domains_raw["journey_meta"] += min(2.5, 0.35 + answers_count * 0.12)
                evidence_workspace["journey_meta"].append(
                    f"{answers_count} dias com respostas registradas nesta campanha"
                )

            for sig in get_collection("day_signals").find(
                {"userId": uid, "sessionId": sid},
                {"dayId": 1, "fieldSignals.thoughts_recurring.themes": 1},
            ):
                did = sig.get("dayId")
                themes = ((sig.get("fieldSignals") or {}).get("thoughts_recurring") or {}).get("themes") or []
                day_note = ""
                if isinstance(themes, list):
                    joined = "; ".join(str(t) for t in themes if t)
                    if joined[:160]:
                        day_note = f"Temas recorrentes (dia {did}): {joined[:140]}"
                    for th in themes:
                        dom = _theme_domain(str(th))
                        if dom:
                            domains_raw[dom] += 0.2
                            if len(evidence_workspace[dom]) < 16:
                                evidence_workspace[dom].append(day_note or str(th))

    patterns = ((((evolution or {}).get("report") or {}).get("patterns") or {}).get("items")) or []

    journey_meta_bonus = False
    for item in patterns[:4]:
        if item:
            journey_meta_bonus = True
            evidence_workspace["journey_meta"].append(f"Padrão salvo pelo analista: {str(item)[:160]}")

    if journey_meta_bonus:
        domains_raw["journey_meta"] += 1.05

    domains_norm = _normalize_scores(domains_raw)
    thematic_keys = ["finance", "relationships", "self_worth"]
    thematic_peak = max(domains_norm[t] for t in thematic_keys) if thematic_keys else 0.0
    meta_peak = domains_norm.get("journey_meta", 0.0)
    domains_norm["general"] = round(min(1.0, 0.06 + thematic_peak * 0.88 + meta_peak * 0.06), 4)

    primary = max(thematic_keys, key=lambda kk: domains_norm.get(kk, 0.0))

    limited_evidence = _limit_evidence(evidence_workspace, max_total=8)

    general_strip: list[str] = []
    for kk in thematic_keys + ["journey_meta"]:
        for ln in limited_evidence.get(kk, []):
            if len(general_strip) >= 8:
                break
            general_strip.append(f"[{kk}] {(str(ln))[:172]}")
    limited_evidence["general"] = general_strip[:8]

    domains_out = {
        kk: {"score": float(domains_norm.get(kk, 0.0)), "evidence": limited_evidence.get(kk, [])}
        for kk in domains_norm.keys()
    }

    readiness = _compute_readiness(campaign_arc, destructive_recent)

    return JourneyCoverage(
        user_id=user_id,
        session_id=session_id,
        session_exists=session_exists,
        session_missing=session_missing,
        has_registered_journey_content=(not session_missing) and session_exists and has_content,
        session_label=session_label,
        domains=domains_out,
        primary_domain=primary,
        readiness=readiness,
        emotional_arc=_emotional_arc_from_metrics(metrics_doc),
    )
