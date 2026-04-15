from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pandas as pd

from report_pipeline.reference_parser import parse_reference
from report_pipeline.risk import evaluate_risk
from report_pipeline.sections import build_cancer_interpretations, build_cardio_interpretations, build_nutrition_sections, build_summary_sections
from report_pipeline.sources import normalize_lab_dataframe
from report_pipeline.whitelist import match_indicators


def _clean_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _load_personal_basic_info(xlsx_path: str) -> dict[str, Any]:
    """从客户基本信息xlsx读取基础体检数据并计算BMI和腰高比"""
    if not xlsx_path or not Path(xlsx_path).exists():
        return {}

    try:
        df = pd.read_excel(xlsx_path)
        if df.empty:
            return {}

        result: dict[str, Any] = {}

        # 字段映射
        FIELD_MAP = {
            "身高": ["身高", "身高(cm)"],
            "体重": ["体重", "体重(kg)"],
            "腹围": ["腹围", "腰围", "腹围(cm)", "腰围(CM)"],
            "收缩压": ["收缩压", "血压(收缩压)"],
            "舒张压": ["舒张压", "血压(舒张压)"],
            "脉搏": ["脉搏", "脉搏(次/分)"],
        }

        for field, candidates in FIELD_MAP.items():
            for col in candidates:
                if col in df.columns:
                    val = df[col].iloc[0] if not df[col].empty else None
                    if pd.notna(val):
                        # Handle numpy types (numpy.int64, numpy.float64, etc.)
                        if hasattr(val, "item"):
                            try:
                                val = val.item()
                            except Exception:
                                pass
                        if isinstance(val, (int, float)):
                            result[field] = val
                        else:
                            result[field] = str(val)
                        break

        # 计算 BMI = 体重(kg) / 身高(m)^2
        if "身高" in result and "体重" in result:
            height_m = result["身高"] / 100
            if height_m > 0:
                result["BMI"] = round(result["体重"] / (height_m ** 2), 2)

        # 计算 腰高比 = 腹围 / 身高
        if "身高" in result and "腹围" in result and result["身高"] > 0:
            result["腰高比"] = round(result["腹围"] / result["身高"], 2)

        return result
    except Exception:
        return {}


def _build_quality_control(raw_lab: pd.DataFrame, matched: pd.DataFrame) -> dict[str, Any]:
    """构建质控校验表数据"""
    first_row = raw_lab.iloc[0]

    # 获取条码
    barcode = _clean_text(first_row.get("艾迪康条码", ""))
    sample_id = barcode if barcode else _clean_text(first_row.get("医院条码", ""))

    # 根据条码决定送检单位和检测机构
    if barcode.startswith("1Z1127"):
        sending_unit = "山丘生物（杭州）有限公司"
        inspection_org = "杭州艾迪康医学检验中心"
        address = "浙江省杭州市西湖区三墩镇振中路208号"
    elif barcode.startswith("#630805"):
        sending_unit = "山丘可见（上海）生物科技有限公司"
        inspection_org = "上海锦测医学检验所"
        address = "上海市中春路1288号8号楼"
    else:
        sending_unit = _clean_text(first_row.get("送检医院", ""))
        inspection_org = "杭州艾迪康医学检验中心"
        address = "浙江省杭州市西湖区三墩镇振中路208号"

    # 提取检验人和审核人（去重）
    inspectors = []
    reviewers = []
    seen_inspectors = set()
    seen_reviewers = set()

    for _, row in matched.iterrows():
        inspector = _clean_text(row.get("检验医生", ""))
        reviewer = _clean_text(row.get("审核医生", ""))
        if inspector and inspector not in seen_inspectors:
            seen_inspectors.add(inspector)
            inspectors.append(inspector)
        if reviewer and reviewer not in seen_reviewers:
            seen_reviewers.add(reviewer)
            reviewers.append(reviewer)

    # 格式化日期
    def _format_date(val):
        if pd.isna(val):
            return ""
        if isinstance(val, pd.Timestamp):
            return val.strftime("%Y年%m月%d日")
        if isinstance(val, str) and val:
            try:
                return pd.Timestamp(val).strftime("%Y年%m月%d日")
            except Exception:
                return val
        return ""

    sampling_date = _format_date(first_row.get("采集时间"))  # 采样日期
    receive_date = _format_date(first_row.get("接收时间"))  # 收样日期
    report_date = _format_date(first_row.get("报告日期"))  # 报告日期

    return {
        "sampling_date": sampling_date,
        "receive_date": receive_date,
        "report_date": report_date,
        "sample_id": sample_id,
        "sample_type": "静脉血",  # 固定值
        "sample_amount": "17 ML",  # 固定值
        "sample_status": "合格",  # 固定值
        "temperature_control": "合格",  # 固定值
        "data_quality_control": "合格",  # 固定值
        "sending_unit": sending_unit,
        "inspection_org": inspection_org,
        "address": address,
        "test_item": "综合健康评估",  # 固定值
        "inspectors": "；".join(inspectors) if inspectors else "--",
        "reviewers": "；".join(reviewers) if reviewers else "--",
    }


