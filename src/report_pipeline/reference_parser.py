from __future__ import annotations

import re


NUMBER = r"-?\d+(?:\.\d+)?(?:E[+-]?\d+)?"
RANGE_RE = re.compile(rf"^\s*({NUMBER})\s*-\s*({NUMBER})\s*$", re.I)
RULE_RE = re.compile(r"^\s*(?P<label>[^:：]+)\s*[:：]\s*(?P<expr>.+?)\s*$")
BOUND_RE = re.compile(rf"^\s*(?P<op>[<>≤≥＜＞])\s*(?P<value>{NUMBER})\s*$", re.I)
QUAL_ONLY_RE = re.compile(r"^\s*(阴性|阳性|未见|未检出|/)\s*$")


def _normalize_op(op: str) -> str:
    return op.replace("＜", "<").replace("＞", ">")


def _parse_rule_line(line: str) -> dict | None:
    match = RULE_RE.match(line)
    if not match:
        return None

    label = match.group("label").strip()
    expr = match.group("expr").strip()
    range_match = RANGE_RE.match(expr)
    if range_match:
        return {
            "label": label,
            "kind": "range",
            "low": float(range_match.group(1)),
            "high": float(range_match.group(2)),
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


def parse_reference(raw: str) -> dict:
    text = "" if raw is None else str(raw).strip()
    if not text or text.lower() == "nan":
        return {"kind": "empty", "raw": text}

    multi_rule_lines = [line.strip() for line in text.splitlines() if line.strip()]
    parsed_rules = [_parse_rule_line(line) for line in multi_rule_lines]
    if len(parsed_rules) > 1 and all(rule is not None for rule in parsed_rules):
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
        kind = "upper_bound" if op in {"<", "≤"} else "lower_bound"
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

    if len(parsed_rules) == 1 and parsed_rules[0] is not None:
        return {
            "kind": "multi_rule",
            "raw": text,
            "labels": [parsed_rules[0]["label"]],
            "rules": parsed_rules,
        }

    return {"kind": "special", "raw": text}
