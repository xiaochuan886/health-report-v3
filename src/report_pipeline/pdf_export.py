from __future__ import annotations

import io
import os
import re
import subprocess
import sys
from pathlib import Path

import pypdf
from pypdf.generic import NameObject


MD2PDF_SCRIPT = Path(__file__).parent / "md2pdf.py"

# Green badge visual parameters
_BADGE_WIDTH = 42       # pt
_BADGE_HEIGHT = 13      # pt
_BADGE_RADIUS = 3       # pt (rounded corner)
_BADGE_COLOR = (0.18, 0.55, 0.34)  # #2E8B57 sea green
_STAMP_MARKER = "STAMP_合格"


def build_md2pdf_command(
    markdown_path: str,
    pdf_path: str,
    title: str,
    author: str,
    patient_name: str = "",
    report_date: str = "",
    institution_name: str = "",
    cover_patient: str = "",
) -> list[str]:
    # Resolve base directory from markdown file location (for image paths)
    base_dir = str(Path(markdown_path).parent.resolve())

    cmd = [
        sys.executable,
        str(MD2PDF_SCRIPT),
        "--input",
        markdown_path,
        "--output",
        pdf_path,
        "--title",
        title,
        "--author",
        institution_name or author,
        "--header-title",
        "",
        "--footer-left",
        title,
        "--theme",
        "corporate-blue",
        "--logo",
        str(Path(__file__).parent / "logo.png"),
        "--cover", "true",
        "--toc", "true",
        "--first-h1-inline", "true",
        "--base-dir", base_dir,
    ]
    if patient_name:
        cmd.extend(["--header-right", patient_name])
    if report_date:
        cmd.extend(["--date", report_date])
    if cover_patient:
        cmd.extend(["--cover-patient", cover_patient])
    return cmd


def _find_stamp_page(pdf_path: str) -> int | None:
    """Find the 0-based page index containing the STAMP marker text."""
    reader = pypdf.PdfReader(pdf_path)
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if _STAMP_MARKER in text:
            return i
    return None


def _extract_stamp_positions(pdf_path: str, page_idx: int) -> list[tuple[float, float]]:
    """Extract actual STAMP positions from PDF content stream.

    Parses the PDF content stream to find transformation matrices (cm operators)
    that precede STAMP_ text. Returns list of (x, y) positions in PDF points
    with y measured from page bottom.
    """
    reader = pypdf.PdfReader(pdf_path)
    page = reader.pages[page_idx]

    # Get content stream
    contents_ref = page.get("/Contents")
    contents = contents_ref.get_object()

    # Handle array of streams or single stream
    # Use isinstance to check for ArrayObject, not just hasattr(__iter__)
    from pypdf.generic._data_structures import ArrayObject
    if isinstance(contents, ArrayObject):
        streams = [item.get_object() for item in contents]
    else:
        streams = [contents]

    # Combine all stream data
    combined_text = ""
    for stream in streams:
        try:
            data = stream.get_data()
            combined_text += data.decode("latin-1", errors="replace")
        except Exception:
            pass

    positions: list[tuple[float, float]] = []

    # Find each STAMP_ occurrence and look backwards for the cm transformation
    for match in re.finditer(r"STAMP_", combined_text):
        idx = match.start()
        chunk = combined_text[max(0, idx - 400) : idx]

        # Find the last transformation matrix before STAMP_
        cm_matches = list(re.finditer(r"1 0 0 1 ([\d.]+) ([\d.]+) cm", chunk))
        if cm_matches:
            last_cm = cm_matches[-1]
            x = float(last_cm.group(1))
            y = float(last_cm.group(2))
            positions.append((x, y))

    return positions


