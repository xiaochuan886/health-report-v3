from __future__ import annotations

import pandas as pd


SUMMARY_CATEGORIES = {
    "癌筛": "癌症健康监测小结",
    "心筛": "心脑血管健康监测小结",
}

NUTRITION_CATEGORIES = {
    "微量元素": "微量元素检测结果",
    "维生素": "维生素检测结果",
}

SUMMARY_EXCLUDED_STATUSES = {"normal", "正常"}
SUMMARY_EXCLUDED_REFERENCES = {"/", ""}


def _clean_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _filter_rows(
    matched: pd.DataFrame,
    categories: set[str],
    *,
    exclude_statuses: set[str] | None = None,
    exclude_no_reference: bool = False,
) -> pd.DataFrame:
    if matched.empty:
        return matched.iloc[0:0].copy()

    category_series = matched.get("risk_category", pd.Series(index=matched.index, dtype="object")).map(_clean_text)
    mask = category_series.isin(categories)

    if exclude_statuses is not None:
        status_series = matched.get("risk_status", pd.Series(index=matched.index, dtype="object")).map(_clean_text)
        mask &= ~status_series.isin(exclude_statuses)

    if exclude_no_reference:
        ref_series = matched.get("raw_reference", pd.Series(index=matched.index, dtype="object")).map(_clean_text)
        mask &= ~ref_series.isin(SUMMARY_EXCLUDED_REFERENCES)

    return matched.loc[mask].copy()


def _sort_section_rows(section: pd.DataFrame) -> pd.DataFrame:
    if section.empty or "display_order" not in section.columns:
        return section
    return section.sort_values(by="display_order", kind="mergesort", na_position="last")


def _flatten_cancer_rows(section: pd.DataFrame) -> list[dict]:
    if section.empty:
        return []

    ordered = _sort_section_rows(section)
    if "indicator_short_name" not in ordered.columns:
        return ordered.to_dict("records")

    disease_map: dict[str, list[dict[str, str]]] = {}
    for _, row in ordered.iterrows():
        short_name = _clean_text(row.get("indicator_short_name"))
        disease = _clean_text(row.get("disease_type"))
        ind_type = _clean_text(row.get("indicator_type"))
        if not short_name:
            continue
        disease_map.setdefault(short_name, []).append(
            {"disease_type": disease, "indicator_type": ind_type}
        )

    seen: set[str] = set()
    flat: list[dict] = []
    for _, row in ordered.iterrows():
        short_name = _clean_text(row.get("indicator_short_name"))
        if not short_name or short_name in seen:
            continue
        seen.add(short_name)

        record = dict(row)
        entries = disease_map.get(short_name, [])
        by_type: dict[str, list[str]] = {}
        for entry in entries:
            t = entry["indicator_type"] or "其他"
            d = entry["disease_type"] or ""
            if d:
                by_type.setdefault(t, []).append(d)

        parts = [f"{t}: {'、'.join(ds)}" for t, ds in by_type.items()]
        record["related_diseases"] = "；".join(parts) if parts else "--"
        flat.append(record)

    return flat


def build_summary_sections(matched: pd.DataFrame) -> dict[str, list[dict]]:
    summary_rows = _filter_rows(matched, set(SUMMARY_CATEGORIES), exclude_statuses=SUMMARY_EXCLUDED_STATUSES, exclude_no_reference=True)

    summary: dict[str, list[dict]] = {}
    for category, section_name in SUMMARY_CATEGORIES.items():
        section_rows = summary_rows.loc[summary_rows["risk_category"].map(_clean_text) == category].copy()
        if category == "癌筛":
            summary[section_name] = _flatten_cancer_rows(section_rows)
        else:
            summary[section_name] = _sort_section_rows(section_rows).to_dict("records")
    return summary


def build_nutrition_sections(matched: pd.DataFrame) -> dict[str, list[dict]]:
    nutrition_rows = _filter_rows(matched, set(NUTRITION_CATEGORIES))
    hit_rows = nutrition_rows.loc[nutrition_rows.get("match_status", pd.Series(index=nutrition_rows.index, dtype="object")).map(_clean_text) != "unmatched"].copy()

    nutrition: dict[str, list[dict]] = {}
    for category, section_name in NUTRITION_CATEGORIES.items():
        section_rows = hit_rows.loc[hit_rows["risk_category"].map(_clean_text) == category].copy()
        nutrition[section_name] = _sort_section_rows(section_rows).to_dict("records")
    return nutrition


