from report_pipeline.reference_parser import parse_reference
from report_pipeline.risk import evaluate_risk


def test_parse_range_reference():
    parsed = parse_reference("57.04-139.14")
    assert parsed["kind"] == "range"
    assert parsed["low"] == 57.04
    assert parsed["high"] == 139.14


def test_parse_vitamin_d_multirule():
    parsed = parse_reference(
        "严重缺乏:≤10.00\n缺乏:10.01-20.00\n不足:20.01-30.00\n正常:30.01-80.00\n过量:>80.00\n中毒:>150.00"
    )
    assert parsed["kind"] == "multi_rule"
    assert parsed["labels"][:3] == ["严重缺乏", "缺乏", "不足"]


def test_evaluate_range_near_upper():
    parsed = parse_reference("57.04-139.14")
    risk = evaluate_risk(123, parsed)
    assert risk["risk_status"] == "near_upper"


def test_evaluate_range_near_lower_uses_twenty_percent_threshold():
    parsed = parse_reference("10.00-20.00")
    risk = evaluate_risk(12, parsed)
    assert risk["risk_status"] == "near_lower"


def test_evaluate_multirule_status():
    parsed = parse_reference(
        "严重缺乏:≤10.00\n缺乏:10.01-20.00\n不足:20.01-30.00\n正常:30.01-80.00\n过量:>80.00\n中毒:>150.00"
    )
    risk = evaluate_risk(29.85, parsed)
    assert risk["risk_status"] == "不足"


def test_parse_upper_bound_reference():
    parsed = parse_reference("<5.09")
    assert parsed["kind"] == "upper_bound"
    assert parsed["value"] == 5.09


def test_evaluate_upper_bound_near_upper():
    parsed = parse_reference("<10.00")
    risk = evaluate_risk(8.5, parsed)
    assert risk["risk_status"] == "near_upper"


def test_parse_qual_only_reference():
    parsed = parse_reference("阴性")
    assert parsed["kind"] == "qual_only"
    risk = evaluate_risk("阴性", parsed)
    assert risk["risk_status"] == "normal"


def test_evaluate_multirule_negative_label_as_normal():
    parsed = parse_reference("阴性:<0.05")
    risk = evaluate_risk(0.02, parsed)
    assert risk["risk_status"] == "normal"


# ─── 血脂分级参考值（胆固醇 / 甘油三酯 / HDL-C）───
# 修复前：单行分号分隔、无冒号标签、复合"且"条件均解析失败 → 漏报异常


def test_parse_total_cholesterol_semicolon_multirule():
    """总胆固醇：单行分号分隔、无冒号标签。"""
    parsed = parse_reference("合适水平<5.18；边缘升高5.18-6.19；升高≥6.20")
    assert parsed["kind"] == "multi_rule"
    assert parsed["labels"] == ["合适水平", "边缘升高", "升高"]


def test_parse_total_cholesterol_compound_bound():
    """总胆固醇：含"且"复合条件。"""
    parsed = parse_reference("合适水平<5.20；边缘升高≥5.20且<6.20；升高≥6.20")
    assert parsed["kind"] == "multi_rule"
    assert parsed["labels"] == ["合适水平", "边缘升高", "升高"]


def test_evaluate_cholesterol_elevated_is_abnormal():
    parsed = parse_reference("合适水平<5.18；边缘升高5.18-6.19；升高≥6.20")
    risk = evaluate_risk(6.50, parsed)
    assert risk["risk_status"] == "升高"
    assert risk["is_abnormal"] is True


def test_evaluate_cholesterol_borderline_is_abnormal():
    parsed = parse_reference("合适水平<5.18；边缘升高5.18-6.19；升高≥6.20")
    risk = evaluate_risk(5.80, parsed)
    assert risk["risk_status"] == "边缘升高"
    assert risk["is_abnormal"] is True


def test_evaluate_cholesterol_optimal_is_normal():
    parsed = parse_reference("合适水平<5.18；边缘升高5.18-6.19；升高≥6.20")
    risk = evaluate_risk(4.00, parsed)
    assert risk["risk_status"] == "normal"
    assert risk["is_abnormal"] is False


def test_evaluate_triglycerides_elevated_is_abnormal():
    parsed = parse_reference("合适水平<1.70；边缘升高1.70-2.25；升高≥2.26")
    risk = evaluate_risk(2.50, parsed)
    assert risk["risk_status"] == "升高"
    assert risk["is_abnormal"] is True


def test_evaluate_triglycerides_compound_bound_elevated():
    """甘油三酯：复合"且"条件的边缘区间。"""
    parsed = parse_reference("合适水平<1.70；边缘升高≥1.70且<2.25；升高≥2.25")
    risk = evaluate_risk(1.90, parsed)
    assert risk["risk_status"] == "边缘升高"
    assert risk["is_abnormal"] is True


def test_evaluate_hdl_low_is_abnormal():
    """HDL-C：下限型分级（合适水平>1.04；降低≤1.04）。"""
    parsed = parse_reference("合适水平>1.04；降低≤1.04")
    risk = evaluate_risk(0.90, parsed)
    assert risk["risk_status"] == "降低"
    assert risk["is_abnormal"] is True


def test_evaluate_hdl_optimal_is_normal():
    parsed = parse_reference("合适水平>1.04；降低≤1.04")
    risk = evaluate_risk(1.50, parsed)
    assert risk["risk_status"] == "normal"
    assert risk["is_abnormal"] is False


def test_evaluate_strict_less_than_boundary():
    """严格不等号："<5.18" 的边界值 5.18 本身不应判为合适水平。"""
    parsed = parse_reference("合适水平<5.18；边缘升高5.18-6.19；升高≥6.20")
    risk = evaluate_risk(5.18, parsed)
    assert risk["risk_status"] == "边缘升高"