def _calculate_stamp_positions(page_width: float, page_height: float) -> list[tuple[float, float]]:
    """Calculate stamp positions based on the warm-academic theme layout.

    The 质控校验表 starts after an H2 heading at ~30% down the page.
    The three 合格 rows are at data rows 9, 10, 11 (0-indexed).
    Returns list of (x, y) tuples for badge centers.
    """
    # Warm-academic theme margins (pt)
    lm = 25 * 2.8346  # 70.87 pt
    tm = 28 * 2.8346  # 79.37 pt
    bm = 25 * 2.8346  # 70.87 pt
    body_h = page_height - tm - bm
    body_w = page_width - lm - (22 * 2.8346)

    # H2 section: spacer(30% body_h) + heading(~26pt) + rule(~25pt)
    y_table_top = page_height - tm - body_h * 0.30 - 26 - 25

    # Table header row ~18pt, data rows ~17pt each
    header_h = 18
    row_h = 17

    # Stamp rows are at indices 9, 10, 11 (0-indexed data rows)
    stamp_rows = [9, 10, 11]

    # Column layout: 2-column table, "内容" column is ~65% width
    col1_w = body_w * 0.35
    col2_w = body_w * 0.65
    col2_center_x = lm + col1_w + col2_w * 0.45  # slightly left of center for visual balance

    positions = []
    for row_idx in stamp_rows:
        y = y_table_top - header_h - row_idx * row_h - row_h / 2
        positions.append((col2_center_x, y))

    return positions


def _create_stamp_overlay(page_width: float, page_height: float, positions: list[tuple[float, float]]) -> bytes:
    """Create a single-page PDF overlay with green badge stamps at given positions.

    Uses reportlab to draw green rounded rectangles with white "合格" text.
    """
    from reportlab.lib.colors import Color
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # Register CJK font for Chinese text in badge
    cjk_candidates = [
        ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", None),
        ("/System/Library/Fonts/Supplemental/Songti.ttc", 0),
        ("/System/Library/Fonts/PingFang.ttc", 0),
        ("C:/Windows/Fonts/msyh.ttc", None),
    ]
    cjk_font_name = "Helvetica"  # fallback
    for font_path, subfont_idx in cjk_candidates:
        if Path(font_path).exists():
            try:
                if subfont_idx is not None:
                    pdfmetrics.registerFont(TTFont("StampCJK", font_path, subfontIndex=subfont_idx))
                else:
                    pdfmetrics.registerFont(TTFont("StampCJK", font_path))
                cjk_font_name = "StampCJK"
                break
            except Exception:
                continue

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_width, page_height))

    green = Color(*_BADGE_COLOR)

    for cx, cy in positions:
        x = cx - _BADGE_WIDTH / 2
        y = cy - _BADGE_HEIGHT / 2

        # White background to cover original STAMP_合格 text
        c.setFillColor(Color(1, 1, 1))
        c.setStrokeColor(Color(1, 1, 1))
        c.rect(x - 2, y - 1, _BADGE_WIDTH + 4, _BADGE_HEIGHT + 2, fill=1, stroke=0)

        # Green rounded rectangle background
        c.setFillColor(green)
        c.setStrokeColor(green)
        c.roundRect(x, y, _BADGE_WIDTH, _BADGE_HEIGHT, _BADGE_RADIUS, fill=1, stroke=0)

        # White "合格" text centered in the badge using CJK font
        c.setFillColor(Color(1, 1, 1))
        c.setFont(cjk_font_name, 8)
        c.drawCentredString(cx, cy - 3, "\u5408\u683c")  # 合格

    c.save()
    return buf.getvalue()


def _add_green_stamps(pdf_path: str) -> None:
    """Post-process the generated PDF to add green badge stamps over STAMP markers.

    Uses reportlab to create an overlay with CJK text, then merges it using pypdf.
    """
    reader = pypdf.PdfReader(pdf_path)
    writer = pypdf.PdfWriter()

    stamp_page_idx = _find_stamp_page(pdf_path)

    for i, page in enumerate(reader.pages):
        added_page = writer.add_page(page)
        if i == stamp_page_idx:
            try:
                _apply_stamp_overlay(added_page, pdf_path)
            except Exception:
                pass  # Skip badge on error

    with open(pdf_path, "wb") as f:
        writer.write(f)


