from report_pipeline.report_styles import format_display, risk_bar, status_label


def test_status_label_maps_core_statuses():
    assert status_label("above") == "高于参考范围"
    assert status_label("不足") == "不足"


def test_risk_bar_renders_fixed_width():
    assert risk_bar("near_upper") == "████████░░"
    assert risk_bar("unknown") == "░░░░░░░░░░"


def test_format_display_uses_placeholder_for_empty_values():
    assert format_display("") == "--"
    assert format_display(None) == "--"
