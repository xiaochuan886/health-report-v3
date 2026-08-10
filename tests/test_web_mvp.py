from pathlib import Path


def test_job_service_runs_pipeline_and_writes_artifacts(tmp_path: Path):
    from report_pipeline.web_mvp import ReportJobService

    calls = []

    def fake_run_extract(lab_xls, standard_xlsx, output_dir, personal_info_xlsx=None):
        calls.append((Path(lab_xls).name, Path(standard_xlsx).name, Path(output_dir).name, Path(personal_info_xlsx).name if personal_info_xlsx else None))
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "matched_indicators.json").write_text("[]", encoding="utf-8")
        (out / "summary_sections.json").write_text('{"癌症健康监测小结":[],"心脑血管健康监测小结":[]}', encoding="utf-8")
        (out / "nutrition_sections.json").write_text('{"微量元素检测结果":[],"维生素检测结果":[]}', encoding="utf-8")

    def fake_load_render_bundle(output_dir):
        return {
            "matched_rows": [{"病人姓名": "测试", "病人性别": "男", "病人年龄": 30, "送检医院": "机构"}],
            "summary_sections": {"癌症健康监测小结": [], "心脑血管健康监测小结": []},
            "nutrition_sections": {"微量元素检测结果": [], "维生素检测结果": []},
        }

    def fake_build_render_context(bundle):
        return {
            "title": "综合健康检测报告",
            "hospital_name": "机构",
            "patient_name": "测试",
            "patient_gender": "男",
            "patient_age": "30",
            "report_date": "2026年04月15日",
        }

    def fake_generate_markdown_report(context):
        return "# 报告\n"

    def fake_export_pdf(markdown_path, pdf_path, title, author, **kwargs):
        Path(pdf_path).write_text("pdf", encoding="utf-8")

    service = ReportJobService(
        root_dir=tmp_path,
        run_extract_fn=fake_run_extract,
        load_render_bundle_fn=fake_load_render_bundle,
        build_render_context_fn=fake_build_render_context,
        generate_markdown_report_fn=fake_generate_markdown_report,
        export_pdf_fn=fake_export_pdf,
    )

    job_id = service.create_job(
        lab_filename="lab.xls",
        lab_bytes=b"lab",
        personal_info_filename="personal_info.xlsx",
        personal_info_bytes=b"personal",
    )
    service.wait(job_id, timeout=3.0)

    status = service.get_status(job_id)
    assert status["status"] == "succeeded"
    assert (tmp_path / "jobs" / job_id / "report.md").exists()
    assert (tmp_path / "jobs" / job_id / "report.pdf").exists()
    assert calls and calls[0][0] == "lab.xls"
    assert calls[0][1] == "standard.xlsx"


def test_job_service_marks_failed_on_exception(tmp_path: Path):
    from report_pipeline.web_mvp import ReportJobService

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    service = ReportJobService(root_dir=tmp_path, run_extract_fn=boom)
    job_id = service.create_job(
        lab_filename="lab.xls",
        lab_bytes=b"lab",
    )
    service.wait(job_id, timeout=3.0)

    status = service.get_status(job_id)
    assert status["status"] == "failed"
    assert "boom" in status["error"]


def test_index_html_sets_inline_favicon():
    from report_pipeline.web_mvp import _INDEX_HTML

    assert 'rel="icon"' in _INDEX_HTML
    assert 'href="data:,' in _INDEX_HTML


def test_index_html_uses_system_standard_and_progress_ui():
    from report_pipeline.web_mvp import _INDEX_HTML

    assert 'name="standard_xlsx"' not in _INDEX_HTML
    assert 'data-step="extract"' in _INDEX_HTML
    assert 'aria-live="polite"' in _INDEX_HTML