def _first_non_empty(series: pd.Series) -> str:
    for value in series:
        text = _clean_text(value)
        if text:
            return text
    return ""


def _patient_gender(raw_lab: pd.DataFrame) -> str:
    for column in ("病人性别", "性别"):
        if column in raw_lab.columns:
            return _first_non_empty(raw_lab[column])
    return ""


def _to_float(value: Any) -> float | None:
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    for op in ("<=", ">=", "<", ">", "≤", "≥", "＜", "＞"):
        if text.startswith(op):
            text = text[len(op):].strip()
            break
    try:
        return float(text)
    except ValueError:
        return None


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _risk_fields(raw_result: Any, raw_reference: Any) -> dict[str, Any]:
    parsed_reference = parse_reference(_clean_text(raw_reference))
    numeric_value = _to_float(raw_result)

    if numeric_value is not None and parsed_reference["kind"] in {"range", "upper_bound", "lower_bound", "multi_rule"}:
        risk = evaluate_risk(numeric_value, parsed_reference)
    elif parsed_reference["kind"] == "qual_only":
        risk = evaluate_risk(_clean_text(raw_result), parsed_reference)
    else:
        risk = {"risk_status": "unknown", "is_abnormal": False}

    return {
        "parsed_reference": parsed_reference,
        "reference_kind": parsed_reference["kind"],
        "risk_status": risk["risk_status"],
        "is_abnormal": risk["is_abnormal"],
    }


def _join_indicator_descriptions(matched: pd.DataFrame, descriptions: pd.DataFrame) -> pd.DataFrame:
    if descriptions.empty:
        out = matched.copy()
        for column in ("indicator_label", "indicator_meaning", "indicator_application"):
            if column not in out.columns:
                out[column] = None
        return out

    description_rows = descriptions.copy()
    description_rows["indicator_short_name"] = description_rows.get("指标简称", pd.Series(dtype="object")).map(_clean_text)
    description_rows["indicator_label"] = description_rows.get("指标", pd.Series(dtype="object")).map(_clean_text)
    description_rows["indicator_meaning"] = description_rows.get("具体意义", pd.Series(dtype="object")).map(_clean_text)
    description_rows["indicator_application"] = description_rows.get("临床应用", pd.Series(dtype="object")).map(_clean_text)
    selected = description_rows.loc[
        description_rows["indicator_short_name"] != "",
        ["indicator_short_name", "indicator_label", "indicator_meaning", "indicator_application"],
    ].drop_duplicates(subset=["indicator_short_name"], keep="first")
    return matched.merge(selected, how="left", on="indicator_short_name")


def _explode_disease_types(matched: pd.DataFrame, disease_map: pd.DataFrame) -> pd.DataFrame:
    if matched.empty:
        return matched.copy()

    disease_lookup: dict[str, list[dict[str, str]]] = {}
    for _, row in disease_map.iterrows():
        short_name = _clean_text(row.get("指标简称"))
        if not short_name:
            continue
        disease_lookup.setdefault(short_name, []).append(
            {
                "disease_type": _clean_text(row.get("疾病类型")),
                "indicator_type": _clean_text(row.get("指标类型")),
            }
        )

    rows: list[dict[str, Any]] = []
    for _, row in matched.iterrows():
        record = dict(row)
        mappings = disease_lookup.get(_clean_text(record.get("indicator_short_name")), [])
        if _clean_text(record.get("risk_category")) == "癌筛" and mappings:
            for mapping in mappings:
                expanded = dict(record)
                expanded.update(mapping)
                rows.append(expanded)
            continue

        record.setdefault("disease_type", None)
        record.setdefault("indicator_type", None)
        rows.append(record)

    return pd.DataFrame(rows)


