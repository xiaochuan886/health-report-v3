from __future__ import annotations

NORMAL_LABELS = {"正常", "阴性", "未见", "未检出", "/"}


def _match_multi_rule(value, rules: list[dict]) -> str:
    for rule in rules:
        kind = rule["kind"]
        if kind == "range":
            if rule["low"] <= value <= rule["high"]:
                return rule["label"]
        elif kind == "bound":
            op = rule["op"]
            boundary = rule["value"]
            if op in {"<", "≤"} and value <= boundary:
                return rule["label"]
            if op in {">", "≥"} and value >= boundary:
                return rule["label"]
        else:
            return rule["label"]
    return "unknown"


def _normalize_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def evaluate_risk(value, parsed: dict) -> dict:
    if parsed["kind"] == "range":
        low = parsed["low"]
        high = parsed["high"]
        span = high - low
        if value < low:
            return {"risk_status": "below", "is_abnormal": True}
        if value > high:
            return {"risk_status": "above", "is_abnormal": True}
        if span > 0 and value >= low + 0.8 * span:
            return {"risk_status": "near_upper", "is_abnormal": False}
        if low != 0 and span > 0 and value <= low + 0.2 * span:
            return {"risk_status": "near_lower", "is_abnormal": False}
        return {"risk_status": "normal", "is_abnormal": False}

    if parsed["kind"] == "upper_bound":
        boundary = parsed["value"]
        if value > boundary:
            return {"risk_status": "above", "is_abnormal": True}
        if boundary != 0 and value >= 0.8 * boundary:
            return {"risk_status": "near_upper", "is_abnormal": False}
        return {"risk_status": "normal", "is_abnormal": False}

    if parsed["kind"] == "lower_bound":
        boundary = parsed["value"]
        if value < boundary:
            return {"risk_status": "below", "is_abnormal": True}
        if boundary != 0 and value <= 1.2 * boundary:
            return {"risk_status": "near_lower", "is_abnormal": False}
        return {"risk_status": "normal", "is_abnormal": False}

    if parsed["kind"] == "multi_rule":
        risk_status = _match_multi_rule(value, parsed.get("rules", []))
        if risk_status in NORMAL_LABELS:
            return {"risk_status": "normal", "is_abnormal": False}
        return {
            "risk_status": risk_status,
            "is_abnormal": risk_status not in NORMAL_LABELS,
        }

    if parsed["kind"] == "qual_only":
        risk_status = "normal" if _normalize_text(value) == _normalize_text(parsed.get("label")) else "unknown"
        return {"risk_status": risk_status, "is_abnormal": risk_status != "normal"}

    return {"risk_status": "unknown", "is_abnormal": False}
