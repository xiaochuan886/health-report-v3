"""
pdf_builder.py — Core PDF builder class for md2pdf.

PDFBuilder orchestrates:
  - Style sheet construction (body, headings, TOC, tables, code)
  - Page template drawing (cover, frontispiece, normal pages, TOC, back cover)
  - Markdown parsing → ReportLab story elements
  - Table parsing with configurable column widths
  - PDF document assembly and output
"""

import re
import os
import sys
from datetime import date

from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.units import mm
from reportlab.lib.colors import Color, HexColor, black, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak,
    Table, TableStyle, NextPageTemplate, Flowable, Image as RLImage,
    KeepTogether
)
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics

from report_pipeline.pdf_fonts import register_fonts
from report_pipeline.pdf_utils import (
    _is_cjk, _font_wrap, _draw_mixed, _draw_mixed_segs,
    _flatten_transparency, esc, esc_code, md_inline
)
from report_pipeline.pdf_flowables import (
    _cur_chapter, _anchor_counter, _outline_level,
    MedicalResultFlowable, BadgeFlowable, RiskBarFlowable,
    ChapterMark, HRule, HRuleCentered, ClayDot, LeftBorderParagraph,
    TocEntry
)


class PDFBuilder:
    """Convert a Markdown string to a professionally typeset PDF via ReportLab."""

    def __init__(self, config):
        self.cfg = config
        self.T = config["theme"]   # resolved theme colors
        self.L = self.T["layout"]  # layout parameters
        self.page_w, self.page_h = config["page_size"]
        lm, rm, tm, bm = self.L["margins"]
        self.lm, self.rm, self.tm, self.bm = lm*mm, rm*mm, tm*mm, bm*mm
        self.body_w = self.page_w - self.lm - self.rm
        self.body_h = self.page_h - self.tm - self.bm
        self.accent_hex = config.get("accent_hex", "#CC785C")
        self._current_part_title = ""
        self._current_body_cjk_font = "CJK"
        self.ST = self._build_styles()

    @staticmethod
    def _norm_weight(weight, fallback=400):
        try:
            w = int(weight)
            if w < 100:
                return 100
            if w > 900:
                return 900
            return (w // 100) * 100
        except Exception:
            return fallback

    def _cjk_font_by_weight(self, weight, fallback="CJK"):
        w = self._norm_weight(weight, 400)
        alias = f"CJK{w}"
        return alias if alias in pdfmetrics.getRegisteredFontNames() else fallback

    def _style_cjk_font(self, style_key):
        L = self.L
        mapping = {
            "part": L.get("part_cjk_weight", 700),
            "chapter": L.get("chapter_cjk_weight", 700),
            "h3": L.get("h3_cjk_weight", 600),
            "body": L.get("body_cjk_weight", 400),
            "bullet": L.get("bullet_cjk_weight", L.get("body_cjk_weight", 400)),
            "body_indent": L.get("body_indent_cjk_weight", L.get("body_cjk_weight", 400)),
            "table_th": L.get("table_header_cjk_weight", 700),
            "table_tc": L.get("table_cell_cjk_weight", L.get("body_cjk_weight", 400)),
        }
        return self._cjk_font_by_weight(mapping.get(style_key, 400))

    def _section_body_cjk_font(self, part_title):
        overrides = self.L.get("section_body_cjk_weight_overrides", {}) or {}
        for key, weight in overrides.items():
            if part_title == key or (key and key in part_title):
                return self._cjk_font_by_weight(weight, fallback=self._style_cjk_font("body"))
        return self._style_cjk_font("body")

    def _cover_title_cjk_font(self):
        return self._cjk_font_by_weight(800, fallback="CJK")

    # ── Style sheet ─────────────────────────────────────────────────────────
    def _build_styles(self):
        T = self.T; L = self.L
        s = {}
        bf = L["body_font"]  # "Serif" or "Sans"
        bs, bl = L["body_size"], L["body_leading"]
        h_align = TA_CENTER if L["heading_align"] == "center" else TA_LEFT
        s['part'] = ParagraphStyle('Part', fontName=f"{bf}Bold", fontSize=L["h1_size"],
            leading=L["h1_size"]+10, textColor=T["ink"], alignment=h_align,
            spaceBefore=0, spaceAfter=0)
        s['chapter'] = ParagraphStyle('Ch', fontName=f"{bf}Bold", fontSize=L["h2_size"],
            leading=L["h2_size"]+8, textColor=T["ink"], alignment=h_align,
            spaceBefore=0, spaceAfter=0)
        s['h3'] = ParagraphStyle('H3', fontName="SansBold", fontSize=L["h3_size"],
            leading=L["h3_size"]+5, textColor=T["accent"], alignment=TA_LEFT,
            spaceBefore=10, spaceAfter=4)
        s['body'] = ParagraphStyle('Body', fontName=bf, fontSize=bs, leading=bl,
            textColor=T["ink"], alignment=TA_JUSTIFY, spaceBefore=2, spaceAfter=4,
            wordWrap='CJK')
        s['body_indent'] = ParagraphStyle('BI', parent=s['body'],
            leftIndent=14, rightIndent=14, textColor=T["ink_faded"],
            borderColor=T["accent"], borderWidth=0, borderPadding=4)
        s['bullet'] = ParagraphStyle('Bul', fontName=bf, fontSize=bs, leading=bl,
            textColor=T["ink"], alignment=TA_LEFT, spaceBefore=1, spaceAfter=1,
            leftIndent=18, bulletIndent=6, wordWrap='CJK')
        # Code block: "bg" = background fill, "border" = left accent line (no bg)
        self._code_style_type = L["code_style"]
        if L["code_style"] == "border":
            s['code'] = ParagraphStyle('Code', fontName="Mono", fontSize=7.5, leading=10.5,
                textColor=HexColor("#3D3D3A"), alignment=TA_LEFT, spaceBefore=4, spaceAfter=4,
                leftIndent=14, rightIndent=8, backColor=None,
                borderColor=None, borderWidth=0, borderPadding=6)
        else:
            s['code'] = ParagraphStyle('Code', fontName="Mono", fontSize=7.5, leading=10.5,
                textColor=HexColor("#3D3D3A"), alignment=TA_LEFT, spaceBefore=4, spaceAfter=4,
                leftIndent=8, rightIndent=8, backColor=T["canvas_sec"],
                borderColor=T["border"], borderWidth=0.5, borderPadding=6)
        s['toc1'] = ParagraphStyle('T1', fontName=f"{bf}Bold", fontSize=12, leading=20,
            textColor=T["ink"], leftIndent=0, spaceBefore=6, spaceAfter=2)
        s['toc2'] = ParagraphStyle('T2', fontName="Sans", fontSize=10, leading=16,
            textColor=T["ink_faded"], leftIndent=16, spaceBefore=1, spaceAfter=1)
        s['th'] = ParagraphStyle('TH', fontName="SansBold", fontSize=8.5, leading=12,
            textColor=white, alignment=TA_LEFT)
        s['tc'] = ParagraphStyle('TC', fontName="Sans", fontSize=8, leading=11,
            textColor=T["ink"], alignment=TA_LEFT)
        return s

    # ── Page callbacks ───────────────────────────────────────────────────────
    def _draw_bg(self, c):
        c.setFillColor(self.T["canvas"])
        c.rect(0, 0, self.page_w, self.page_h, fill=1, stroke=0)

    def _cover_page(self, c, doc):
        c.saveState(); self._draw_bg(c)
        T = self.T; cx = self.page_w / 2
        cover = self.L["cover_style"]

        if cover == "left-aligned":
            self._cover_left_aligned(c, T, cx)
        elif cover == "minimal":
            self._cover_minimal(c, T, cx)
        else:
            self._cover_centered(c, T, cx)

        c.restoreState()

    def _cover_centered(self, c, T, cx):
        """Classic centered cover with accent bars and rule."""
        # Top accent bar
        c.setFillColor(T["accent"])
        c.rect(0, self.page_h - 3*mm, self.page_w, 3*mm, fill=1, stroke=0)

        # Draw logo if provided
        logo = self.cfg.get("logo", "")
        if logo and os.path.exists(logo):
            try:
                # Resolve relative path
                base_dir = self.cfg.get("base_dir", "")
                if base_dir and not os.path.isabs(logo):
                    logo = os.path.join(base_dir, logo)

                img_src = _flatten_transparency(logo)
                logo_w = 60*mm
                c.drawImage(img_src, cx - logo_w/2, self.page_h - 50*mm, width=logo_w, height=logo_w/3, preserveAspectRatio=True, mask='auto', anchor='c')
            except Exception as e:
                print(f"Warning: Cover logo draw failed: {e}", file=sys.stderr)

        title_y = self.page_h * 0.62
        c.setFillColor(T["ink"])
        btm = _draw_mixed(
            c, cx, title_y, self.cfg.get("title", "Document"), 38,
            anchor="center", max_w=self.page_w - 40*mm,
            cjk_font=self._cover_title_cjk_font(), latin_font="SansBold"
        )

        ver = self.cfg.get("version", "")
        if ver:
            c.setFillColor(T["accent"]); c.setFont("Sans", 13)
            c.drawCentredString(cx, btm - 30, ver)

        rule_y = btm - 52
        c.setStrokeColor(T["accent"]); c.setLineWidth(1.5)
        c.line(cx - 17*mm, rule_y, cx + 17*mm, rule_y)

        sub = self.cfg.get("subtitle", "")
        sub_segs = self.cfg.get("subtitle_segs")
        if sub_segs:
            c.setFillColor(T["ink_faded"]); _draw_mixed_segs(c, cx, rule_y - 32, sub_segs)
        elif sub:
            c.setFillColor(T["ink"]); _draw_mixed(c, cx, rule_y - 32, sub, 20, anchor="center")

        stats = self.cfg.get("stats_line", "")
        stats2 = self.cfg.get("stats_line2", "")
        if stats or stats2:
            c.setFillColor(T["ink_faded"]); stats_y = rule_y - 72
            if stats: _draw_mixed(c, cx, stats_y, stats, 9.5, anchor="center")
            if stats2: _draw_mixed(c, cx, stats_y - 18, stats2, 9.5, anchor="center")

        c.setStrokeColor(T["border"]); c.setLineWidth(0.5)
        c.line(self.lm + 20*mm, 52*mm, self.page_w - self.rm - 20*mm, 52*mm)

        author = self.cfg.get("author", "")
        if author:
            c.setFillColor(T["ink_faded"]); _draw_mixed(c, cx, 38*mm, author, 10, anchor="center")

        cover_patient = self.cfg.get("cover_patient", "")
        if cover_patient:
            c.setFillColor(T["ink"]); _draw_mixed(c, cx, 30*mm, cover_patient, 11, anchor="center")

        dt = self.cfg.get("date", str(date.today()))
        c.setFillColor(T["ink_faded"]); _draw_mixed(c, cx, 22*mm, dt, 9, anchor="center")

        edition = self.cfg.get("edition_line", "")
        if edition:
            c.setFillColor(T["ink_faded"]); _draw_mixed(c, cx, 20*mm, edition, 7.5, anchor="center")

        c.setFillColor(T["accent"])
        c.rect(0, 0, self.page_w, 3*mm, fill=1, stroke=0)

    def _cover_left_aligned(self, c, T, cx):
        """Modern left-aligned cover (GitHub/IEEE style)."""
        # Thick left accent stripe
        c.setFillColor(T["accent"])
        c.rect(0, 0, 6*mm, self.page_h, fill=1, stroke=0)

        lx = 25*mm  # left text x
        title_y = self.page_h * 0.58
        c.setFillColor(T["ink"])
        btm = _draw_mixed(
            c, lx, title_y, self.cfg.get("title", "Document"), 34,
            anchor="left", max_w=self.page_w - lx - 20*mm,
            cjk_font=self._cover_title_cjk_font(), latin_font="SansBold"
        )

        ver = self.cfg.get("version", "")
        if ver:
            c.setFillColor(T["accent"]); c.setFont("Sans", 12)
            c.drawString(lx, btm - 28, ver)

        # Accent underline
        c.setStrokeColor(T["accent"]); c.setLineWidth(2)
        c.line(lx, btm - 42, lx + 50*mm, btm - 42)

        sub = self.cfg.get("subtitle", "")
        sub_segs = self.cfg.get("subtitle_segs")
        if sub_segs:
            c.setFillColor(T["ink_faded"]); _draw_mixed_segs(c, lx + 40*mm, btm - 62, sub_segs)
        elif sub:
            c.setFillColor(T["ink_faded"]); _draw_mixed(c, lx, btm - 62, sub, 16, anchor="left")

        stats = self.cfg.get("stats_line", "")
        stats2 = self.cfg.get("stats_line2", "")
        if stats or stats2:
            c.setFillColor(T["ink_faded"]); stats_y = btm - 100
            if stats: _draw_mixed(c, lx, stats_y, stats, 9, anchor="left")
            if stats2: _draw_mixed(c, lx, stats_y - 16, stats2, 9, anchor="left")

        # Bottom left info block
        author = self.cfg.get("author", "")
        if author:
            c.setFillColor(T["ink_faded"]); _draw_mixed(c, lx, 38*mm, author, 10, anchor="left")
        dt = self.cfg.get("date", str(date.today()))
        c.setFillColor(T["ink_faded"]); _draw_mixed(c, lx, 28*mm, dt, 9, anchor="left")

        edition = self.cfg.get("edition_line", "")
        if edition:
            c.setFillColor(T["ink_faded"]); _draw_mixed(c, lx, 20*mm, edition, 7.5, anchor="left")

    def _cover_minimal(self, c, T, cx):
        """Minimal cover (Tufte/ink-wash style) — lots of whitespace, no bars."""
        title_y = self.page_h * 0.50
        c.setFillColor(T["ink"])
        btm = _draw_mixed(
            c, cx, title_y, self.cfg.get("title", "Document"), 32,
            anchor="center", max_w=self.page_w - 50*mm,
            cjk_font=self._cover_title_cjk_font(), latin_font="SansBold"
        )

        sub = self.cfg.get("subtitle", "")
        sub_segs = self.cfg.get("subtitle_segs")
        if sub_segs:
            c.setFillColor(T["ink_faded"]); _draw_mixed_segs(c, cx, btm - 36, sub_segs)
        elif sub:
            c.setFillColor(T["ink_faded"]); _draw_mixed(c, cx, btm - 36, sub, 16, anchor="center")

        ver = self.cfg.get("version", "")
        if ver:
            c.setFillColor(T["ink_faded"]); c.setFont("Sans", 10)
            c.drawCentredString(cx, btm - 60, ver)

        # Simple thin rule
        c.setStrokeColor(T["border"]); c.setLineWidth(0.3)
        c.line(cx - 25*mm, btm - 75, cx + 25*mm, btm - 75)

        author = self.cfg.get("author", "")
        if author:
            c.setFillColor(T["ink_faded"]); _draw_mixed(c, cx, 35*mm, author, 10, anchor="center")
        dt = self.cfg.get("date", str(date.today()))
        c.setFillColor(T["ink_faded"]); _draw_mixed(c, cx, 25*mm, dt, 9, anchor="center")

    def _frontispiece_page(self, c, doc):
        """Full-page image page after cover."""
        c.saveState(); self._draw_bg(c)
        fp = self.cfg.get("frontispiece", "")
        if fp and os.path.exists(fp):
            margin = 18*mm
            avail_w = self.page_w - 2 * margin
            avail_h = self.page_h - 2 * margin
            try:
                # Resolve relative path using base_dir
                base_dir = self.cfg.get("base_dir", "")
                if base_dir and not os.path.isabs(fp):
                    fp = os.path.join(base_dir, fp)

                img_src = _flatten_transparency(fp)
                c.drawImage(img_src, margin, margin, width=avail_w, height=avail_h,
                            preserveAspectRatio=True, anchor='c', mask='auto')
            except Exception:
                pass
        c.restoreState()

    def _backcover_page(self, c, doc):
        """Back cover with banner branding."""
        c.saveState(); self._draw_bg(c)
        T = self.T; cx = self.page_w / 2

        # Top accent
        c.setFillColor(T["accent"])
        c.rect(0, self.page_h - 3*mm, self.page_w, 3*mm, fill=1, stroke=0)

        # Banner image — centered
        banner = self.cfg.get("banner", "")
        if banner and os.path.exists(banner):
            cy = self.page_h / 2
            banner_w = 150*mm
            banner_h = banner_w / 2.57
            banner_x = (self.page_w - banner_w) / 2
            banner_y = cy - banner_h / 2 + 15*mm
            try:
                # Resolve relative path
                base_dir = self.cfg.get("base_dir", "")
                if base_dir and not os.path.isabs(banner):
                    banner = os.path.join(base_dir, banner)

                img_src = _flatten_transparency(banner)
                c.drawImage(img_src, banner_x, banner_y, width=banner_w,
                            height=banner_h, preserveAspectRatio=True, mask='auto')
            except Exception:
                pass

        # Bottom disclaimer
        disclaimer = self.cfg.get("disclaimer", "")
        if disclaimer:
            c.setFillColor(T["ink_faded"])
            _draw_mixed(c, cx, 32*mm, disclaimer, 8.5, anchor="center")

        # Copyright
        copyright_text = self.cfg.get("copyright", "")
        if copyright_text:
            c.setFillColor(T["ink_faded"])
            _draw_mixed(c, cx, 20*mm, copyright_text, 8.5, anchor="center")

        # Bottom accent
        c.setFillColor(T["accent"])
        c.rect(0, 0, self.page_w, 3*mm, fill=1, stroke=0)

        c.restoreState()

    def _draw_page_decoration(self, c):
        """Draw theme-specific page decorations visible even at thumbnail size."""
        T = self.T; deco = self.L.get("page_decoration", "none")
        if deco == "top-bar":
            # Thin accent bar at very top of page
            c.setFillColor(T["accent"])
            c.rect(0, self.page_h - 2.5*mm, self.page_w, 2.5*mm, fill=1, stroke=0)
        elif deco == "left-stripe":
            # Thick colored stripe on left edge
            c.setFillColor(T["accent"])
            c.rect(0, 0, 5*mm, self.page_h, fill=1, stroke=0)
        elif deco == "side-rule":
            # Thin vertical rule on left side (Tufte-style margin line)
            c.setStrokeColor(T["border"]); c.setLineWidth(0.4)
            c.line(self.lm - 5*mm, self.bm, self.lm - 5*mm, self.page_h - self.tm + 5*mm)
        elif deco == "corner-marks":
            # Decorative corner brackets
            c.setStrokeColor(T["accent"]); c.setLineWidth(0.8)
            m = 12*mm; clen = 12*mm
            # Top-left
            c.line(m, self.page_h - m, m + clen, self.page_h - m)
            c.line(m, self.page_h - m, m, self.page_h - m - clen)
            # Top-right
            c.line(self.page_w - m, self.page_h - m, self.page_w - m - clen, self.page_h - m)
            c.line(self.page_w - m, self.page_h - m, self.page_w - m, self.page_h - m - clen)
            # Bottom-left
            c.line(m, m, m + clen, m)
            c.line(m, m, m, m + clen)
            # Bottom-right
            c.line(self.page_w - m, m, self.page_w - m - clen, m)
            c.line(self.page_w - m, m, self.page_w - m, m + clen)
        elif deco == "top-band":
            # Wide accent band at top (IEEE-style)
            c.setFillColor(T["accent"])
            c.rect(0, self.page_h - 8*mm, self.page_w, 8*mm, fill=1, stroke=0)
            # White text header inside band
            header_title = self.cfg.get("header_title", "")
            if header_title:
                c.setFillColor(white)
                _draw_mixed(c, self.lm, self.page_h - 6*mm, header_title, 7.5)
            header_right = self.cfg.get("header_right", "")
            if header_right:
                c.setFillColor(white)
                _draw_mixed(c, self.page_w - self.rm, self.page_h - 6*mm, header_right, 7.5, anchor="right")
        elif deco == "double-rule":
            # Double horizontal rules at top and bottom (elegant book style)
            c.setStrokeColor(T["accent"]); c.setLineWidth(0.6)
            y_top = self.page_h - 14*mm
            c.line(self.lm, y_top, self.page_w - self.rm, y_top)
            c.line(self.lm, y_top - 2*mm, self.page_w - self.rm, y_top - 2*mm)
            y_bot = self.bm - 4*mm
            c.line(self.lm, y_bot, self.page_w - self.rm, y_bot)
            c.line(self.lm, y_bot + 2*mm, self.page_w - self.rm, y_bot + 2*mm)

    def _normal_page(self, c, doc):
        self._draw_bg(c); pg = c.getPageNumber()
        c.saveState()
        T = self.T; hs = self.L["header_style"]

        # Page decoration (drawn first, behind content)
        self._draw_page_decoration(c)

        # Watermark
        wm = self.cfg.get("watermark", "")
        if wm:
            c.setFont("CJK", 52); c.setFillColor(T["wm_color"])
            c.translate(self.page_w/2, self.page_h/2); c.rotate(35)
            for dy in range(-300, 400, 160):
                for dx in range(-400, 500, 220):
                    c.drawCentredString(dx, dy, wm)
            c.rotate(-35); c.translate(-self.page_w/2, -self.page_h/2)

        # Header (skip if top-band decoration already drew header)
        deco = self.L.get("page_decoration", "none")
        if hs == "full" and deco != "top-band":
            c.setStrokeColor(T["border"]); c.setLineWidth(0.5)
            c.line(self.lm, self.page_h - 20*mm, self.page_w - self.rm, self.page_h - 20*mm)
            c.setFillColor(T["ink_faded"])

            logo = self.cfg.get("logo", "")
            title_lx = self.lm
            if logo and os.path.exists(logo):
                try:
                    # Resolve relative path
                    base_dir = self.cfg.get("base_dir", "")
                    if base_dir and not os.path.isabs(logo):
                        logo = os.path.join(base_dir, logo)

                    img_src = _flatten_transparency(logo)
                    c.drawImage(img_src, self.lm, self.page_h - 18*mm, width=20*mm, height=10*mm, preserveAspectRatio=True, anchor='sw', mask='auto')
                    title_lx = self.lm + 25*mm
                except Exception as e:
                    print(f"Warning: Header logo draw failed: {e}", file=sys.stderr)

            header_title = self.cfg.get("header_title", "")
            if header_title:
                _draw_mixed(c, title_lx, self.page_h - 15*mm, header_title, 8)

            header_right = self.cfg.get("header_right", "")
            if header_right:
                _draw_mixed(c, self.page_w - self.rm, self.page_h - 18*mm, header_right, 8, anchor="right")
        elif hs == "minimal" and deco != "top-band":
            c.setFillColor(T["ink_faded"]); c.setFont("Sans", 8)
            c.drawRightString(self.page_w - self.rm, self.page_h - 16*mm, str(pg))

        # Footer (skip line if double-rule decoration already drew it)
        if hs != "none" and deco not in ("double-rule",):
            c.setStrokeColor(T["border"])
            c.line(self.lm, self.bm - 8*mm, self.page_w - self.rm, self.bm - 8*mm)

        # Footer center: page number
        if hs == "full":
            c.setFillColor(T["accent"]); c.setFont("Serif", 9)
            c.drawCentredString(self.page_w/2, self.bm - 16*mm, f"\u2014  {pg}  \u2014")
        elif hs == "minimal":
            c.setFillColor(T["ink_faded"]); c.setFont("Sans", 8)
            c.drawCentredString(self.page_w/2, self.bm - 14*mm, str(pg))
        elif hs == "none":
            c.setFillColor(T["ink_faded"]); c.setFont("Serif", 8)
            c.drawCentredString(self.page_w/2, self.bm - 10*mm, str(pg))

        # Footer left/right
        if hs == "full":
            footer_left = self.cfg.get("footer_left", self.cfg.get("author", ""))
            if footer_left:
                c.setFillColor(T["ink_faded"])
                _draw_mixed(c, self.lm, self.bm - 16*mm, footer_left, 8)
            c.setFillColor(T["ink_faded"])
            _draw_mixed(c, self.page_w - self.rm, self.bm - 16*mm,
                        self.cfg.get("date", str(date.today())), 8, anchor="right")
        c.restoreState()

    def _toc_page(self, c, doc):
        self._draw_bg(c); pg = c.getPageNumber()
        c.saveState()
        T = self.T

        # Header line
        c.setStrokeColor(T["border"]); c.setLineWidth(0.5)
        c.line(self.lm, self.page_h - 20*mm, self.page_w - self.rm, self.page_h - 20*mm)
        c.setFillColor(T["ink_faded"])

        # Header left: logo
        logo = self.cfg.get("logo", "")
        if logo and os.path.exists(logo):
            try:
                base_dir = self.cfg.get("base_dir", "")
                if base_dir and not os.path.isabs(logo):
                    logo = os.path.join(base_dir, logo)
                img_src = _flatten_transparency(logo)
                c.drawImage(img_src, self.lm, self.page_h - 18*mm, width=20*mm, height=10*mm, preserveAspectRatio=True, anchor='sw', mask='auto')
            except Exception as e:
                print(f"Warning: TOC header logo draw failed: {e}", file=sys.stderr)

        # Footer
        c.setStrokeColor(T["border"])
        c.line(self.lm, self.bm - 8*mm, self.page_w - self.rm, self.bm - 8*mm)
        c.setFillColor(T["accent"]); c.setFont("Serif", 9)
        c.drawCentredString(self.page_w/2, self.bm - 16*mm, f"\u2014  {pg}  \u2014")

        # Footer left: report title
        footer_left = self.cfg.get("footer_left", "")
        if footer_left:
            c.setFillColor(T["ink_faded"])
            _draw_mixed(c, self.lm, self.bm - 16*mm, footer_left, 8)

        # Header right: "目  录"
        c.setFont("CJK", 8)
        c.drawRightString(self.page_w - self.rm, self.page_h - 18*mm, "\u76ee  \u5f55")

        c.restoreState()

    # ── Table parser ─────────────────────────────────────────────────────────
    def parse_table(self, lines):
        rows = []
        for l in lines:
            l = l.strip().strip('|')
            rows.append([c.strip() for c in l.split('|')])
        if len(rows) < 2: return None
        header = rows[0]
        data = [r for r in rows[1:] if not all(set(c.strip()) <= set('-: ') for c in r)]
        if not data: return None
        nc = len(header)
        ST = self.ST

        def cell_to_flowable(cell, style):
            """Convert a markdown cell to a Paragraph, Badge, RiskBar, or Image flowable."""
            # Check for risk bar data span first
            riskbar_match = re.search(r'data-riskbar="([^"]+)"', cell)
            if riskbar_match:
                parts = riskbar_match.group(1).split(';;')
                if len(parts) == 3:
                    raw_result, raw_reference, risk_status = parts
                    return RiskBarFlowable(
                        raw_result=raw_result,
                        raw_reference=raw_reference,
                        risk_status=risk_status,
                        width=80,
                        height=16,
                    )

            # Check for result badge data span
            badge_match = re.search(r'data-badge="([^"]+)"', cell)
            if badge_match:
                parts = badge_match.group(1).split(';;')
                if len(parts) >= 4:
                    val, arrow, text, color = parts[:4]
                    show_pill = True
                    if len(parts) >= 5:
                        show_pill = parts[4] == "1"

                    return MedicalResultFlowable(
                        value=val,
                        arrow=arrow,
                        status_text=text,
                        color=color,
                        width=68 if text else 52,
                        height=28 if text else 18,
                        show_pill=show_pill
                    )

            # Check if cell contains 'STAMP_合格' marker (used as fallback for missing badges)
            if cell.strip() == "STAMP_合格":
                return BadgeFlowable(text="合格", width=36, height=15, radius=2)

            # Check if cell contains an image: ![alt](path)
            img_match = re.match(r'^!\[([^\]]*)\]\(([^)]+)\)$', cell.strip())
            if img_match:
                img_path = img_match.group(2)
                # Check if this is a badge image - use vector badge for crisp rendering
                if 'badge' in img_path.lower() or '合格' in img_path:
                    return BadgeFlowable(text="合格", width=36, height=15, radius=2)

                # Resolve relative path using base_dir from config
                base_dir = self.cfg.get("base_dir", "")
                if base_dir and not os.path.isabs(img_path):
                    img_path = os.path.join(base_dir, img_path)
                # Flatten transparency if PNG with alpha
                img_src = _flatten_transparency(img_path)
                try:
                    img = RLImage(img_src, width=36, height=15)
                    return img
                except Exception:
                    # Fallback to text if image fails
                    pass
            cjk_font = self._style_cjk_font("table_th") if style == ST['th'] else self._style_cjk_font("table_tc")
            return Paragraph(md_inline(cell, self.accent_hex, cjk_font=cjk_font), style)

        td = [[cell_to_flowable(h, ST['th']) for h in header]]
        for r in data:
            while len(r) < nc: r.append("")
            td.append([cell_to_flowable(c, ST['tc']) for c in r[:nc]])

        # Check for specific table patterns to apply custom column widths
        header_text = ' '.join(h.strip() for h in header)
        avail = self.body_w - 4*mm

        # Assessment result tables: 指标, 结果, 单位, 参考值, 风险刻度
        if header_text in ['指标 结果 单位 参考值 风险刻度', '指标 结果 单位 参考值 状态']:
            cw = [avail * 0.32, avail * 0.12, avail * 0.12, avail * 0.17, avail * 0.27]
        # Summary tables with reordered columns (Result after Indicator)
        elif header_text == '指标 结果/状态 单位 参考值 关联疾病风险':
            # 5 columns for Cancer Summary
            cw = [avail * 0.34, avail * 0.18, avail * 0.10, avail * 0.15, avail * 0.23]
        elif header_text == '指标 结果/状态 单位 参考值':
            # 4 columns for Cardio and Nutrition Summaries
            cw = [avail * 0.44, avail * 0.20, avail * 0.16, avail * 0.20]
        elif header_text in ['疾病类型 / 判断指标 常见诱发因素 防癌管理建议', '疾病类型 / 风险预警 常见诱因/因素 健康管理建议']:
            # 3 columns for merged cancer and cardio interpretations, first column 30%
            cw = [avail * 0.30, avail * 0.35, avail * 0.35]
        elif header_text == '项目 临床表现 / 具体意义 饮食补充 / 临床应用':
            # 3 columns for Nutrition explanations, first column 25%
            cw = [avail * 0.25, avail * 0.375, avail * 0.375]
        else:
            # Default: proportional width based on content
            max_lens = [max((len(r[ci]) if ci < len(r) else 0) for r in [header]+data) for ci in range(nc)]
            max_lens = [max(m, 2) for m in max_lens]
            total = sum(max_lens)
            cw = [avail * m / total for m in max_lens]
            min_w = 18*mm
            for ci in range(nc):
                if cw[ci] < min_w:
                    deficit = min_w - cw[ci]; cw[ci] = min_w
                    widest = sorted(range(nc), key=lambda x: -cw[x])
                    for oi in widest:
                        if oi != ci: cw[oi] -= deficit; break
        T = self.T
        t = Table(td, colWidths=cw, repeatRows=1)
        ts = [
            ('BACKGROUND',(0,0),(-1,0), T["accent"]),
            ('TEXTCOLOR',(0,0),(-1,0), white),
            ('ROWBACKGROUNDS',(0,1),(-1,-1), [white, T["canvas_sec"]]),
            ('GRID',(0,0),(-1,-1), 0.5, T["border"]),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
            ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
        ]

        # Center align specific columns for result tables (2nd column to last)
        # Match if the header starts with common result column sequence
        if header_text.startswith('指标 结果 单位 参考值'):
            ts.append(('ALIGN', (1, 0), (-1, -1), 'CENTER'))
        elif header_text == '项目 内容':
            ts.append(('ALIGN', (0, 0), (-1, -1), 'LEFT'))

        t.setStyle(TableStyle(ts))
        return t

    # ── Markdown → Story ─────────────────────────────────────────────────────
    @staticmethod
    def _preprocess_md(md):
        """Normalize markdown: split merged headings like '# Part## Chapter'."""
        lines = md.split('\n')
        out = []
        in_code = False
        for line in lines:
            if line.strip().startswith('```'):
                in_code = not in_code
            if in_code:
                out.append(line); continue
            # Split where a non-# char is followed by ## (heading marker)
            # e.g. "# 第一部分：背景与概览## 第1章" or "---## 第2章"
            parts = re.split(r'(?<=[^#\s])\s*(?=#{1,3}\s)', line)
            if len(parts) > 1:
                for p in parts:
                    p = p.strip()
                    if p:
                        out.append(p)
            else:
                out.append(line)
        return '\n'.join(out)

    def parse_md(self, md):
        story, toc = [], []
        md = self._preprocess_md(md)
        lines = md.split('\n')
        i, in_code, code_buf = 0, False, []
        ST = self.ST; ah = self.accent_hex
        self._current_part_title = ""
        self._current_body_cjk_font = self._section_body_cjk_font("")

        def inl(text, style_key="body"):
            cjk_font = self._current_body_cjk_font if style_key in {"body", "bullet", "body_indent"} else self._style_cjk_font(style_key)
            return md_inline(text, ah, cjk_font=cjk_font)

        code_max = self.cfg.get("code_max_lines", 30)
        first_h1_done = False  # Track first H1 for inline rendering
        first_h2_done = False  # Track first H2 for no page break

        while i < len(lines):
            line = lines[i]; stripped = line.strip()

            # Code blocks
            if stripped.startswith('```'):
                if in_code:
                    ct = '\n'.join(code_buf)
                    if ct.strip():
                        cl = ct.split('\n')
                        if len(cl) > code_max:
                            cl = cl[:code_max - 2] + ['  // ... (truncated)']
                            ct = '\n'.join(cl)
                        para = Paragraph(_font_wrap(esc_code(ct)), ST['code'])
                        if self._code_style_type == "border":
                            story.append(LeftBorderParagraph(para, self.T["accent"]))
                        else:
                            story.append(para)
                    code_buf = []; in_code = False
                else: in_code = True; code_buf = []
                i += 1; continue
            if in_code: code_buf.append(line); i += 1; continue
            if stripped in ('---','\\newpage','') or stripped.startswith(('title:','subtitle:','author:','date:')):
                i += 1; continue

            # H1 — Part heading: normal top-aligned heading
            if (re.match(r'^# (第.+部分|附录)', stripped) or \
               (re.match(r'^# .+', stripped) and not stripped.startswith('## '))):
                title = stripped.lstrip('#').strip()
                story.append(PageBreak())
                first_h1_done = True
                self._current_part_title = title
                self._current_body_cjk_font = self._section_body_cjk_font(title)
                cm = ChapterMark(title, level=0); story.append(cm)

                # Normal top spacer instead of centered
                h1_top_ratio = self.cfg.get("h2_top_ratio", 0.05)
                story.append(Spacer(1, self.body_h * h1_top_ratio))

                hdeco = self.L["heading_decoration"]
                story.append(Paragraph(inl(title, "part"), ST['part']))

                if hdeco == "rules":
                    story.append(Spacer(1, 4*mm))
                    story.append(HRuleCentered(self.body_w, 40*mm, 1.2, self.T["accent"]))
                elif hdeco == "underline":
                    story.append(Spacer(1, 4*mm))
                    story.append(HRule(self.body_w, 1.0, self.T["accent"]))
                elif hdeco == "dot":
                    story.append(Spacer(1, 6*mm))
                    story.append(ClayDot(self.body_w, self.T["accent"]))
                toc.append(('part', title, cm.key))
                i += 1; continue

            # H2 — Chapter heading
            if stripped.startswith('## '):
                title = stripped[3:].strip()
                story.append(PageBreak())
                first_h2_done = True
                cm = ChapterMark(title, level=1); story.append(cm)
                hdeco = self.L["heading_decoration"]
                # Use configurable top spacer (default 5% for health reports)
                h2_top_ratio = self.cfg.get("h2_top_ratio", 0.05)
                story.append(Spacer(1, self.body_h * h2_top_ratio))
                story.append(Paragraph(inl(title, "chapter"), ST['chapter']))
                if hdeco == "rules":
                    story.append(Spacer(1, 5*mm))
                    story.append(HRuleCentered(self.body_w, 35*mm, 1.2, self.T["accent"]))
                elif hdeco == "underline":
                    story.append(Spacer(1, 3*mm))
                    story.append(HRule(self.body_w, 0.8, self.T["accent"]))
                elif hdeco == "dot":
                    story.append(Spacer(1, 5*mm))
                    story.append(ClayDot(self.body_w, self.T["accent"]))
                toc.append(('chapter', title, cm.key))
                i += 1; continue

            # H3 = Section
            if stripped.startswith('### '):
                story.append(Spacer(1, 3*mm))
                story.append(Paragraph(inl(stripped[4:].strip(), "h3"), ST['h3']))
                story.append(Spacer(1, 1*mm))
                i += 1; continue

            # H4-H6 Heading
            if stripped.startswith('#### '):
                story.append(Spacer(1, 2*mm))
                story.append(Paragraph(inl(stripped[5:].strip(), "h3"), ST['h3']))
                story.append(Spacer(1, 1*mm))
                i += 1; continue
            if stripped.startswith('##### '):
                story.append(Spacer(1, 2*mm))
                story.append(Paragraph(inl(stripped[6:].strip(), "h3"), ST['h3']))
                story.append(Spacer(1, 1*mm))
                i += 1; continue
            if stripped.startswith('###### '):
                story.append(Spacer(1, 1*mm))
                story.append(Paragraph(inl(stripped[7:].strip(), "h3"), ST['h3']))
                i += 1; continue

            # Tables
            if stripped.startswith('|'):
                tl = []
                while i < len(lines) and lines[i].strip().startswith('|'):
                    tl.append(lines[i]); i += 1
                t = self.parse_table(tl)
                if t: story.append(Spacer(1,2*mm)); story.append(t); story.append(Spacer(1,2*mm))
                continue

            # Images: ![alt](path)
            img_match = re.match(r'^!\[([^\]]*)\]\(([^)]+)\)', stripped)
            if img_match:
                img_caption = img_match.group(1)
                img_path = img_match.group(2)
                base_dir = self.cfg.get("base_dir", "")
                if base_dir and not os.path.isabs(img_path):
                    img_path = os.path.join(base_dir, img_path)
                if os.path.exists(img_path):
                    try:
                        avail_w = self.body_w - 10*mm
                        img_reader = ImageReader(img_path)
                        iw, ih = img_reader.getSize()
                        ratio = ih / iw
                        img_w = min(avail_w, iw)
                        img_h = img_w * ratio
                        # Cap height at 60% of body height
                        max_h = self.body_h * 0.55
                        if img_h > max_h:
                            img_h = max_h
                            img_w = img_h / ratio
                        # Handle transparent PNGs: composite onto white background
                        img_src = _flatten_transparency(img_path)
                        img = RLImage(img_src, width=img_w, height=img_h)
                        story.append(Spacer(1, 4*mm))
                        # Center the image
                        img_elements = [img]
                        if img_caption:
                            cap_style = ParagraphStyle(
                                'ImgCap', fontName="Sans", fontSize=8, leading=11,
                                textColor=self.T["ink_faded"], alignment=TA_CENTER,
                                spaceBefore=2*mm)
                            img_elements.append(Paragraph(_font_wrap(esc(img_caption), cjk_font=self._current_body_cjk_font), cap_style))
                        story.append(KeepTogether(img_elements))
                        story.append(Spacer(1, 4*mm))
                    except Exception as e:
                        story.append(Paragraph(_font_wrap(esc(f"[Image: {img_caption or img_path}]"), cjk_font=self._current_body_cjk_font), ST['body']))
                i += 1; continue

            # Bullets
            if stripped.startswith('- ') or stripped.startswith('* '):
                story.append(Spacer(1, 1*mm))
                while i < len(lines):
                    l = lines[i].strip()
                    if l.startswith('- ') or l.startswith('* '):
                        txt = l[2:].strip()
                        story.append(Paragraph(inl(txt, "bullet"), ST['bullet']))
                        i += 1
                    else:
                        break
                story.append(Spacer(1, 1*mm))
                continue

            # Numbered list
            num_match = re.match(r'^(\d+)\.\s', stripped)
            if num_match:
                story.append(Spacer(1, 1*mm))
                while i < len(lines):
                    l = lines[i].strip()
                    m = re.match(r'^(\d+)\.\s', l)
                    if m:
                        txt = l[m.end():].strip()
                        story.append(Paragraph(inl(txt, "bullet"), ST['bullet'], bulletText=m.group(1)+'.'))
                        i += 1
                    else:
                        break
                story.append(Spacer(1, 1*mm))
                continue

            # Blockquote
            if stripped.startswith('> '):
                plines = []
                while i < len(lines) and lines[i].strip().startswith('> '):
                    plines.append(lines[i].strip()[2:].strip())
                    i += 1
                merged = ' '.join(plines)
                story.append(Spacer(1, 2*mm))
                story.append(Paragraph(inl(merged, "body_indent"), ST['body_indent']))
                story.append(Spacer(1, 2*mm))
                continue

            # Paragraph — join consecutive lines; skip space between CJK characters
            plines = []
            while i < len(lines):
                l = lines[i].strip()
                if not l:
                    # If we have gathered some paragraph lines, stop here to process them.
                    # If we haven't, it means we are on an empty line, but the outer loop
                    # will handle incrementing i below if we exit this inner loop.
                    break
                # Stop if it starts with special marker
                if l.startswith('#') or l.startswith('```') or l.startswith('|') or \
                   l.startswith('- ') or l.startswith('* ') or l.startswith('> ') or re.match(r'^\d+\.\s', l):
                    break
                plines.append(l); i += 1

            if plines:
                merged = ""
                for pl in plines:
                    if not merged: merged = pl
                    else:
                        # If prev line ends with CJK and next starts with CJK, join directly (no space)
                        if _is_cjk(merged[-1]) and _is_cjk(pl[0]):
                            merged += pl
                        else:
                            merged += ' ' + pl
                story.append(Paragraph(inl(merged, "body"), ST['body']))
            else:
                # If we didn't match anything else and plines is empty,
                # we MUST increment i to avoid infinite loop.
                i += 1

        return story, toc

    def build_toc(self, toc, page_map=None):
        """Build TOC entries with dot leaders and right-aligned page numbers."""
        T = self.T; ah = self.accent_hex
        s = [Spacer(1, 15*mm)]
        s.append(Paragraph(md_inline("\u76ee    \u5f55", ah, cjk_font=self._style_cjk_font("part")), self.ST['part']))
        s.append(HRule(self.body_w * 0.12, 1, T["accent"]))
        s.append(Spacer(1, 8*mm))

        for etype, title, key in toc:
            is_part = etype == 'part'
            pg = page_map.get(key, "") if page_map else ""
            s.append(TocEntry(
                title=title,
                page=pg,
                anchor_key=key,
                width=self.body_w,
                font_size=12 if is_part else 10,
                bold=is_part,
                title_color=T["ink"] if is_part else T["ink_faded"],
                dot_color=T["border"],
                indent=0 if is_part else 16,
            ))
        return s

    # ── Build PDF ────────────────────────────────────────────────────────────
    def build(self, md_text, output_path):
        register_fonts()
        has_toc = self.cfg.get("toc", True)

        if has_toc:
            # First pass: parse and build to collect page numbers
            print("Parsing markdown (pass 1)...")
            # 重置全局 anchor 计数器，确保 pass 1 和 pass 2 的 anchor key 一致
            # （修复同一进程多次构建时 TOC 页码全部丢失的 bug）
            _anchor_counter[0] = 0
            _outline_level[0] = -1
            _cur_chapter[0] = ""
            story_content_1, toc = self.parse_md(md_text)
            print(f"  {len(story_content_1)} elements, {len(toc)} TOC entries")
            if not toc:
                has_toc = False

        if has_toc:
            # Two-pass build: collect page numbers first, then render with real TOC
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_path = tmp.name

            print("Pass 1: collecting page numbers...")
            try:
                page_map = self._build_pass(tmp_path, story_content_1, toc)
            finally:
                # 确保 _build_pass 异常时临时 PDF 也被清理
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            # Second pass: re-parse to get fresh flowables, then build with real page numbers
            print(f"Parsing markdown (pass 2, {len(page_map)} page refs)...")
            _anchor_counter[0] = 0
            _outline_level[0] = -1
            _cur_chapter[0] = ""
            story_content_2, toc_2 = self.parse_md(md_text)
            self._build_pass(output_path, story_content_2, toc_2, page_map=page_map)
        else:
            print("Parsing markdown...")
            story_content, toc = self.parse_md(md_text)
            print(f"  {len(story_content)} elements, {len(toc)} TOC entries")
            self._build_pass(output_path, story_content, toc)

        size = os.path.getsize(output_path)
        print(f"Done! {output_path} ({size/1024/1024:.1f} MB)")

    def _build_pass(self, output_path, story_content, toc, page_map=None):
        """Single build pass. First pass collects page numbers via afterFlowable."""
        body_frame = Frame(self.lm, self.bm, self.body_w, self.body_h, id='body')
        full_frame = Frame(0, 0, self.page_w, self.page_h, leftPadding=0,
                           rightPadding=0, topPadding=0, bottomPadding=0, id='full')

        has_frontis = self.cfg.get("frontispiece") and os.path.exists(self.cfg["frontispiece"])
        has_banner = self.cfg.get("banner") and os.path.exists(self.cfg["banner"])
        has_toc = self.cfg.get("toc", True) and toc

        collected_pages = {}

        class _DocWithCollector(BaseDocTemplate):
            """DocTemplate that collects ChapterMark page numbers via afterFlowable."""
            def afterFlowable(self, flowable):
                if isinstance(flowable, ChapterMark):
                    collected_pages[flowable.key] = self.page

        doc = _DocWithCollector(output_path, pagesize=(self.page_w, self.page_h),
                                leftMargin=self.lm, rightMargin=self.rm,
                                topMargin=self.tm, bottomMargin=self.bm,
                                title=self.cfg.get("title", ""),
                                author=self.cfg.get("author", ""))

        templates = [
            PageTemplate(id='normal', frames=[body_frame], onPage=self._normal_page),
        ]

        story = []

        # Cover page
        if self.cfg.get("cover", True):
            templates.insert(0, PageTemplate(id='cover', frames=[full_frame], onPage=self._cover_page))
            story.append(Spacer(1, self.page_h))

            if has_frontis:
                templates.append(PageTemplate(id='frontis', frames=[full_frame], onPage=self._frontispiece_page))
                story.append(NextPageTemplate('frontis'))
                story.append(PageBreak())
                story.append(Spacer(1, self.page_h))
                if has_toc:
                    templates.append(PageTemplate(id='toc', frames=[body_frame], onPage=self._toc_page))
                    story.append(NextPageTemplate('toc'))
                else:
                    story.append(NextPageTemplate('normal'))
                story.append(PageBreak())
            elif has_toc:
                templates.append(PageTemplate(id='toc', frames=[body_frame], onPage=self._toc_page))
                story.append(NextPageTemplate('toc'))
                story.append(PageBreak())
            else:
                story.append(NextPageTemplate('normal'))
                story.append(PageBreak())
        elif has_toc:
            templates.append(PageTemplate(id='toc', frames=[body_frame], onPage=self._toc_page))
            story.append(NextPageTemplate('toc'))

        # TOC (with or without page numbers)
        if has_toc:
            story.extend(self.build_toc(toc, page_map=page_map))
            story.append(NextPageTemplate('normal'))
            story.append(PageBreak())

        # Strip leading PageBreak from body content to avoid blank page
        body_copy = list(story_content)
        while body_copy and isinstance(body_copy[0], (PageBreak, Spacer)):
            if isinstance(body_copy[0], PageBreak):
                body_copy.pop(0)
                break
            body_copy.pop(0)

        story.extend(body_copy)

        # Back cover
        if has_banner:
            templates.append(PageTemplate(id='backcover', frames=[full_frame], onPage=self._backcover_page))
            story.append(NextPageTemplate('backcover'))
            story.append(PageBreak())
            story.append(Spacer(1, 1))

        doc.addPageTemplates(templates)
        doc.build(story)

        return collected_pages
