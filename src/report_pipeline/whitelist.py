from __future__ import annotations

import re

import pandas as pd


def _clean_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _gender_allows(patient_gender: str, rule: str) -> bool:
    rule = _clean_text(rule).upper()
    gender = _clean_text(patient_gender).upper()

    if rule in {"F/M", "M/F", "男女", "男/女", "女/男"}:
        return True
    if gender in {"男", "M", "MALE"}:
        return rule in {"M", "男"}
    if gender in {"女", "F", "FEMALE"}:
        return rule in {"F", "女"}
    return False


def match_indicators(lab: pd.DataFrame, whitelist: pd.DataFrame, patient_gender: str) -> pd.DataFrame:
    eligible = whitelist.loc[whitelist["性别"].map(lambda rule: _gender_allows(patient_gender, rule))].copy()
    if "排序" in eligible.columns:
        eligible = eligible.sort_values(by="排序", ascending=True, kind="mergesort")

    by_short = {}
    by_shanghai = {}
    for _, row in eligible.iterrows():
        short_name = _clean_text(row.get("指标简称"))
        if short_name and short_name not in by_short:
            by_short[short_name] = row
        shanghai_codes_raw = _clean_text(row.get("上海指标码"))
        for sc in shanghai_codes_raw.split("、"):
            sc = sc.strip()
            if sc and sc not in by_shanghai:
                by_shanghai[sc] = row

    rows = []
    for _, lab_row in lab.iterrows():
        code = _clean_text(lab_row.get("raw_code"))
        match = by_short.get(code)
        status = "hit_by_short"
        if match is None:
            match = by_shanghai.get(code)
            status = "hit_by_shanghai" if match is not None else "unmatched"

        record = dict(lab_row)
        if match is None:
            record.update(
                match_status="unmatched",
                indicator_short_name=None,
                indicator_display_name=None,
                risk_category=None,
                display_order=None,
            )
        else:
            record.update(
                match_status=status,
                indicator_short_name=_clean_text(match.get("指标简称")) or None,
                indicator_display_name=_clean_text(match.get("中文简称")) or None,
                risk_category=_clean_text(match.get("风险类别")) or None,
                display_order=match.get("排序"),
            )
        rows.append(record)

    return pd.DataFrame(rows)
