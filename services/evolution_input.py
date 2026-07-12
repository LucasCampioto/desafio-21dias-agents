from datetime import datetime

from bson import ObjectId

from db.mongo import get_collection


def _safe_num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_json_value(value):
    """Converte tipos MongoDB para valores serializáveis em JSON."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _to_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_json_value(item) for item in value]
    return value


def _signals_for_session(user_id: str, session_id: str) -> list[dict]:
    cursor = (
        get_collection("day_signals")
        .find(
            {"userId": ObjectId(user_id), "sessionId": ObjectId(session_id)},
            {"_id": 0},
        )
        .sort("dayId", 1)
    )
    return [_to_json_value(doc) for doc in cursor]


def _session_label(session: dict | None, session_id: str) -> str:
    if session and session.get("label"):
        return session["label"]
    return session_id


def _week_pct(week_data: dict | None, key: str) -> float:
    if not week_data:
        return 0.0
    pct_key = f"{key}Pct"
    if pct_key in week_data:
        return _safe_num(week_data.get(pct_key))
    # legado: soma de scores 0–1 por dia na semana
    raw = _safe_num(week_data.get(key))
    day_count = week_data.get("dayCount") or 7
    if raw <= 1:
        return round(raw * 100, 1)
    return round((raw / day_count) * 100, 1)


def _campaign_from_session(user_id: str, session: dict, idx: int) -> dict:
    session_id = str(session["_id"])
    progress = get_collection("session_progress").find_one({"sessionId": session["_id"]}) or {}
    completed = progress.get("completedDays") or []
    signals = _signals_for_session(user_id, session_id)
    metrics = get_collection("session_metrics").find_one({"sessionId": session["_id"]}, {"_id": 0}) or {}

    return {
        "sessionId": session_id,
        "sessionNumber": metrics.get("sessionNumber", idx),
        "label": _session_label(session, session_id),
        "overallTone": metrics.get("overallTone") or "neutral",
        "completedDays": metrics.get("completedDays") or completed,
        "byWeek": _to_json_value(metrics.get("byWeek") or {}),
        "campaignArc": _to_json_value(metrics.get("campaignArc") or {}),
        "daySignalsCount": len(signals),
        "daySignals": signals,
        "answersCount": get_collection("day_answers").count_documents(
            {"userId": ObjectId(user_id), "sessionId": session["_id"]}
        ),
    }


def build_evolution_input(user_id: str) -> dict:
    """Monta JSON comparativo entre campanhas para o Analista.

    Preferência: session_metrics. Fallback: sessions + day_answers (quando agents
    esteve offline e métricas nunca foram geradas).
    """
    uid = ObjectId(user_id)
    metrics_docs = list(
        get_collection("session_metrics").find({"userId": uid}, {"_id": 0}).sort("sessionNumber", 1)
    )

    campaigns = []
    if metrics_docs:
        for idx, metrics in enumerate(metrics_docs, start=1):
            session_id_raw = metrics.get("sessionId")
            session_id = str(session_id_raw) if session_id_raw else None
            signals = _signals_for_session(user_id, session_id) if session_id else []
            session = (
                get_collection("sessions").find_one({"_id": ObjectId(session_id)}, {"label": 1})
                if session_id
                else None
            )
            campaigns.append(
                {
                    "sessionId": session_id,
                    "sessionNumber": metrics.get("sessionNumber", idx),
                    "label": _session_label(session, session_id or f"Campanha {idx}"),
                    "overallTone": metrics.get("overallTone"),
                    "completedDays": metrics.get("completedDays", 0),
                    "byWeek": _to_json_value(metrics.get("byWeek", {})),
                    "campaignArc": _to_json_value(metrics.get("campaignArc", {})),
                    "daySignalsCount": len(signals),
                    "daySignals": signals,
                }
            )
    else:
        sessions = list(
            get_collection("sessions").find({"userId": uid}).sort("createdAt", 1)
        )
        for idx, session in enumerate(sessions, start=1):
            campaign = _campaign_from_session(user_id, session, idx)
            # Só inclui se houver algum progresso real
            completed = campaign.get("completedDays") or []
            if campaign["answersCount"] > 0 or (isinstance(completed, list) and len(completed) > 0):
                campaigns.append(campaign)

    comparatives = []
    if len(campaigns) >= 2:
        first = campaigns[0]
        last = campaigns[-1]

        def week_delta(week: str) -> dict | None:
            a = (first.get("byWeek") or {}).get(week, {})
            b = (last.get("byWeek") or {}).get(week, {})
            if not a and not b:
                return None
            return {
                "week": week,
                "negativePct": {
                    "from": _week_pct(a, "negative"),
                    "to": _week_pct(b, "negative"),
                    "delta": round(_week_pct(b, "negative") - _week_pct(a, "negative"), 1),
                },
                "positivePct": {
                    "from": _week_pct(a, "positive"),
                    "to": _week_pct(b, "positive"),
                    "delta": round(_week_pct(b, "positive") - _week_pct(a, "positive"), 1),
                },
                "destructiveAvg": {
                    "from": _safe_num(a.get("destructiveAvg")),
                    "to": _safe_num(b.get("destructiveAvg")),
                    "delta": round(
                        _safe_num(b.get("destructiveAvg")) - _safe_num(a.get("destructiveAvg")),
                        1,
                    ),
                },
            }

        for week in ("1", "2", "3"):
            item = week_delta(week)
            if item:
                comparatives.append(item)

        def day1_destructive(campaign: dict) -> float | None:
            for signal in campaign.get("daySignals", []):
                if signal.get("dayId") == 1:
                    thoughts = (signal.get("fieldSignals") or {}).get("thoughts_recurring") or {}
                    return thoughts.get("destructiveCount")
            return None

        d1_first = day1_destructive(first)
        d1_last = day1_destructive(last)
        if d1_first is not None and d1_last is not None:
            comparatives.append(
                {
                    "metric": "day1_destructive_delta",
                    "from": d1_first,
                    "to": d1_last,
                    "delta": d1_last - d1_first,
                    "narrative_hint": (
                        f"Pensamentos destrutivos/dia no início (dia 1): "
                        f"{d1_first} → {d1_last} (contagem, não percentual)"
                    ),
                }
            )

    return {
        "userId": user_id,
        "campaignCount": len(campaigns),
        "campaigns": campaigns,
        "comparatives": comparatives,
    }
