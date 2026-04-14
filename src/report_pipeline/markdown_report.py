from __future__ import annotations

from pathlib import Path

from report_pipeline.report_styles import (
    format_display,
    get_status_arrow,
    get_status_color,
    get_status_summary_text,
    indicator_display_name,
    nutrition_indicator_display,
    risk_bar,
    status_label,
)

def _risk_bar_cell(row: dict) -> str:
    """Return a risk bar cell with encoded data for PDF rendering."""
    raw_result = format_display(row.get("raw_result"))
    raw_reference = format_display(row.get("raw_reference"))
    risk_status = format_display(row.get("risk_status"))
    # Unicode bar for markdown viewers; PDF extracts data-riskbar for RiskBarFlowable
    text_bar = risk_bar(risk_status)
    return f'<span data-riskbar="{raw_result};;{raw_reference};;{risk_status}">{text_bar}</span>'


def _result_badge_cell(row: dict, show_pill: bool = True) -> str:
    """Return a result badge cell with encoded data for PDF rendering.
    Encoding: result;;arrow;;summary_text;;color;;show_pill
    """
    result = format_display(row.get("raw_result"))
    status = format_display(row.get("risk_status"))
    arrow = get_status_arrow(status)
    summary_text = get_status_summary_text(status)
    color = get_status_color(status)
    pill_val = "1" if show_pill else "0"
    
    # Use ';;' as separator
    return f'<span data-badge="{result};;{arrow};;{summary_text};;{color};;{pill_val}">{result}</span>'


def _cell(value: str) -> str:
    return format_display(value).replace("|", "\\|").replace("\r", "").replace("\n", "<br/>")


def _nutrition_item_cell(row: dict) -> str:
    """Return indicator name colored and formatted according to its risk status."""
    from report_pipeline.report_styles import indicator_display_name
    name = indicator_display_name(row)
    
    if format_display(row.get("raw_reference")) in {"--", "/"}:
        return name

    status = format_display(row.get("risk_status"))
    if status in {"above", "过量", "中毒"}:
        return f"[RED]{name} ↑[/RED]"
    elif status in {"below", "严重缺乏", "缺乏", "不足"}:
        return f"[RED]{name} ↓[/RED]"
    elif status in {"near_upper", "near_lower"}:
        return f"[ORANGE]{name} ！[/ORANGE]"
    elif status not in {"normal", "正常", "unknown", "暂无法判断", "--", ""}:
        return f"[ORANGE]{name} ！[/ORANGE]"
    return name


def _excerpt(value: str, limit: int = 140) -> str:
    text = format_display(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_cell(value) for value in row) + " |")
    return "\n".join(lines)


_STAMP_MARKER = "STAMP_合格"


def _badge_cell(context: dict, qc_key: str) -> str:
    """Return badge image markdown if value is '合格', otherwise the value."""
    qc = context.get("quality_control", {})
    if qc.get(qc_key) == "合格":
        badge_path = context.get("badge_image_path", "")
        if badge_path:
            return f"![]({badge_path})"
        return _STAMP_MARKER
    return qc.get(qc_key, "--")


