import pandas as pd

from report_pipeline.sources import normalize_lab_dataframe


REQUIRED_COLUMNS = [
    "raw_code",
    "raw_name",
    "raw_result",
    "lab_flag",
    "raw_reference",
    "unit",
    "raw_barcode",
    "specimen_type",
    "received_at",
    "reported_at",
    "reviewed_at",
    "sampled_at",
]


def test_normalize_backfills_missing_canonical_columns():
    raw = pd.DataFrame(
        [
            {
                "项目代号": "VD",
                "项目名称": "25-羟基维生素D",
            }
        ]
    )

    out = normalize_lab_dataframe(raw)
    assert set(REQUIRED_COLUMNS) <= set(out.columns)
    assert out.loc[0, "raw_code"] == "VD"
    assert out.loc[0, "raw_name"] == "25-羟基维生素D"
    for column in REQUIRED_COLUMNS[2:]:
        assert pd.isna(out.loc[0, column])


def test_normalize_new_format_columns():
    raw = pd.DataFrame(
        [
            {
                "项目代号": "VD",
                "项目名称": "25-羟基维生素D",
                "项目测定值": 29.85,
                "高低标记": "",
                "参考值": "正常:30.01-80.00",
                "单位": "ng/mL",
                "艾迪康条码": "1Z1127003774",
                "样本种类": "血清",
                "报告日期": "2026-03-12 16:27:00",
            }
        ]
    )

    out = normalize_lab_dataframe(raw)
    record = out.iloc[0].to_dict()
    assert record["raw_code"] == "VD"
    assert record["raw_result"] == 29.85
    assert record["raw_barcode"] == "1Z1127003774"
    assert record["specimen_type"] == "血清"


def test_normalize_old_format_columns():
    raw = pd.DataFrame(
        [
            {
                "项目编号": "CEA",
                "项目名称": "癌胚抗原",
                "结果": 4.19,
                "提示": "z",
                "参考值": "0.00-5.09",
                "单位": "ng/mL",
                "条形码": "#630805000127",
                "标本类型": "血清",
                "报告时间": "2025/12/25 04:25:53",
            }
        ]
    )

    out = normalize_lab_dataframe(raw)
    record = out.iloc[0].to_dict()
    assert record["raw_code"] == "CEA"
    assert record["raw_result"] == 4.19
    assert record["lab_flag"] == "z"
    assert record["raw_barcode"] == "#630805000127"
