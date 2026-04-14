import json
from pathlib import Path

import pandas as pd

from report_pipeline.cli import build_parser, main
from report_pipeline.pipeline import export_outputs, run_extract


def test_build_parser_exposes_extract_arguments():
    parser = build_parser()
    subparsers = [
        action
        for action in parser._actions
        if action.__class__.__name__ == "_SubParsersAction"
    ]

    assert len(subparsers) == 1
    extract = subparsers[0].choices["extract"]
    argument_dests = {action.dest for action in extract._actions}
    assert {"lab_xls", "standard_xlsx", "output_dir"} <= argument_dests
    render = subparsers[0].choices["render"]
    render_argument_dests = {action.dest for action in render._actions}
    assert {"input_dir", "markdown_output", "pdf_output"} <= render_argument_dests


def test_export_outputs_writes_expected_files(tmp_path: Path):
    export_outputs(
        matched_rows=[{"indicator_short_name": "VD", "risk_category": "维生素"}],
        summary={"癌症健康监测小结": [], "心脑血管健康监测小结": []},
        nutrition={"维生素检测结果": [{"indicator_short_name": "VD"}], "微量元素检测结果": []},
        cancer_explanations=[],
        cancer_interpretations=[],
        cardio_interpretations=[],
        personal_info={},
        quality_control={},
        output_dir=tmp_path,
    )

    matched = json.loads((tmp_path / "matched_indicators.json").read_text(encoding="utf-8"))
    summary = json.loads((tmp_path / "summary_sections.json").read_text(encoding="utf-8"))
    nutrition = json.loads((tmp_path / "nutrition_sections.json").read_text(encoding="utf-8"))

    assert matched == [{"indicator_short_name": "VD", "risk_category": "维生素"}]
    assert summary == {"癌症健康监测小结": [], "心脑血管健康监测小结": []}
    assert nutrition == {
        "维生素检测结果": [{"indicator_short_name": "VD"}],
        "微量元素检测结果": [],
    }


def test_run_extract_builds_expected_outputs(tmp_path: Path):
    lab_path = tmp_path / "lab.xlsx"
    standard_path = tmp_path / "standard.xlsx"
    output_dir = tmp_path / "output"

    pd.DataFrame(
        [
            {
                "病人性别": "男",
                "项目代号": "CEA",
                "项目名称": "癌胚抗原",
                "项目测定值": 4.5,
                "参考值": "0.00-5.00",
                "单位": "ng/mL",
            },
            {
                "病人性别": "男",
                "项目代号": "VD",
                "项目名称": "25-羟基维生素D",
                "项目测定值": 29.85,
                "参考值": "严重缺乏:≤10.00\n缺乏:10.01-20.00\n不足:20.01-30.00\n正常:30.01-80.00\n过量:>80.00\n中毒:>150.00",
                "单位": "ng/mL",
            },
        ]
    ).to_excel(lab_path, index=False)

    with pd.ExcelWriter(standard_path, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {
                    "指标简称": "CEA",
                    "上海指标码": "CEA-X",
                    "中文简称": "癌胚抗原",
                    "性别": "F/M",
                    "风险类别": "癌筛",
                    "排序": 2,
                },
                {
                    "指标简称": "VD",
                    "上海指标码": "VD",
                    "中文简称": "25-羟基维生素D",
                    "性别": "F/M",
                    "风险类别": "维生素",
                    "排序": 10,
                },
            ]
        ).to_excel(writer, sheet_name="指标明细", index=False)

        pd.DataFrame(
            [
                {"指标简称": "CEA", "疾病类型": "结直肠癌", "指标类型": "辅助"},
                {"指标简称": "CEA", "疾病类型": "肺癌", "指标类型": "辅助"},
            ]
        ).to_excel(writer, sheet_name="指标对应风险部位", index=False)

    result = run_extract(str(lab_path), str(standard_path), str(output_dir))

    assert (output_dir / "matched_indicators.json").exists()
    assert (output_dir / "summary_sections.json").exists()
    assert (output_dir / "nutrition_sections.json").exists()
    assert len(result["matched_rows"]) == 3
    cancer_summary = result["summary_sections"]["癌症健康监测小结"]
    assert len(cancer_summary) == 1
    assert cancer_summary[0]["indicator_short_name"] == "CEA"
    assert "结直肠癌" in cancer_summary[0]["related_diseases"]
    assert "肺癌" in cancer_summary[0]["related_diseases"]
    assert result["nutrition_sections"]["维生素检测结果"][0]["risk_status"] == "不足"


