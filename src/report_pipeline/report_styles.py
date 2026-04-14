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
    return f"{code}<br/>{name}"


def nutrition_indicator_display(row: dict) -> str:
    """Merge category and indicator for nutrition summary."""
    category = format_display(row.get("category"))
    name = indicator_display_name(row)
    if category == "--" or not category:
        return name
    return f"{category}<br/>{name}"


# Status Color Mapping for Medical Best Practice:
# 超过参考区间 (above/below/outliers) -> Red, 接近/不足 (near/insufficiency) -> Orange, Other -> Dark Gray
STATUS_COLORS = {
    "above": "#E53E3E",          # Red
    "below": "#E53E3E",          # Red
    "near_upper": "#DD6B20",     # Orange
    "near_lower": "#DD6B20",     # Orange
    "normal": "#2D3748",         # Dark Gray (Ink)
    "unknown": "#718096",        # Gray
    "不足": "#DD6B20",           # Orange
    # Fine-grained VD levels:
    "严重缺乏": "#E53E3E",       # Red
    "缺乏": "#E53E3E",           # Red
    "过量": "#E53E3E",           # Red
    "中毒": "#E53E3E",           # Red
}


def get_status_color(status: str) -> str:
    """Map risk status to hex color based on medical best practice."""
    # Check for direct matches (for fine-grained labels from risk rules)
    if status in STATUS_COLORS:
        return STATUS_COLORS[status]
    # Fallback to general mapping
    return "#718096"


def get_status_arrow(status: str) -> str:
    """Return upward/downward arrow for outliers or high/low risk words."""
    s = str(status).strip()
    if s in {"above", "过量", "中毒"}:
        return "↑"
    if s in {"below", "严重缺乏", "缺乏", "不足"}:
        return "↓"
    return ""


def get_status_summary_text(status: str) -> str:
    """Return shorter status text for summary table."""
    s = str(status).strip()
    # If the status is already a fine-grained medical label (like "严重缺乏"), return it directly
    FINE_GRAINED_LABELS = {"严重缺乏", "缺乏", "不足", "正常", "过量", "中毒"}
    if s in FINE_GRAINED_LABELS:
        return s

    mapping = {
        "above": "高于上限",
        "below": "低于下限",
        "near_upper": "接近上限",
        "near_lower": "接近下限",
        "不足": "营养不足",
    }
    return mapping.get(s, "")
