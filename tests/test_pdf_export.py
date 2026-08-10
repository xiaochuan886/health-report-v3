import io
import pytest

from report_pipeline.pdf_export import (
    build_md2pdf_command,
    export_pdf,
    _add_green_stamps,
    _calculate_stamp_positions,
    _create_stamp_overlay,
    _STAMP_MARKER,
)


def test_build_md2pdf_command_contains_expected_arguments():
    import sys
    command = build_md2pdf_command("report.md", "report.pdf", "综合健康检测报告", "检测机构")

    assert command[0] == sys.executable
    assert any(arg.startswith("--input=") for arg in command)
    assert any(arg == "--theme=corporate-blue" for arg in command)
    # Verify health report specific flags
    assert "--cover=true" in command
    assert "--toc=true" in command
    assert "--first-h1-inline=true" in command
    assert any(arg.startswith("--base-dir=") for arg in command)


def test_export_pdf_raises_runtime_error_on_failure(monkeypatch):
    class Result:
        returncode = 1
        stderr = "boom"

    monkeypatch.setattr("report_pipeline.pdf_export.subprocess.run", lambda *args, **kwargs: Result())
    # Also mock _add_green_stamps since the pdf won't exist
    monkeypatch.setattr("report_pipeline.pdf_export._add_green_stamps", lambda path: None)

    with pytest.raises(RuntimeError, match="boom"):
        export_pdf("report.md", "report.pdf", "综合健康检测报告", "检测机构")


def test_export_pdf_calls_md2pdf_in_process_when_frozen(monkeypatch):
    called = {}

    def fake_main(argv=None):
        called["argv"] = argv
        return None

    monkeypatch.setattr("report_pipeline.pdf_export._is_frozen_app", lambda: True)
    monkeypatch.setattr("report_pipeline.md2pdf.main", fake_main)
    monkeypatch.setattr(
        "report_pipeline.pdf_export.subprocess.run",
        lambda *args, **kwargs: pytest.fail("subprocess.run should not be called in frozen mode"),
    )

    export_pdf("report.md", "report.pdf", "综合健康检测报告", "检测机构")

    assert called["argv"] is not None
    assert any(arg.startswith("--input=") for arg in called["argv"])
    assert any(arg.startswith("--output=") for arg in called["argv"])


def test_build_md2pdf_command_handles_dash_prefixed_patient_name():
    command = build_md2pdf_command(
        "report.md",
        "report.pdf",
        "综合健康检测报告",
        "检测机构",
        patient_name="--",
        cover_patient="--  --  67岁",
    )

    assert "--header-right=--" in command
    assert "--cover-patient=--  --  67岁" in command


def test_calculate_stamp_positions_returns_three():
    """Should return exactly 3 stamp positions for the three 合格 rows."""
    positions = _calculate_stamp_positions(595.28, 841.89)

    assert len(positions) == 3
    for x, y in positions:
        assert 0 < x < 595.28
        assert 0 < y < 841.89


def test_calculate_stamp_positions_y_ordering():
    """Stamps should be vertically ordered (top to bottom)."""
    positions = _calculate_stamp_positions(595.28, 841.89)

    y_values = [y for _, y in positions]
    assert y_values[0] > y_values[1] > y_values[2]


def test_create_stamp_overlay_produces_valid_pdf():
    """Overlay should be a valid single-page PDF."""
    positions = [(300, 400), (300, 380), (300, 360)]
    data = _create_stamp_overlay(595.28, 841.89, positions)

    assert len(data) > 0
    assert data.startswith(b"%PDF")

    # Verify it's readable by pypdf
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(data))
    assert len(reader.pages) == 1


def test_add_green_stamps_no_marker_no_error(tmp_path, monkeypatch):
    """If PDF has no STAMP marker, _add_green_stamps should return without error."""
    # Create a minimal PDF without the stamp marker
    import pypdf
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=595, height=842)
    pdf_path = tmp_path / "test.pdf"
    with open(pdf_path, "wb") as f:
        writer.write(f)

    # Should not raise
    _add_green_stamps(str(pdf_path))