def run_extract(lab_xls: str, standard_xlsx: str, output_dir: str, personal_info_xlsx: str | None = None) -> dict[str, Any]:
    raw_lab = pd.read_excel(lab_xls)
    normalized_lab = normalize_lab_dataframe(raw_lab)

    whitelist = pd.read_excel(standard_xlsx, sheet_name="指标明细")
    disease_map = pd.read_excel(standard_xlsx, sheet_name="指标对应风险部位")
    workbook = pd.ExcelFile(standard_xlsx)
    descriptions = (
        pd.read_excel(standard_xlsx, sheet_name="指标说明")
        if "指标说明" in workbook.sheet_names
        else pd.DataFrame(columns=["指标简称", "指标", "具体意义", "临床应用"])
    )
    cancer_explanations = (
        pd.read_excel(standard_xlsx, sheet_name="癌症说明")
        if "癌症说明" in workbook.sheet_names
        else pd.DataFrame(columns=["疾病类型", "性别", "常见诱发因素", "防癌管理建议"])
    )
    special_refs = (
        pd.read_excel(standard_xlsx, sheet_name="特殊指标参考值")
        if "特殊指标参考值" in workbook.sheet_names
        else pd.DataFrame(columns=["指标简称", "性别", "参考值", "说明"])
    )
    report_config_df = (
        pd.read_excel(standard_xlsx, sheet_name="报告配置")
        if "报告配置" in workbook.sheet_names
        else pd.DataFrame(columns=["配置项", "值"])
    )
    report_config = {
        _clean_text(row.get("配置项")): _clean_text(row.get("值"))
        for _, row in report_config_df.iterrows()
        if _clean_text(row.get("配置项"))
    }

    matched = match_indicators(normalized_lab, whitelist, patient_gender=_patient_gender(raw_lab))
    matched = _join_indicator_descriptions(matched, descriptions)
    matched = _explode_disease_types(matched, disease_map)

    # 特殊参考值覆盖（从标准文档读取）
    special_ref_map: dict[str, dict[str, str]] = {}
    for _, row in special_refs.iterrows():
        key = _clean_text(row.get("指标简称"))
        gender_val = _clean_text(row.get("性别", ""))
        ref_val = _clean_text(row.get("参考值"))
        if key and ref_val:
            special_ref_map.setdefault(key, {})[gender_val] = ref_val

    patient_gender = _patient_gender(raw_lab)
    for idx, row in matched.iterrows():
        short_name = _clean_text(row.get("indicator_short_name"))
        if short_name in special_ref_map:
            ref_dict = special_ref_map[short_name]
            # 优先匹配具体性别，其次通用 F/M
            override = ref_dict.get(patient_gender) or ref_dict.get("F/M") or ref_dict.get("")
            if override:
                matched.at[idx, "raw_reference"] = override

    risk_frame = pd.DataFrame(
        [_risk_fields(row.get("raw_result"), row.get("raw_reference")) for _, row in matched.iterrows()]
    )
    enriched = pd.concat([matched.reset_index(drop=True), risk_frame], axis=1)

    # 计算 TC/HDL 比值
    tc_rows = enriched[enriched["indicator_short_name"] == "TC"]
    hdl_rows = enriched[enriched["indicator_short_name"] == "HDL-C"]
    if not tc_rows.empty and not hdl_rows.empty:
        tc_val = _to_float(tc_rows.iloc[0].get("raw_result"))
        hdl_val = _to_float(hdl_rows.iloc[0].get("raw_result"))
        if tc_val is not None and hdl_val is not None and hdl_val != 0:
            ratio = tc_val / hdl_val
            gender = _patient_gender(raw_lab)
            ref = "<4.5" if gender != "女" else "<3.5"
            ratio_risk = _risk_fields(f"{ratio:.2f}", ref)
            ratio_row = tc_rows.iloc[0].copy()
            ratio_row["indicator_short_name"] = "TC/HDL"
            ratio_row["indicator_display_name"] = "总胆固醇与高密度脂蛋白胆固醇的比值"
            ratio_row["indicator_label"] = "TC/HDL\n总胆固醇与高密度脂蛋白胆固醇的比值"
            ratio_row["raw_result"] = f"{ratio:.2f}"
            ratio_row["raw_reference"] = ref
            ratio_row["unit"] = ""
            ratio_row["parsed_reference"] = ratio_risk["parsed_reference"]
            ratio_row["reference_kind"] = ratio_risk["reference_kind"]
            ratio_row["risk_status"] = ratio_risk["risk_status"]
            ratio_row["is_abnormal"] = ratio_risk["is_abnormal"]
            enriched = pd.concat([enriched, ratio_row.to_frame().T], ignore_index=True)

    summary = build_summary_sections(enriched)
    nutrition = build_nutrition_sections(enriched)
    cancer_explanations_rows = _json_safe(_clean_cancer_explanations(cancer_explanations))
    cancer_interpretations = build_cancer_interpretations(enriched, cancer_explanations_rows)
    cardio_interpretations = build_cardio_interpretations(enriched, cancer_explanations_rows)
    personal_info = _load_personal_basic_info(personal_info_xlsx) if personal_info_xlsx else {}
    quality_control = _build_quality_control(raw_lab, matched)
    matched_rows = [_json_safe(record) for record in enriched.to_dict("records")]
    summary_rows = _json_safe(summary)
    nutrition_rows = _json_safe(nutrition)

    export_outputs(matched_rows, summary_rows, nutrition_rows, cancer_explanations_rows, _json_safe(cancer_interpretations), _json_safe(cardio_interpretations), personal_info, quality_control, report_config, output_dir)
    return {
        "matched_rows": matched_rows,
        "summary_sections": summary_rows,
        "nutrition_sections": nutrition_rows,
        "cancer_explanations": cancer_explanations_rows,
        "cancer_interpretations": cancer_interpretations,
        "cardio_interpretations": cardio_interpretations,
        "personal_info": personal_info,
        "quality_control": quality_control,
        "report_config": report_config,
    }