def build_cancer_interpretations(enriched: pd.DataFrame, cancer_explanations: list[dict]) -> list[dict]:
    if enriched.empty:
        return []

    cancer_rows = _filter_rows(enriched, {"癌筛"})
    cancer_rows = cancer_rows.loc[cancer_rows.get("match_status", pd.Series(index=cancer_rows.index, dtype="object")).map(_clean_text) != "unmatched"]

    explanations_map: dict[str, dict] = {}
    for exp in cancer_explanations:
        key = _clean_text(exp.get("disease_type"))
        if key:
            explanations_map[key] = exp

    disease_groups: dict[str, list[dict]] = {}
    for _, row in cancer_rows.iterrows():
        disease = _clean_text(row.get("disease_type"))
        if not disease:
            continue
        disease_groups.setdefault(disease, []).append(dict(row))

    result = []
    for disease, rows in disease_groups.items():
        ordered = sorted(
            rows,
            key=lambda r: r.get("display_order") if r.get("display_order") is not None else 999,
        )
        exp = explanations_map.get(disease, {})

        by_type: dict[str, list[str]] = {}
        for row in ordered:
            ind_type = _clean_text(row.get("indicator_type"))
            short_name = _clean_text(row.get("indicator_short_name"))
            risk_status = _clean_text(row.get("risk_status"))
            
            display_name = short_name
            if risk_status not in {"normal", "正常", ""}:
                if risk_status in {"above", "过量", "中毒"}:
                    display_name = f"[RED]{short_name} ↑[/RED]"
                elif risk_status in {"below", "严重缺乏", "缺乏", "不足"}:
                    display_name = f"[RED]{short_name} ↓[/RED]"
                else:
                    display_name = f"[ORANGE]{short_name} ！[/ORANGE]"

            if ind_type and short_name:
                by_type.setdefault(ind_type, []).append(display_name)

        # 特异性在前，辅助判断在后，换行分隔
        type_order = [("特异性", "特异性"), ("辅助", "辅助判断")]
        judgment_lines = []
        for type_key, type_label in type_order:
            if type_key in by_type:
                judgment_lines.append(f"{type_label}: {'、'.join(by_type[type_key])}")

        judgment_text = "\n".join(judgment_lines) if judgment_lines else "--"
        result.append({
            "disease_type": disease,
            "judgment_indicators": judgment_text,
            "risk_warning": "--",
            "common_causes": _clean_text(exp.get("common_causes")) or "--",
            "prevention_advice": _clean_text(exp.get("prevention_advice")) or "--",
        })

    return result


def build_cardio_interpretations(
    enriched: pd.DataFrame, cardio_explanations: list[dict]
) -> list[dict]:
    """Build cardiovascular disease interpretations from enriched data and explanations.

    cardio_explanations comes from 癌症说明 sheet where disease_type='心脑血管'.
    """
    if enriched.empty:
        return []

    explanations_map: dict[str, dict] = {}
    for exp in cardio_explanations:
        key = _clean_text(exp.get("disease_type"))
        if key:
            explanations_map[key] = exp

    cardio_rows = enriched[enriched["risk_category"] == "心筛"]
    cardio_rows = cardio_rows[cardio_rows["match_status"].map(_clean_text) != "unmatched"]

    # Build risk warnings from abnormal/near_upper/near_lower indicators
    risk_warnings: list[str] = []
    for _, row in cardio_rows.iterrows():
        status = _clean_text(row.get("risk_status"))
        if status in {"above", "below", "near_upper", "near_lower"}:
            name = _clean_text(row.get("indicator_short_name"))
            if status in {"above", "过量", "中毒"}:
                risk_warnings.append(f"[RED]{name} ↑[/RED]")
            elif status in {"below", "严重缺乏", "缺乏", "不足"}:
                risk_warnings.append(f"[RED]{name} ↓[/RED]")
            else:
                risk_warnings.append(f"[ORANGE]{name} ！[/ORANGE]")

    exp = explanations_map.get("心脑血管", {})
    return [{
        "disease_type": "心脑血管",
        "risk_warning": "异常指标: " + "、".join(risk_warnings) if risk_warnings else "--",
        "common_causes": _clean_text(exp.get("common_causes")) or "--",
        "prevention_advice": _clean_text(exp.get("prevention_advice")) or "--",
    }]
