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
    cursor = get_collection("day_signals").find(
        {"userId": ObjectId(user_id), "sessionId": ObjectId(session_id)},
        {"_id": 0},
    ).sort("dayId", 1)
    return [_to_json_value(doc) for doc in cursor]


def _session_label(session_id: str) -> str:
    session = get_collection("sessions").find_one({"_id": ObjectId(session_id)}, {"label": 1})
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


def build_evolution_input(user_id: str) -> dict:
    """Monta JSON comparativo entre campanhas para o Analista."""
    metrics_docs = list(
        get_collection("session_metrics")
        .find({"userId": ObjectId(user_id)}, {"_id": 0})
        .sort("sessionNumber", 1)
    )

    campaigns = []
    for idx, metrics in enumerate(metrics_docs, start=1):
        session_id_raw = metrics.get("sessionId")
        session_id = str(session_id_raw) if session_id_raw else None
        signals = _signals_for_session(user_id, session_id) if session_id else []
        campaigns.append(
            {
                "sessionId": session_id,
                "sessionNumber": metrics.get("sessionNumber", idx),
                "label": _session_label(session_id) if session_id else f"Campanha {idx}",
                "overallTone": metrics.get("overallTone"),
                "completedDays": metrics.get("completedDays", 0),
                "byWeek": _to_json_value(metrics.get("byWeek", {})),
                "campaignArc": _to_json_value(metrics.get("campaignArc", {})),
                "daySignalsCount": len(signals),
                "daySignals": signals,
            }
        )

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
                        _safe_num(b.get("destructiveAvg")) - _safe_num(a.get("destructiveAvg")), 1
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
