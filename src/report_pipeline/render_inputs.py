from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _first_record(records: list[dict]) -> dict:
    return records[0] if records else {}


def _clean(value: Any, default: str = "--") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def load_render_bundle(input_dir: str | Path) -> dict[str, Any]:
    base = Path(input_dir)
    cancer_interp_path = base / "cancer_interpretations.json"
    cardio_interp_path = base / "cardio_interpretations.json"
    personal_info_path = base / "personal_info.json"
    quality_control_path = base / "quality_control.json"
    report_config_path = base / "report_config.json"
    return {
        "input_dir": str(base),
        "matched_rows": _read_json(base / "matched_indicators.json"),
        "summary_sections": _read_json(base / "summary_sections.json"),
        "nutrition_sections": _read_json(base / "nutrition_sections.json"),
        "cancer_interpretations": _read_json(cancer_interp_path) if cancer_interp_path.exists() else [],
        "cardio_interpretations": _read_json(cardio_interp_path) if cardio_interp_path.exists() else [],
        "personal_info": _read_json(personal_info_path) if personal_info_path.exists() else {},
        "quality_control": _read_json(quality_control_path) if quality_control_path.exists() else {},
        "report_config": _read_json(report_config_path) if report_config_path.exists() else {},
    }


def build_render_context(bundle: dict[str, Any]) -> dict[str, Any]:
    matched_rows = bundle["matched_rows"]
    summary_sections = bundle["summary_sections"]
    nutrition_sections = bundle["nutrition_sections"]
    cancer_interpretations = bundle.get("cancer_interpretations", [])
    first = _first_record(matched_rows)

    cancer_summary_rows = summary_sections.get("癌症健康监测小结", [])
    # Part 2 needs ALL matched cancer indicators (not filtered by abnormal status)
    # matched_rows has exploded disease types, deduplicate by (raw_code, indicator_short_name)
    seen_cancer: set[tuple[str, str]] = set()
    cancer_all_rows = []
    for row in matched_rows:
        if row.get("risk_category") == "癌筛" and row.get("match_status") != "unmatched":
            key = (row.get("indicator_short_name", ""), row.get("raw_code", ""))
            if key[0] and key not in seen_cancer:
                seen_cancer.add(key)
                cancer_all_rows.append(row)
    cardio_rows = summary_sections.get("心脑血管健康监测小结", [])
    # Part 3 needs ALL matched cardio indicators (not filtered by abnormal status)
    seen_cardio: set[tuple[str, str]] = set()
    cardio_all_rows = []
    for row in matched_rows:
        if row.get("risk_category") == "心筛" and row.get("match_status") != "unmatched":
            key = (row.get("indicator_short_name", ""), row.get("raw_code", ""))
            if key[0] and key not in seen_cardio:
                seen_cardio.add(key)
                cardio_all_rows.append(row)
    cardio_all_rows.sort(key=lambda r: r.get("display_order") or 999)

    glossary_map: dict[str, dict[str, str]] = {}
    glossary_source_rows = list(cancer_all_rows)
    glossary_source_rows.extend(cardio_all_rows)

    for row in glossary_source_rows:
        short_name = _clean(row.get("indicator_short_name"), default="")
        if not short_name or short_name in glossary_map:
            continue
        label = _clean(row.get("indicator_label"))
        # Skip if indicator_label is "--" (no interpretation data available)
        if label == "--":
            continue
        glossary_map[short_name] = {
            "indicator_short_name": short_name,
            "indicator_label": label,
            "indicator_meaning": _clean(row.get("indicator_meaning")),
            "indicator_application": _clean(row.get("indicator_application")),
        }

    cardio_interpretations = bundle.get("cardio_interpretations", [])
    personal_info = bundle.get("personal_info", {})

    # 一般普通检查
    general_check = {
        "身高": personal_info.get("身高"),
        "体重": personal_info.get("体重"),
        "腹围": personal_info.get("腹围"),
        "收缩压": personal_info.get("收缩压"),
        "舒张压": personal_info.get("舒张压"),
        "脉搏": personal_info.get("脉搏"),
        "BMI": personal_info.get("BMI"),
        "腰高比": personal_info.get("腰高比"),
    }

    # 大营养板块小结 - 筛选异常的微量元素和维生素指标
    abnormal_nutrition: list[dict] = []
    for row in nutrition_sections.get("微量元素检测结果", []):
        risk_status = _clean(row.get("risk_status"))
        if risk_status and risk_status not in {"normal", "正常", ""}:
            abnormal_nutrition.append({**row, "category": "微量元素"})
    for row in nutrition_sections.get("维生素检测结果", []):
        risk_status = _clean(row.get("risk_status"))
        if risk_status and risk_status not in {"normal", "正常", ""}:
            abnormal_nutrition.append({**row, "category": "维生素"})

    # Resolve health guide path: always use canonical source under src/data/
    shared_guide = Path(__file__).parent / "data" / "health_guide.md"
    final_guide_path = str(shared_guide)

    report_config = bundle.get("report_config", {})
    quality_control = bundle.get("quality_control", {})

    return {
        "title": "综合健康检测报告",
        "patient_name": _clean(first.get("病人姓名")),
        "patient_gender": _clean(first.get("病人性别")),
        "patient_age": _clean(first.get("病人年龄")),
        "specimen_type": _clean(first.get("specimen_type")),
        "received_at": _clean(first.get("received_at")),
        "reported_at": _clean(first.get("reported_at")),
        "hospital_name": _clean(first.get("送检医院")),
        "institution_name": report_config.get("机构名称", ""),
        "report_date": quality_control.get("report_date", ""),
        "summary_sections": summary_sections,
        "cancer_summary_rows": cancer_summary_rows,
        "cancer_all_rows": cancer_all_rows,
        "cardio_rows": cardio_rows,
        "cardio_all_rows": cardio_all_rows,
        "cancer_interpretations": cancer_interpretations,
        "cardio_interpretations": cardio_interpretations,
        "nutrition_sections": nutrition_sections,
        "nutrition_explanations": {
            "微量元素检测结果": [
                row
                for row in nutrition_sections.get("微量元素检测结果", [])
                if _clean(row.get("indicator_meaning")) != "--" or _clean(row.get("indicator_application")) != "--"
            ],
            "维生素检测结果": [
                row
                for row in nutrition_sections.get("维生素检测结果", [])
                if _clean(row.get("indicator_meaning")) != "--" or _clean(row.get("indicator_application")) != "--"
            ],
        },
        "general_check": general_check,
        "nutrition_summary": abnormal_nutrition,
        "quality_control": quality_control,
        "glossary_rows": list(glossary_map.values()),
        "health_guide_path": final_guide_path,
    }