def generate_markdown_report(context: dict) -> str:
    lines: list[str] = []


    # 基础信息与质控校验表（合并）
    qc = context.get("quality_control", {})
    qc_rows = [
        ["姓名", context["patient_name"]],
        ["性别", context["patient_gender"]],
        ["年龄", context["patient_age"]],
        ["采样日期", qc.get("sampling_date", "--")],
        ["收样日期", qc.get("receive_date", "--")],
        ["报告日期", qc.get("report_date", "--")],
        ["样本编号", qc.get("sample_id", "--")],
        ["样本类型", qc.get("sample_type", "--")],
        ["样本量", qc.get("sample_amount", "--")],
        ["样本状态", _badge_cell(context, "sample_status")],
        ["温度控制", _badge_cell(context, "temperature_control")],
        ["监测数据质控", _badge_cell(context, "data_quality_control")],
        ["送检单位", qc.get("sending_unit", "--")],
        ["监测机构", qc.get("inspection_org", "--")],
        ["检测机构地址", qc.get("address", "--")],
        ["检测项目", qc.get("test_item", "--")],
        ["检验人", qc.get("inspectors", "--")],
        ["审核人", qc.get("reviewers", "--")],
    ]
    lines.extend([
        "## 基础信息与质控校验表",
        "",
        _table(["项目", "内容"], qc_rows),
        "",
    ])

    lines.extend([
        "## 第一部分 评估结果小结",
        "",
        "### 癌症健康监测小结",
        "",
    ])

    cancer_summary_rows = context["summary_sections"].get("癌症健康监测小结", [])
    lines.extend(
        [
            _table(
                ["指标", "结果/状态", "单位", "参考值", "关联疾病风险"],
                [
                    [
                        indicator_display_name(row),
                        _result_badge_cell(row),
                        format_display(row.get("unit")),
                        format_display(row.get("raw_reference")),
                        format_display(row.get("related_diseases")),
                    ]
                    for row in cancer_summary_rows
                    if format_display(row.get("raw_reference")) not in {"--", "/"}
                ]
                or [["--", "--", "--", "--", "--"]],
            ),
            "",
        ]
    )

    lines.extend(
        [
            "### 心脑血管健康监测小结",
            "",
            _table(
                ["指标", "结果/状态", "单位", "参考值"],
                [
                    [
                        indicator_display_name(row),
                        _result_badge_cell(row),
                        format_display(row.get("unit")),
                        format_display(row.get("raw_reference")),
                    ]
                    for row in context["summary_sections"].get("心脑血管健康监测小结", [])
                    if format_display(row.get("raw_reference")) not in {"--", "/"}
                ]
                or [["--", "--", "--", "--"]],
            ),
            "",
        ]
    )

    # 大营养板块小结
    nutrition_summary = context.get("nutrition_summary", [])
    if nutrition_summary:
        nutrition_summary_rows = [
            [
                indicator_display_name(row),
                _result_badge_cell(row),
                format_display(row.get("unit")),
                format_display(row.get("raw_reference")),
            ]
            for row in nutrition_summary
            if format_display(row.get("raw_reference")) not in {"--", "/"}
        ]
        if not nutrition_summary_rows:
            nutrition_summary_rows = [["--", "--", "--", "--"]]
    else:
        nutrition_summary_rows = [["--", "--", "--", "--"]]
    lines.extend([
        "### 大营养板块小结",
        "",
        _table(["指标", "结果/状态", "单位", "参考值"], nutrition_summary_rows),
        "",
    ])

    # 一般普通检查
    general_check = context.get("general_check", {})
    general_check_rows = [
        ["身高（cm）", general_check.get("身高", "--")],
        ["体重（kg）", general_check.get("体重", "--")],
        ["腹围（cm）", general_check.get("腹围", "--")],
        ["收缩压", general_check.get("收缩压", "--")],
        ["舒张压", general_check.get("舒张压", "--")],
        ["脉搏", general_check.get("脉搏", "--")],
        ["体重指数", general_check.get("BMI", "--")],
        ["腰高比", general_check.get("腰高比", "--")],
    ]
    lines.extend([
        "### 一般普通检查",
        "",
        _table(["项目", "检查结果"], general_check_rows),
        "",
        "",
        "体重指数BMI：通常反映全身肥胖程度；我国成人体重指数BMI的正常者应该注意保持在正常范围（18.5 kg/m² ≤ BMI < 24 kg/m²）。超重和肥胖者应该尽量减小体重、争取达到正常范围，并减少高血压、血脂异常、糖尿病等其他危险因素，综合降低心血管病风险。",
        "",
        "体脂储藏在腹部（腹内脂肪）比皮下脂肪带来更高的心血管病风险，测量腰围是反映腹部脂肪堆积的简便方法。我国成人腰围的分类：正常范围男性 < 85 cm，女性 < 80 cm。当腰围 85 cm ≤ 男性 < 90 cm、80 cm ≤ 女性 < 85 cm定义为中心性肥胖前期。当腰围男性 ≥ 90 cm、女性 ≥ 85 cm定义为中心性肥胖。",
        "",
        "腰高比：正常范围在0.5以下。超过正常值的说明已经有\u201c大肚腩\u201d了，腰高比数字越高说明\u201c肚腩\u201d越大，是腹型肥胖的标志。2023年8月，美国华盛顿大学的研究人员在 Aging and Disease 上发表的一篇论文发现，腰高比越大，脑子萎缩越快，罹患痴呆风险更高。",
        "",
        "2010年美国心脏协会（AHA）提出了7项评估心血管健康（Cardiovascular Health, CVH）的重要指标，包括4种健康行为（吸烟、体重指数、体力活动、膳食）和3种生理生化因素（血压、总胆固醇、空腹血糖）指标。如果达到7种理想心血管健康（CVH）指标，能够减少62.1%的动脉粥样硬化性心血管疾病 (ASCVD)发病（包括减少38.7%的冠心病发病、减少66.4%的脑卒中发病）和60.5%的ASCVD死亡。这7项CVH指标中，保持理想血压（收缩压/舒张压 < 120/80 mmHg）带来的心血管健康获益最大：可以避免33.0% - 47.2%的动脉粥样硬化性心血管疾病ASCVD发病。但我国人群满足4项及以上健康膳食标准的比例仅为4.2%。因此强调保持理想血压、健康膳食等心血管健康指标的目的是让心血管疾病防治关口前移，更大幅度降低心脑血管疾病的发生，拥有健康美好生活！",
        "",
    ])

    lines.extend([
        "## 第二部分 癌症健康监测与指导",
            "",
            "### 评估结果检测",
            "",
            _table(
                ["指标", "结果", "单位", "参考值", "风险刻度"],
                [
                    [
                        indicator_display_name(row),
                        _result_badge_cell(row, show_pill=False),
                        format_display(row.get("unit")),
                        format_display(row.get("raw_reference")),
                        _risk_bar_cell(row),
                    ]
                    for row in context["cancer_all_rows"]
                ]
                or [["--", "--", "--", "--", "--"]],
            ),
            "",
            "### 肿瘤健康监测释义",
            "",
            _table(
                ["疾病类型 / 判断指标", "常见诱发因素", "防癌管理建议"],
                [
                    [
                        f"[TITLE]{format_display(row.get('disease_type'))}[/TITLE]<br/><br/>{format_display(row.get('judgment_indicators'))}",
                        format_display(row.get("common_causes")),
                        format_display(row.get("prevention_advice")),
                    ]
                    for row in context.get("cancer_interpretations", [])
                ]
                or [["--", "--", "--"]],
            ),
            "",
            "## 第三部分 心脑血管健康监测与指导",
            "",
            "### 评估结果检测",
            "",
            _table(
                ["指标", "结果", "单位", "参考值", "风险刻度"],
                [
                    [
                        indicator_display_name(row),
                        _result_badge_cell(row, show_pill=False),
                        format_display(row.get("unit")),
                        format_display(row.get("raw_reference")),
                        _risk_bar_cell(row),
                    ]
                    for row in context["cardio_all_rows"]
                ]
                or [["--", "--", "--", "--", "--"]],
            ),
            "",
            "### 心脑血管健康释义",
            "",
            _table(
                ["疾病类型 / 风险预警", "常见诱因/因素", "健康管理建议"],
                [
                    [
                        f"[TITLE]{format_display(row.get('disease_type'))}[/TITLE]<br/><br/>{format_display(row.get('risk_warning'))}",
                        format_display(row.get("common_causes")),
                        format_display(row.get("prevention_advice")),
                    ]
                    for row in context.get("cardio_interpretations", [])
                ]
                or [["--", "--", "--"]],
            ),
            "",
            "## 第四部分 大营养检测与建议",
            "",
            "### 4-1 评估结果检测",
            "",
        ]
    )

    for section_name in ["微量元素检测结果", "维生素检测结果"]:
        lines.extend(
            [
                f"**{section_name}**",
                "",
                _table(
                    ["指标", "结果", "单位", "参考值", "风险刻度"],
                    [
                        [
                            indicator_display_name(row),
                            _result_badge_cell(row, show_pill=False),
                            format_display(row.get("unit")),
                            format_display(row.get("raw_reference")),
                            _risk_bar_cell(row),
                        ]
                        for row in context["nutrition_sections"].get(section_name, [])
                    ]
                    or [["--", "--", "--", "--", "--"]],
                ),
                "",
            ]
        )

    lines.extend(["### 4-2 结果解读与建议", ""])
    for section_name in ["微量元素检测结果", "维生素检测结果"]:
        lines.append(f"**{section_name}**")
        lines.append("")
        explain_rows = context["nutrition_explanations"].get(section_name, [])
        lines.append(
            _table(
                ["项目", "临床表现 / 具体意义", "饮食补充 / 临床应用"],
                [
                        [
                            _nutrition_item_cell(row),
                            _excerpt(row.get("indicator_meaning")),
                            _excerpt(row.get("indicator_application")),
                        ]
                    for row in explain_rows
                ]
                or [["--", "本次未命中相关指标", "--"]],
            )
        )
        lines.append("")

    lines.extend(
        [
            "## 医学名词释义",
            "",
            "### 医学名词释义",
            "",
            _table(
                ["项目", "具体意义", "临床应用"],
                [
                    [
                        format_display(row.get("indicator_label")),
                        _excerpt(row.get("indicator_meaning")),
                        _excerpt(row.get("indicator_application")),
                    ]
                    for row in context["glossary_rows"]
                ]
                or [["--", "本次无可展示释义", "--"]],
            ),
            "",
        ]
    )

    # Append health guide from external file
    health_guide_path = context.get("health_guide_path")
    if health_guide_path and Path(health_guide_path).exists():
        health_guide_content = Path(health_guide_path).read_text(encoding="utf-8")
        lines.append(health_guide_content)
    else:
        lines.append("> [!WARNING]\n> 健康生活指南内容缺失")

    lines.append("")
    return "\n".join(lines)
