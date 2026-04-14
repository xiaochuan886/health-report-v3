import pandas as pd

from report_pipeline.whitelist import match_indicators


def test_match_indicators_prefers_short_name_then_shanghai_code():
    lab = pd.DataFrame(
        [
            {"raw_code": "VD", "raw_name": "25-羟基维生素D"},
            {"raw_code": "CEA-X", "raw_name": "癌胚抗原"},
            {"raw_code": "UNKNOWN", "raw_name": "未知项目"},
        ]
    )
    whitelist = pd.DataFrame(
        [
            {
                "指标简称": "VD",
                "上海指标码": "VD",
                "中文简称": "25-羟基维生素D",
                "性别": "F/M",
                "风险类别": "维生素",
                "排序": 40,
            },
            {
                "指标简称": "CEA",
                "上海指标码": "CEA-X",
                "中文简称": "癌胚抗原",
                "性别": "F/M",
                "风险类别": "癌筛",
                "排序": 2,
            },
        ]
    )

    out = match_indicators(lab, whitelist, patient_gender="男")

    assert list(out["match_status"]) == ["hit_by_short", "hit_by_shanghai", "unmatched"]
    assert list(out["indicator_short_name"].fillna("")) == ["VD", "CEA", ""]
    assert list(out["indicator_display_name"].fillna("")) == ["25-羟基维生素D", "癌胚抗原", ""]
    assert list(out["risk_category"].fillna("")) == ["维生素", "癌筛", ""]
    assert list(out["display_order"].fillna("")) == [40, 2, ""]


def test_match_indicators_respects_gender_filtering():
    lab = pd.DataFrame(
        [
            {"raw_code": "PSA", "raw_name": "前列腺特异抗原"},
            {"raw_code": "CA125", "raw_name": "糖类抗原125"},
        ]
    )
    whitelist = pd.DataFrame(
        [
            {
                "指标简称": "PSA",
                "上海指标码": "PSA",
                "中文简称": "前列腺特异抗原",
                "性别": "M",
                "风险类别": "癌筛",
                "排序": 1,
            },
            {
                "指标简称": "CA125",
                "上海指标码": "CA125",
                "中文简称": "糖类抗原125",
                "性别": "F",
                "风险类别": "癌筛",
                "排序": 2,
            },
        ]
    )

    male_out = match_indicators(lab, whitelist, patient_gender="男")
    female_out = match_indicators(lab, whitelist, patient_gender="女")

    assert list(male_out["match_status"]) == ["hit_by_short", "unmatched"]
    assert list(female_out["match_status"]) == ["unmatched", "hit_by_short"]


def test_match_indicators_supports_chinese_whitelist_gender_values():
    lab = pd.DataFrame(
        [
            {"raw_code": "PSA", "raw_name": "前列腺特异抗原"},
            {"raw_code": "CA125", "raw_name": "糖类抗原125"},
        ]
    )
    whitelist = pd.DataFrame(
        [
            {
                "指标简称": "PSA",
                "上海指标码": "PSA",
                "中文简称": "前列腺特异抗原",
                "性别": "男",
                "风险类别": "癌筛",
                "排序": 1,
            },
            {
                "指标简称": "CA125",
                "上海指标码": "CA125",
                "中文简称": "糖类抗原125",
                "性别": "女",
                "风险类别": "癌筛",
                "排序": 2,
            },
        ]
    )

    male_out = match_indicators(lab, whitelist, patient_gender="男")
    female_out = match_indicators(lab, whitelist, patient_gender="女")

    assert list(male_out["match_status"]) == ["hit_by_short", "unmatched"]
    assert list(female_out["match_status"]) == ["unmatched", "hit_by_short"]


def test_match_indicators_uses_lowest_sort_for_duplicate_keys():
    lab = pd.DataFrame(
        [
            {"raw_code": "VD", "raw_name": "25-羟基维生素D"},
        ]
    )
    whitelist = pd.DataFrame(
        [
            {
                "指标简称": "VD",
                "上海指标码": "VD",
                "中文简称": "25-羟基维生素D-高排序",
                "性别": "F/M",
                "风险类别": "维生素",
                "排序": 40,
            },
            {
                "指标简称": "VD",
                "上海指标码": "VD",
                "中文简称": "25-羟基维生素D-低排序",
                "性别": "F/M",
                "风险类别": "维生素",
                "排序": 10,
            },
        ]
    )

    out = match_indicators(lab, whitelist, patient_gender="男")

    assert list(out["match_status"]) == ["hit_by_short"]
    assert out.loc[0, "indicator_display_name"] == "25-羟基维生素D-低排序"
    assert out.loc[0, "display_order"] == 10
