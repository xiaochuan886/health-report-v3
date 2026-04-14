import json

from report_pipeline.render_inputs import build_render_context, load_render_bundle


def test_load_render_bundle_reads_exported_json(tmp_path):
    (tmp_path / "matched_indicators.json").write_text("[]", encoding="utf-8")
    (tmp_path / "summary_sections.json").write_text('{"癌症健康监测小结":[],"心脑血管健康监测小结":[]}', encoding="utf-8")
    (tmp_path / "nutrition_sections.json").write_text('{"微量元素检测结果":[],"维生素检测结果":[]}', encoding="utf-8")
    (tmp_path / "cancer_interpretations.json").write_text("[]", encoding="utf-8")

    bundle = load_render_bundle(tmp_path)

    assert bundle["matched_rows"] == []
    assert list(bundle["summary_sections"]) == ["癌症健康监测小结", "心脑血管健康监测小结"]


def test_build_render_context_extracts_patient_and_glossary():
    bundle = {
        "matched_rows": [
            {
                "病人姓名": "边伟星",
                "病人性别": "男",
                "病人年龄": 56,
                "specimen_type": "血清",
                "received_at": "2026-03-11 18:57:00",
                "reported_at": "2026-03-12 16:27:00",
                "送检医院": "杭州某机构",
                "match_status": "hit_by_short",
                "risk_category": "癌筛",
                "indicator_short_name": "CEA",
                "indicator_label": "CEA\n癌胚抗原",
                "indicator_meaning": "说明",
                "indicator_application": "应用",
                "disease_type": "结直肠癌",
                "risk_status": "near_upper",
            }
        ],
        "summary_sections": {
            "癌症健康监测小结": [{"indicator_short_name": "CEA", "indicator_label": "CEA\n癌胚抗原", "indicator_meaning": "说明", "indicator_application": "应用"}],
            "心脑血管健康监测小结": [],
        },
        "nutrition_sections": {"微量元素检测结果": [], "维生素检测结果": []},
    }

    context = build_render_context(bundle)

    assert context["patient_name"] == "边伟星"
    assert context["patient_gender"] == "男"
    assert context["glossary_rows"][0]["indicator_short_name"] == "CEA"
    assert context["cancer_summary_rows"][0]["indicator_short_name"] == "CEA"
