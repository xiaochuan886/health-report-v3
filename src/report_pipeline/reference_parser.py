from __future__ import annotations

import re


NUMBER = r"-?\d+(?:\.\d+)?(?:E[+-]?\d+)?"
RANGE_RE = re.compile(rf"^\s*({NUMBER})\s*-\s*({NUMBER})\s*$", re.I)
BOUND_RE = re.compile(rf"^\s*(?P<op>[<>≤≥＜＞]|<=|>=)\s*(?P<value>{NUMBER})\s*$", re.I)
QUAL_ONLY_RE = re.compile(r"^\s*(阴性|阳性|未见|未检出|/)\s*$")
# 复合条件：low_op value (且/AND/&) high_op value，如 "≥5.20且<6.20"
COMPOUND_BOUND_RE = re.compile(
    rf"^\s*(?P<low_op>[<>≤≥＜＞]|<=|>=)\s*(?P<low>{NUMBER})\s*(?:且|AND|and|&)\s*(?P<high_op>[<>≤≥＜＞]|<=|>=)\s*(?P<high>{NUMBER})\s*$",
    re.I,
)


def _normalize_op(op: str) -> str:
    return (
        op.replace("＜", "<")
        .replace("＞", ">")
        .replace("≤", "<=")
        .replace("≥", ">=")
    )


def _apply_op(op: str, value: float, boundary: float) -> bool:
    """按运算符语义判定，严格区分 < 与 ≤（修复旧版一律按 <= 处理的 bug）。"""
    op = _normalize_op(op)
    if op in {"<", "<="}:
        return value < boundary if op == "<" else value <= boundary
    if op in {">", ">="}:
        return value > boundary if op == ">" else value >= boundary
    return False


def _parse_rule_line(line: str) -> dict | None:
    stripped = line.strip()

    # 1) 冒号分隔的传统写法优先：标签:表达式（维D 等）
    colon_match = re.match(r"^(?P<label>[^:：]+?)\s*[:：]\s*(?P<expr>.+?)$", stripped)
    if colon_match:
        label = colon_match.group("label").strip()
        expr = colon_match.group("expr").strip()
        rule = _build_rule(label, expr)
        if rule:
            return rule

    # 2) 无冒号的血脂分级写法：标签后接运算符+数字 或 直接接数字区间
    #    label 排除数字与运算符，expr 起始消费"运算符+数字"或"数字"，保证运算符不落入 label
    m = re.match(
        rf"^(?P<label>[^\d<>=≤≥＜＞\-]+?)(?P<expr>(?:<=|>=|[<>≤≥＜＞])\s*-?\d+(?:\.\d+)?|-?\d+(?:\.\d+)?)",
        stripped,
    )
    if m:
        label = m.group("label").strip()
        expr = stripped[len(m.group("label")):].strip()
        if label and expr:
            return _build_rule(label, expr)

    return None


def _build_rule(label: str, expr: str) -> dict | None:
    if not label or not expr:
        return None

    range_match = RANGE_RE.match(expr)
    if range_match:
        return {
            "label": label,
            "kind": "range",
            "low": float(range_match.group(1)),
            "high": float(range_match.group(2)),
        }

    compound_match = COMPOUND_BOUND_RE.match(expr)
    if compound_match:
        return {
            "label": label,
            "kind": "compound_bound",
            "low_op": _normalize_op(compound_match.group("low_op")),
            "low": float(compound_match.group("low")),
            "high_op": _normalize_op(compound_match.group("high_op")),
            "high": float(compound_match.group("high")),
        }

    bound_match = BOUND_RE.match(expr)
    if bound_match:
        return {
            "label": label,
            "kind": "bound",
            "op": _normalize_op(bound_match.group("op")),
            "value": float(bound_match.group("value")),
        }

    return {"label": label, "kind": "special", "expr": expr}


def _split_rule_segments(text: str) -> list[str]:
    """按换行和中英文分号切分规则段，兼容单行多规则（血脂分级常见）。"""
    segments: list[str] = []
    for line in text.splitlines():
        for part in re.split(r"[；;]", line):
            part = part.strip()
            if part:
                segments.append(part)
    return segments


def parse_reference(raw: str) -> dict:
    text = "" if raw is None else str(raw).strip()
    if not text or text.lower() == "nan":
        return {"kind": "empty", "raw": text}

    rule_segments = _split_rule_segments(text)
    parsed_rules = [r for r in (_parse_rule_line(seg) for seg in rule_segments) if r is not None]
    if len(parsed_rules) > 1:
        return {
            "kind": "multi_rule",
            "raw": text,
            "labels": [rule["label"] for rule in parsed_rules],
            "rules": parsed_rules,
        }

    range_match = RANGE_RE.match(text)
    if range_match:
        return {
            "kind": "range",
            "raw": text,
            "low": float(range_match.group(1)),
            "high": float(range_match.group(2)),
        }

    bound_match = BOUND_RE.match(text)
    if bound_match:
        op = _normalize_op(bound_match.group("op"))
        value = float(bound_match.group("value"))
        kind = "upper_bound" if op in {"<", "≤", "<="} else "lower_bound"
        return {
            "kind": kind,
            "raw": text,
            "op": op,
            "value": value,
        }

    if QUAL_ONLY_RE.match(text):
        return {
            "kind": "qual_only",
            "raw": text,
            "label": text,
        }

    if len(parsed_rules) == 1:
        return {
            "kind": "multi_rule",
            "raw": text,
            "labels": [parsed_rules[0]["label"]],
            "rules": parsed_rules,
        }

    return {"kind": "special", "raw": text}
