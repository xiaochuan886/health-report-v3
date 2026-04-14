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