def _clean_cancer_explanations(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, row in df.iterrows():
        rows.append({
            "disease_type": _clean_text(row.get("疾病类型")),
            "gender": _clean_text(row.get("性别")),
            "common_causes": _clean_text(row.get("常见诱发因素")),
            "prevention_advice": _clean_text(row.get("防癌管理建议")),
        })
    return rows


def export_outputs(matched_rows, summary, nutrition, cancer_explanations, cancer_interpretations, cardio_interpretations, personal_info, quality_control, report_config, output_dir):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    (output_path / "matched_indicators.json").write_text(
        json.dumps(matched_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_path / "summary_sections.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_path / "nutrition_sections.json").write_text(
        json.dumps(nutrition, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_path / "cancer_explanations.json").write_text(
        json.dumps(cancer_explanations, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_path / "cancer_interpretations.json").write_text(
        json.dumps(cancer_interpretations, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_path / "cardio_interpretations.json").write_text(
        json.dumps(cardio_interpretations, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if personal_info:
        (output_path / "personal_info.json").write_text(
            json.dumps(personal_info, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if quality_control:
        (output_path / "quality_control.json").write_text(
            json.dumps(quality_control, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if report_config:
        (output_path / "report_config.json").write_text(
            json.dumps(report_config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # Copy fixed health guide files to output directory
    _copy_health_guide(output_path)


def _copy_health_guide(output_path: Path) -> None:
    """Copy the fixed health guide markdown and images to the output directory.

    Always overwrites so output stays in sync with the canonical source.
    """
    data_dir = Path(__file__).parent / "data"
    guide_src = data_dir / "health_guide.md"
    images_src = data_dir / "health_guide_images"

    if guide_src.exists():
        shutil.copy2(guide_src, output_path / "health_guide.md")
    if images_src.is_dir():
        dst = output_path / "health_guide_images"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(images_src, dst)
