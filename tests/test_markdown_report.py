from report_pipeline.markdown_report import generate_markdown_report, _STAMP_MARKER


def test_generate_markdown_report_contains_required_sections():
    context = {
        "title": "综合健康检测报告",
        "patient_name": "边伟星",
        "patient_gender": "男",
        "patient_age": "56",
        "specimen_type": "血清",
        "received_at": "2026-03-11 18:57:00",
        "reported_at": "2026-03-12 16:27:00",
        "hospital_name": "杭州某机构",
        "summary_sections": {
            "癌症健康监测小结": [{"indicator_display_name": "CEA", "raw_result": "4.5", "raw_reference": "0-5", "risk_status": "near_upper", "related_diseases": "辅助: 结直肠癌"}],
            "心脑血管健康监测小结": [{"indicator_display_name": "总胆固醇", "raw_result": "6.2", "raw_reference": "2-5.7", "risk_status": "above"}],
        },
        "cancer_summary_rows": [{"indicator_display_name": "CEA", "raw_result": "4.5", "raw_reference": "0-5", "risk_status": "near_upper", "related_diseases": "辅助: 结直肠癌"}],
        "cancer_all_rows": [{"indicator_display_name": "CEA", "raw_result": "4.5", "raw_reference": "0-5", "risk_status": "near_upper"}],
        "cancer_interpretations": [],
        "cardio_rows": [{"indicator_display_name": "总胆固醇", "raw_result": "6.2", "raw_reference": "2-5.7", "risk_status": "above"}],
        "cardio_all_rows": [{"indicator_display_name": "总胆固醇", "raw_result": "6.2", "raw_reference": "2-5.7", "risk_status": "above"}],
        "cardio_interpretation": [],
        "cardio_interpretations": [],
        "nutrition_sections": {
            "微量元素检测结果": [{"indicator_display_name": "铜", "raw_result": "12.6", "raw_reference": "8-30", "risk_status": "near_lower"}],
            "维生素检测结果": [{"indicator_display_name": "25-羟基维生素D", "raw_result": "29.85", "raw_reference": "正常:30-80", "risk_status": "不足"}],
        },
        "nutrition_explanations": {
            "微量元素检测结果": [{"indicator_label": "铜", "indicator_meaning": "意义", "indicator_application": "应用", "raw_reference": "8-30", "risk_status": "near_lower"}],
            "维生素检测结果": [{"indicator_label": "VD", "indicator_meaning": "意义", "indicator_application": "应用", "raw_reference": "30-80", "risk_status": "不足"}],
        },
        "glossary_rows": [{"indicator_label": "CEA", "indicator_meaning": "意义", "indicator_application": "应用"}],
        "health_guide_items": ["保持作息规律。"],
    }

    markdown = generate_markdown_report(context)

    assert "# 综合健康检测报告" in markdown
    assert "## 基础信息与质控校验表" in markdown
    assert "## 基础信息" not in markdown or "基础信息与质控校验表" in markdown
    assert "## 质控校验表" not in markdown
    assert "## 第一部分 评估结果小结" in markdown
    assert "## 第三部分 心脑血管健康监测与指导" in markdown
    assert "## 第四部分 大营养检测与建议" in markdown
    assert "## 医学名词释义" in markdown


def test_merged_table_contains_patient_info():
    context = {
        "title": "综合健康检测报告",
        "patient_name": "边伟星",
        "patient_gender": "男",
        "patient_age": "56",
        "specimen_type": "血清",
        "received_at": "2026-03-11 18:57:00",
        "reported_at": "2026-03-12 16:27:00",
        "hospital_name": "杭州某机构",
        "quality_control": {
            "sampling_date": "2026年03月10日",
            "receive_date": "2026年03月11日",
            "report_date": "2026年03月12日",
            "sample_id": "1Z112700123456",
            "sample_type": "静脉血",
            "sample_amount": "17 ML",
            "sample_status": "合格",
            "temperature_control": "合格",
            "data_quality_control": "合格",
            "sending_unit": "山丘生物（杭州）有限公司",
            "inspection_org": "杭州艾迪康医学检验中心",
            "address": "浙江省杭州市西湖区三墩镇振中路208号",
            "test_item": "综合健康评估",
            "inspectors": "张三",
            "reviewers": "李四",
        },
        "summary_sections": {
            "癌症健康监测小结": [],
            "心脑血管健康监测小结": [],
        },
        "cancer_all_rows": [],
        "cardio_all_rows": [],
        "cancer_interpretations": [],
        "cardio_interpretations": [],
        "nutrition_sections": {
            "微量元素检测结果": [],
            "维生素检测结果": [],
        },
        "nutrition_explanations": {
            "微量元素检测结果": [],
            "维生素检测结果": [],
        },
        "glossary_rows": [],
        "health_guide_items": ["保持作息规律。"],
    }

    markdown = generate_markdown_report(context)

    # Patient info in merged table
    assert "边伟星" in markdown
    assert "男" in markdown
    assert "56" in markdown

    # QC fields present
    assert "采样日期" in markdown
    assert "送检单位" in markdown

    # Stamp markers for the three 合格 items
    assert markdown.count(_STAMP_MARKER) == 3


def test_no_duplicate_sections():
    """基础信息和质控校验表 should not appear as separate sections."""
    context = {
        "title": "综合健康检测报告",
        "patient_name": "测试",
        "patient_gender": "女",
        "patient_age": "30",
        "specimen_type": "血清",
        "received_at": "--",
        "reported_at": "--",
        "hospital_name": "--",
        "summary_sections": {"癌症健康监测小结": [], "心脑血管健康监测小结": []},
        "cancer_all_rows": [],
        "cardio_all_rows": [],
        "cancer_interpretations": [],
        "cardio_interpretations": [],
        "nutrition_sections": {"微量元素检测结果": [], "维生素检测结果": []},
        "nutrition_explanations": {"微量元素检测结果": [], "维生素检测结果": []},
        "glossary_rows": [],
        "health_guide_items": [],
    }

    markdown = generate_markdown_report(context)

    # Old section names should not appear
    assert "\n## 基础信息\n" not in markdown
    assert "\n## 质控校验表\n" not in markdown
    # Merged section should appear
    assert "## 基础信息与质控校验表" in markdown
