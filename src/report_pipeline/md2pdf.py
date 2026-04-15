#!/usr/bin/env python3
"""
md2pdf — Convert Markdown to professionally typeset PDF.

Features:
  - CJK/Latin mixed text with automatic font switching
  - Fenced code blocks with preserved indentation and line breaks
  - Markdown tables with smart proportional column widths
  - Cover page, clickable TOC, PDF bookmarks, page numbers
  - Frontispiece (full-page image after cover) and back cover (banner branding)
  - Configurable color themes
  - Watermark support
  - Running header with report title + chapter name
  - Footer with author/brand, page number, date

Usage:
  python md2pdf.py --input report.md --output report.pdf --title "My Report"

Dependencies:
  pip install reportlab --break-system-packages

This file is the CLI entry-point and backward-compatibility re-export layer.
All implementation has been split into focused sub-modules:

  pdf_fonts.py     — Cross-platform font discovery and registration
  pdf_themes.py    — Color themes and layout presets
  pdf_utils.py     — CJK utilities, image helpers, inline Markdown
  pdf_flowables.py — Custom ReportLab Flowable components
  pdf_builder.py   — PDFBuilder class (core engine)
"""

import re
import os
import sys
import argparse
from datetime import date
from reportlab.lib.pagesizes import A4, LETTER

# ── Import strategy: support both `python -m report_pipeline.md2pdf` (package
#    mode, relative imports work) and `python md2pdf.py` (script mode, need
#    to fall back to absolute imports by ensuring parent dir is on sys.path). ─
def _ensure_importable():
    """Add the directory containing the report_pipeline package to sys.path."""
    this_dir = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(this_dir)
    if parent not in sys.path:
        sys.path.insert(0, parent)

_ensure_importable()

# Always use absolute imports so the module works correctly regardless of how
# it is invoked (as script or as part of the package).
from report_pipeline.pdf_fonts import register_fonts, _FONT_CANDIDATES, _find_font          # noqa: F401
from report_pipeline.pdf_themes import THEMES, load_theme, _DEFAULT_LAYOUT                  # noqa: F401
from report_pipeline.pdf_utils import (                                                       # noqa: F401
    _is_cjk, _font_wrap,
    _draw_mixed, _measure_mixed, _draw_mixed_wrap, _draw_mixed_segs,
    _flatten_transparency,
    esc, esc_code, md_inline,
)
from report_pipeline.pdf_flowables import (                                                   # noqa: F401
    _anchor_counter, _outline_level, _cur_chapter,
    MedicalResultFlowable, BadgeFlowable, RiskBarFlowable,
    ChapterMark, HRule, HRuleCentered, ClayDot, LeftBorderParagraph,
    TocEntry,
)
from report_pipeline.pdf_builder import PDFBuilder                                            # noqa: F401


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="md2pdf — Markdown to Professional PDF")
    parser.add_argument("--input", "-i", required=True, help="Input markdown file")
    parser.add_argument("--output", "-o", default="output.pdf", help="Output PDF path")
    parser.add_argument("--title", default="", help="Cover page title")
    parser.add_argument("--subtitle", default="", help="Cover page subtitle")
    parser.add_argument("--author", default="", help="Author name")
    parser.add_argument("--date", default=str(date.today()), help="Date string")
    parser.add_argument("--version", default="", help="Version string on cover")
    parser.add_argument("--watermark", default="", help="Watermark text (empty = none)")
    parser.add_argument("--theme", default="warm-academic", help="Theme name")
    parser.add_argument("--theme-file", default=None, help="Custom theme JSON file path")
    parser.add_argument("--cover", default=True, type=lambda x: x.lower() != 'false', help="Generate cover page")
    parser.add_argument("--toc", default=True, type=lambda x: x.lower() != 'false', help="Generate TOC")
    parser.add_argument("--page-size", default="A4", choices=["A4","Letter"], help="Page size")
    parser.add_argument("--frontispiece", default="", help="Path to full-page image after cover")
    parser.add_argument("--banner", default="", help="Path to back cover banner image")
    parser.add_argument("--header-title", default="", help="Report title shown in page header (left)")
    parser.add_argument("--footer-left", default="", help="Brand/author text in footer (left)")
    parser.add_argument("--header-right", default="", help="Text shown in page header (right)")
    parser.add_argument("--cover-patient", default="", help="Patient info line on cover (e.g. '张三  男  56岁')")
    parser.add_argument("--stats-line", default="", help="Stats line on cover (e.g. '1,884 files ...')")
    parser.add_argument("--stats-line2", default="", help="Second stats line on cover")
    parser.add_argument("--edition-line", default="", help="Edition line at cover bottom")
    parser.add_argument("--disclaimer", default="", help="Back cover disclaimer text")
    parser.add_argument("--copyright", default="", help="Back cover copyright text")
    parser.add_argument("--code-max-lines", default=30, type=int, help="Max lines per code block before truncation")
    parser.add_argument("--base-dir", default="", help="Base directory for resolving relative image paths")
    parser.add_argument("--logo", default="", help="Path to company logo")
    parser.add_argument("--first-h1-inline", default=False, type=lambda x: x.lower() == 'true', help="Render first H1 inline without divider page")
    parser.add_argument("--h2-top-ratio", default=0.05, type=float, help="Top spacer ratio for H2 headings (0.0-1.0)")
    args = parser.parse_args()

    with open(args.input, encoding='utf-8') as f:
        md_text = f.read()

    # Extract title from first H1 if not provided
    title = args.title
    if not title:
        m = re.search(r'^# (.+)$', md_text, re.MULTILINE)
        title = m.group(1).strip() if m else "Document"

    theme = load_theme(args.theme, args.theme_file)
    a = theme['accent']
    accent_hex = f"#{int(a.red*255):02x}{int(a.green*255):02x}{int(a.blue*255):02x}" \
        if hasattr(a, 'red') else "#CC785C"

    config = {
        "title": title,
        "subtitle": args.subtitle,
        "author": args.author,
        "date": args.date,
        "version": args.version,
        "watermark": args.watermark,
        "theme": theme,
        "accent_hex": accent_hex,
        "cover": args.cover,
        "toc": args.toc,
        "page_size": A4 if args.page_size == "A4" else LETTER,
        "frontispiece": args.frontispiece,
        "banner": args.banner,
        "header_title": args.header_title,
        "footer_left": args.footer_left or args.author,
        "header_right": args.header_right,
        "cover_patient": args.cover_patient,
        "stats_line": args.stats_line,
        "stats_line2": args.stats_line2,
        "edition_line": args.edition_line,
        "disclaimer": args.disclaimer,
        "copyright": args.copyright,
        "code_max_lines": args.code_max_lines,
        "base_dir": args.base_dir,
        "logo": args.logo,
        "first_h1_inline": args.first_h1_inline,
        "h2_top_ratio": args.h2_top_ratio,
    }

    builder = PDFBuilder(config)
    builder.build(md_text, args.output)


if __name__ == "__main__":
    main()
