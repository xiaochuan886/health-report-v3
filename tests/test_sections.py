import pandas as pd

from report_pipeline.sections import build_nutrition_sections, build_summary_sections


def test_build_summary_sections_excludes_nutrition_and_normal_rows():
    matched = pd.DataFrame(
        [
            {
                "risk_category": "癌筛",
                "indicator_display_name": "糖链抗原72-4",
                "indicator_short_name": "CA72-4",
                "raw_reference": "≤12.000",
                "risk_status": "above",
                "disease_type": "胃癌",
                "indicator_type": "辅助",
                "display_order": 20,
            },
            {
                "risk_category": "癌筛",
                "indicator_display_name": "癌胚抗原",
                "indicator_short_name": "CEA",
                "raw_reference": "≤5.00",
                "risk_status": "near_upper",
                "disease_type": "结直肠癌",
                "indicator_type": "辅助",
                "display_order": 5,
            },
            {
                "risk_category": "癌筛",
                "indicator_display_name": "癌胚抗原",
                "indicator_short_name": "CEA",
                "raw_reference": "≤5.00",
                "risk_status": "normal",
                "disease_type": "胃癌",
                "indicator_type": "辅助",
                "display_order": 5,
            },
            {
                "risk_category": "癌筛",
                "indicator_display_name": "甲胎蛋白",
                "indicator_short_name": "AFP",
                "raw_reference": "/",
                "risk_status": "normal",
                "disease_type": "肝癌",
                "indicator_type": "辅助",
                "display_order": 10,
            },
            {
                "risk_category": "心筛",
                "indicator_display_name": "低密度脂蛋白胆固醇",
                "indicator_short_name": "LDL-C",
                "raw_reference": "<3.37",
                "risk_status": "near_upper",
                "disease_type": None,
                "display_order": 10,
            },
            {
                "risk_category": "维生素",
                "indicator_display_name": "25-羟基维生素D",
                "indicator_short_name": "VD",
                "raw_reference": "30-80",
                "risk_status": "不足",
                "disease_type": None,
                "display_order": 1,
            },
        ]
    )

    summary = build_summary_sections(matched)

    assert list(summary) == ["癌症健康监测小结", "心脑血管健康监测小结"]
    cancer = summary["癌症健康监测小结"]
    # AFP (raw_reference="/") and CEA-normal are excluded
    assert [row["indicator_display_name"] for row in cancer] == ["癌胚抗原", "糖链抗原72-4"]
    assert cancer[0]["related_diseases"] == "辅助: 结直肠癌"
    assert cancer[1]["related_diseases"] == "辅助: 胃癌"
    assert [row["indicator_display_name"] for row in summary["心脑血管健康监测小结"]] == ["低密度脂蛋白胆固醇"]
    assert all(row["risk_category"] == "癌筛" for row in cancer)
    assert all(row["risk_status"] not in {"normal", "正常"} for row in cancer)
    assert all(row["risk_category"] == "心筛" for row in summary["心脑血管健康监测小结"])


def test_build_nutrition_sections_only_uses_hits():
    matched = pd.DataFrame(
        [
            {
                "match_status": "hit_by_short",
                "risk_category": "微量元素",
                "indicator_display_name": "铜",
                "display_order": 20,
            },
            {
                "match_status": "unmatched",
                "risk_category": "微量元素",
                "indicator_display_name": "锌",
                "display_order": 10,
            },
            {
                "match_status": "hit_by_shanghai",
                "risk_category": "维生素",
                "indicator_display_name": "25-羟基维生素D",
                "display_order": 1,
            },
            {
                "match_status": "hit_by_short",
                "risk_category": "癌筛",
                "indicator_display_name": "糖链抗原72-4",
                "display_order": 5,
            },
        ]
    )

    nutrition = build_nutrition_sections(matched)

    assert list(nutrition) == ["微量元素检测结果", "维生素检测结果"]
    assert [row["indicator_display_name"] for row in nutrition["微量元素检测结果"]] == ["铜"]
    assert [row["indicator_display_name"] for row in nutrition["维生素检测结果"]] == ["25-羟基维生素D"]
    assert all(row["match_status"] != "unmatched" for rows in nutrition.values() for row in rows)
    assert all(row["risk_category"] in {"微量元素", "维生素"} for rows in nutrition.values() for row in rows)