def test_run_extract_parses_numeric_results_with_comparison_prefix(tmp_path: Path):
    lab_path = tmp_path / "lab.xlsx"
    standard_path = tmp_path / "standard.xlsx"
    output_dir = tmp_path / "output"

    pd.DataFrame(
        [
            {
                "病人性别": "男",
                "项目代号": "BHCG",
                "项目名称": "β人绒毛膜促性腺激素",
                "项目测定值": "<1.20",
                "参考值": "< 5.00",
                "单位": "IU/L",
            },
        ]
    ).to_excel(lab_path, index=False)

    with pd.ExcelWriter(standard_path, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {
                    "指标简称": "BHCG",
                    "上海指标码": "BHCG",
                    "中文简称": "β人绒毛膜促性腺激素",
                    "性别": "F/M",
                    "风险类别": "癌筛",
                    "排序": 1,
                },
            ]
        ).to_excel(writer, sheet_name="指标明细", index=False)

        pd.DataFrame(
            [
                {"指标简称": "BHCG", "疾病类型": "睾丸癌", "指标类型": "辅助"},
            ]
        ).to_excel(writer, sheet_name="指标对应风险部位", index=False)

    result = run_extract(str(lab_path), str(standard_path), str(output_dir))

    assert result["matched_rows"][0]["risk_status"] == "normal"
    assert result["summary_sections"]["癌症健康监测小结"] == []


def test_run_extract_includes_indicator_descriptions(tmp_path: Path):
    lab_path = tmp_path / "lab.xlsx"
    standard_path = tmp_path / "standard.xlsx"
    output_dir = tmp_path / "output"

    pd.DataFrame(
        [
            {
                "病人性别": "男",
                "项目代号": "VD",
                "项目名称": "25-羟基维生素D",
                "项目测定值": 29.85,
                "参考值": "严重缺乏:≤10.00\n缺乏:10.01-20.00\n不足:20.01-30.00\n正常:30.01-80.00",
                "单位": "ng/mL",
            },
        ]
    ).to_excel(lab_path, index=False)

    with pd.ExcelWriter(standard_path, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {
                    "指标简称": "VD",
                    "上海指标码": "VD",
                    "中文简称": "25-羟基维生素D",
                    "性别": "F/M",
                    "风险类别": "维生素",
                    "排序": 1,
                },
            ]
        ).to_excel(writer, sheet_name="指标明细", index=False)
        pd.DataFrame(columns=["指标简称", "疾病类型", "指标类型"]).to_excel(
            writer, sheet_name="指标对应风险部位", index=False
        )
        pd.DataFrame(
            [
                {
                    "指标简称": "VD",
                    "指标": "VD\n25-羟基维生素D",
                    "具体意义": "缺乏提示维生素D不足。",
                    "临床应用": "建议增加饮食补充。",
                },
            ]
        ).to_excel(writer, sheet_name="指标说明", index=False)

    result = run_extract(str(lab_path), str(standard_path), str(output_dir))

    row = result["matched_rows"][0]
    assert row["indicator_label"] == "VD\n25-羟基维生素D"
    assert row["indicator_meaning"] == "缺乏提示维生素D不足。"
    assert row["indicator_application"] == "建议增加饮食补充。"


def test_render_command_writes_markdown_and_calls_pdf_export(tmp_path: Path, monkeypatch):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "matched_indicators.json").write_text(
        json.dumps(
            [
                {
                    "病人姓名": "边伟星",
                    "病人性别": "男",
                    "病人年龄": 56,
                    "specimen_type": "血清",
                    "received_at": "2026-03-11 18:57:00",
                    "reported_at": "2026-03-12 16:27:00",
                    "送检医院": "杭州某机构",
                    "match_status": "hit_by_short",
                    "risk_category": "维生素",
                    "indicator_display_name": "25-羟基维生素D",
                    "indicator_short_name": "VD",
                    "indicator_label": "VD",
                    "indicator_meaning": "意义",
                    "indicator_application": "应用",
                    "raw_result": "29.85",
                    "raw_reference": "正常:30-80",
                    "risk_status": "不足",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (input_dir / "summary_sections.json").write_text(
        json.dumps({"癌症健康监测小结": [], "心脑血管健康监测小结": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (input_dir / "nutrition_sections.json").write_text(
        json.dumps(
            {"微量元素检测结果": [], "维生素检测结果": [{"indicator_display_name": "25-羟基维生素D", "raw_result": "29.85", "raw_reference": "正常:30-80", "risk_status": "不足", "indicator_label": "VD", "indicator_meaning": "意义", "indicator_application": "应用"}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (input_dir / "cancer_interpretations.json").write_text(json.dumps([], ensure_ascii=False), encoding="utf-8")

    calls = []

    def fake_export(markdown_path, pdf_path, title, author):
        calls.append((markdown_path, pdf_path, title, author))
        Path(pdf_path).write_text("pdf", encoding="utf-8")

    monkeypatch.setattr("report_pipeline.cli.export_pdf", fake_export)

    markdown_path = tmp_path / "report.md"
    pdf_path = tmp_path / "report.pdf"
    exit_code = main(
        [
            "render",
            "--input-dir",
            str(input_dir),
            "--markdown-output",
            str(markdown_path),
            "--pdf-output",
            str(pdf_path),
        ]
    )

    assert exit_code == 0
    assert markdown_path.exists()
    assert "# 综合健康检测报告" in markdown_path.read_text(encoding="utf-8")
    assert calls[0][1] == str(pdf_path)
