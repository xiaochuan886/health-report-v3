from __future__ import annotations

from typing import Any


STATUS_LABELS = {
    "above": "高于参考范围",
    "below": "低于参考范围",
    "near_upper": "接近上限",
    "near_lower": "接近下限",
    "normal": "正常",
    "unknown": "暂无法判断",
    "不足": "不足",
}

RISK_BAR_LEVELS = {
    "above": 10,
    "below": 2,
    "near_upper": 8,
    "near_lower": 3,
    "normal": 5,
    "unknown": 0,
    "不足": 3,
}


def format_display(value: Any, default: str = "--") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def status_label(status: str) -> str:
    text = format_display(status, default="unknown")
    return STATUS_LABELS.get(text, text)


def risk_bar(status: str, width: int = 10) -> str:
    level = RISK_BAR_LEVELS.get(format_display(status, default="unknown"), 5)
    filled = max(0, min(level, width))
    return "█" * filled + "░" * (width - filled)


def indicator_display_name(row: dict) -> str:
    """Return 'CODE NAME' format, e.g. 'FER 铁蛋白'."""
    code = format_display(row.get("indicator_short_name"))
    name = format_display(row.get("indicator_display_name"))
    if name == "--":
        return code
    if code == "--":
        return name
    return f"{code} {name}"