def test_job_service_list_jobs_sorted_by_created_time(tmp_path: Path):
    from report_pipeline.web_mvp import ReportJobService

    def fake_run_extract(*args, **kwargs):
        out = Path(args[2])
        out.mkdir(parents=True, exist_ok=True)
        (out / "matched_indicators.json").write_text("[]", encoding="utf-8")
        (out / "summary_sections.json").write_text('{"癌症健康监测小结":[],"心脑血管健康监测小结":[]}', encoding="utf-8")
        (out / "nutrition_sections.json").write_text('{"微量元素检测结果":[],"维生素检测结果":[]}', encoding="utf-8")

    def fake_load_render_bundle(output_dir):
        return {
            "matched_rows": [{"病人姓名": "测试", "病人性别": "男", "病人年龄": 30, "送检医院": "机构"}],
            "summary_sections": {"癌症健康监测小结": [], "心脑血管健康监测小结": []},
            "nutrition_sections": {"微量元素检测结果": [], "维生素检测结果": []},
        }

    def fake_build_render_context(bundle):
        return {"title": "综合健康检测报告", "hospital_name": "机构", "patient_name": "测试", "patient_gender": "男", "patient_age": "30"}

    def fake_generate_markdown_report(context):
        return "# 报告\n"

    def fake_export_pdf(markdown_path, pdf_path, title, author, **kwargs):
        Path(pdf_path).write_text("pdf", encoding="utf-8")

    service = ReportJobService(
        root_dir=tmp_path,
        run_extract_fn=fake_run_extract,
        load_render_bundle_fn=fake_load_render_bundle,
        build_render_context_fn=fake_build_render_context,
        generate_markdown_report_fn=fake_generate_markdown_report,
        export_pdf_fn=fake_export_pdf,
    )

    a = service.create_job(lab_filename="a.xls", lab_bytes=b"a")
    b = service.create_job(lab_filename="b.xls", lab_bytes=b"b")
    service.wait(a, timeout=3.0)
    service.wait(b, timeout=3.0)

    jobs = service.list_jobs(limit=10)
    assert len(jobs) >= 2
    assert jobs[0]["created_at"] >= jobs[1]["created_at"]


def test_job_service_keeps_lab_file_when_personal_info_has_same_filename(tmp_path: Path):
    from report_pipeline.web_mvp import ReportJobService

    captured: dict[str, bytes | str | None] = {}

    def fake_run_extract(lab_xls, standard_xlsx, output_dir, personal_info_xlsx=None):
        lab_path = Path(lab_xls)
        captured["lab_name"] = lab_path.name
        captured["lab_bytes"] = lab_path.read_bytes()

        if personal_info_xlsx:
            personal_path = Path(personal_info_xlsx)
            captured["personal_name"] = personal_path.name
            captured["personal_bytes"] = personal_path.read_bytes()
        else:
            captured["personal_name"] = None
            captured["personal_bytes"] = None

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "matched_indicators.json").write_text("[]", encoding="utf-8")
        (out / "summary_sections.json").write_text('{"癌症健康监测小结":[],"心脑血管健康监测小结":[]}', encoding="utf-8")
        (out / "nutrition_sections.json").write_text('{"微量元素检测结果":[],"维生素检测结果":[]}', encoding="utf-8")

    def fake_load_render_bundle(output_dir):
        return {
            "matched_rows": [{"病人姓名": "测试", "病人性别": "男", "病人年龄": 30, "送检医院": "机构"}],
            "summary_sections": {"癌症健康监测小结": [], "心脑血管健康监测小结": []},
            "nutrition_sections": {"微量元素检测结果": [], "维生素检测结果": []},
        }

    def fake_build_render_context(bundle):
        return {"title": "综合健康检测报告", "hospital_name": "机构", "patient_name": "测试", "patient_gender": "男", "patient_age": "30"}

    service = ReportJobService(
        root_dir=tmp_path,
        run_extract_fn=fake_run_extract,
        load_render_bundle_fn=fake_load_render_bundle,
        build_render_context_fn=fake_build_render_context,
        generate_markdown_report_fn=lambda context: "# 报告\n",
        export_pdf_fn=lambda markdown_path, pdf_path, title, author, **kwargs: Path(pdf_path).write_text("pdf", encoding="utf-8"),
    )

    job_id = service.create_job(
        lab_filename="same.xlsx",
        lab_bytes=b"LAB",
        personal_info_filename="same.xlsx",
        personal_info_bytes=b"PERS",
    )
    service.wait(job_id, timeout=3.0)

    assert captured["lab_bytes"] == b"LAB"
    assert captured["personal_bytes"] == b"PERS"
    assert captured["lab_name"] != captured["personal_name"]


def test_resolve_port_falls_back_to_next_available():
    from report_pipeline.web_mvp import _resolve_port

    busy = {8765, 8766}

    def fake_available(host: str, port: int) -> bool:
        return port not in busy

    import report_pipeline.web_mvp as m

    original = m._is_port_available
    try:
        m._is_port_available = fake_available
        assert _resolve_port("127.0.0.1", 8765, max_tries=5) == 8767
    finally:
        m._is_port_available = original