def _apply_stamp_overlay(page, pdf_path: str) -> None:
    """Merge the badge overlay onto the page using pypdf merge_page."""
    page_box = page.mediabox
    pw = float(page_box.width)
    ph = float(page_box.height)

    # Extract actual STAMP positions from PDF content stream
    stamp_positions = _extract_stamp_positions(pdf_path, _find_stamp_page(pdf_path))

    if not stamp_positions:
        # Fallback to calculated positions
        stamp_positions = _calculate_stamp_positions(pw, ph)

    # Badge positioning: place badge at STAMP text position so white background covers it
    # Badge center = (stamp_x, stamp_y + badge_height/2)
    badge_height_half = _BADGE_HEIGHT / 2

    positions = []
    for stamp_x, stamp_y in stamp_positions:
        # stamp_x, stamp_y are PDF coordinates (from bottom-left origin)
        # Badge center at same X as text, slightly above baseline
        badge_x = stamp_x
        badge_y = stamp_y + badge_height_half
        positions.append((badge_x, badge_y))

    overlay_data = _create_stamp_overlay(pw, ph, positions)

    import io
    from pypdf.generic import ArrayObject, FloatObject
    overlay_reader = pypdf.PdfReader(io.BytesIO(overlay_data))
    # Use identity transformation to place overlay at (0,0)
    identity = ArrayObject([
        FloatObject(1), FloatObject(0), FloatObject(0),
        FloatObject(1), FloatObject(0), FloatObject(0)
    ])
    page.merge_transformed_page(overlay_reader.pages[0], identity)


def _apply_stamp_badges(page, writer) -> None:
    """Draw green badge rectangles on the stamp page using pypdf writer."""
    page_box = page.mediabox
    pw = float(page_box.width)
    ph = float(page_box.height)

    positions = _calculate_stamp_positions(pw, ph)
    green_r, green_g, green_b = _BADGE_COLOR

    # Build raw PDF content stream operators
    ops = b"q\n"  # save graphics state
    for cx, cy in positions:
        x = cx - _BADGE_WIDTH / 2
        y = cy - _BADGE_HEIGHT / 2
        # White background to cover STAMP text
        ops += f"1 1 1 rg {x - 6:.1f} {y - 2:.1f} {_BADGE_WIDTH + 12:.1f} {_BADGE_HEIGHT + 4:.1f} re f\n".encode("latin-1")
        # Green badge rectangle
        ops += f"{green_r:.2f} {green_g:.2f} {green_b:.2f} rg {x:.1f} {y:.1f} {_BADGE_WIDTH:.1f} {_BADGE_HEIGHT:.1f} re f\n".encode("latin-1")
    ops += b"Q\n"  # restore graphics state

    # Use pypdf's ContentStream to add the badge operators
    from pypdf.generic import ContentStream as CS
    stamp_cs = CS(None, writer)
    stamp_cs.set_data(ops)

    # Get existing contents
    existing = page.get("/Contents")
    from pypdf.generic import ArrayObject
    if existing is None:
        page[NameObject("/Contents")] = stamp_cs
    elif isinstance(existing, ArrayObject):
        existing.append(stamp_cs)
    else:
        arr = ArrayObject([existing, stamp_cs])
        page[NameObject("/Contents")] = arr


def export_pdf(
    markdown_path: str,
    pdf_path: str,
    title: str,
    author: str,
    patient_name: str = "",
    report_date: str = "",
    institution_name: str = "",
    cover_patient: str = "",
) -> None:
    command = build_md2pdf_command(
        markdown_path, pdf_path, title, author,
        patient_name=patient_name,
        report_date=report_date,
        institution_name=institution_name,
        cover_patient=cover_patient,
    )
    # Use current environment for subprocess
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "md2pdf export failed")

    # Badge stamps are now embedded as images in markdown - no post-processing needed
    # _add_green_stamps(pdf_path)  # disabled: using image badges instead
