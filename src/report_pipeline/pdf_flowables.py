"""
pdf_flowables.py — Custom ReportLab Flowable components for medical PDF reports.

Provides:
  - MedicalResultFlowable: bold text + arrows + optional background tint pills
  - BadgeFlowable: qualified/stamp look (e.g. '合格')
  - RiskBarFlowable: tri-color gradient risk bar with slider triangle
  - ChapterMark: invisible bookmark/outline insertion point
  - HRule / HRuleCentered: horizontal rule separators
  - ClayDot: accent-colored dot separator
  - LeftBorderParagraph: paragraph with left accent border (code blocks)
"""

import re

from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.units import mm
from reportlab.platypus import Flowable


# ── Global outline state (shared across all flowable instances) ──────────────
_anchor_counter = [0]
_outline_level = [-1]
_cur_chapter = [""]


class MedicalResultFlowable(Flowable):
    """Modern medical report result style: bold text, arrows, and optional background pills."""

    def __init__(self, value="", arrow="", status_text="", color="#2D3748",
                 width=62, height=26, show_pill=True):
        Flowable.__init__(self)
        self.value = value
        self.arrow = arrow
        self.status_text = status_text
        self.color = color if isinstance(color, Color) else HexColor(color)
        self.width = width
        self.height = height
        self.show_pill = show_pill
        # Determine background color (soft 12% tint for abnormal results)
        self.bg_color = None
        if self.show_pill and (self.arrow or self.status_text):
            self.bg_color = Color(self.color.red, self.color.green, self.color.blue, alpha=0.12)

    def draw(self):
        c = self.canv

        # Soft background pill for abnormal results (if enabled)
        if self.bg_color and self.show_pill:
            c.setFillColor(self.bg_color)
            c.roundRect(0, 1, self.width, self.height - 2, 4, fill=1, stroke=0)

        c.setFillColor(self.color)
        # Use Bold only for abnormal indicators to maintain harmony
        is_abnormal = bool(self.arrow or self.status_text)
        font_main = "SansBold" if is_abnormal else "Sans"
        font_cjk = "CJK"

        # Line 1: Value + Arrow (Reduced to 9.2)
        val_size = 9.2
        try:
            c.setFont(font_main, val_size)
        except Exception:
            c.setFont("Helvetica-Bold" if is_abnormal else "Helvetica", val_size)

        # Draw value first
        val_text = str(self.value)
        val_w = c.stringWidth(val_text, font_main, val_size)

        arrow_w = 0
        if self.arrow:
            # Force CJK font for arrow
            c.setFont(font_cjk, val_size)
            arrow_w = c.stringWidth(f" {self.arrow}", font_cjk, val_size)

        # Calculate start X to center the combined group
        total_w = val_w + arrow_w
        x_start = (self.width - total_w) / 2

        if self.status_text:
            # Dual line layout
            y1 = self.height / 2 + 1.5
            c.setFont(font_main, val_size)
            c.drawString(x_start, y1, val_text)
            if self.arrow:
                c.setFont(font_cjk, val_size)
                c.drawString(x_start + val_w, y1, f" {self.arrow}")

            # Line 2: Status Text Label (Further reduced to 5.8)
            status_size = 5.8
            c.setFont(font_cjk, status_size)
            sw = c.stringWidth(self.status_text, font_cjk, status_size)
            sx = (self.width - sw) / 2
            y2 = self.height / 2 - 8.5
            c.drawString(sx, y2, self.status_text)
        else:
            # Single line centered (normal results)
            y = (self.height - val_size) / 2 + 2
            c.setFont(font_main, val_size)
            c.drawString(x_start, y, val_text)
            if self.arrow:
                c.setFont(font_cjk, val_size)
                c.drawString(x_start + val_w, y, f" {self.arrow}")


class BadgeFlowable(MedicalResultFlowable):
    """Restore the original stamp look for indicators like '合格'."""

    def __init__(self, text="合格", color="#2E8B57", width=46, height=15, radius=3, **kwargs):
        # We call the medical initializer but we'll override the draw method for the stamp look
        super().__init__(value=text, color=color, width=width, height=height)
        self.radius = radius

    def draw(self):
        c = self.canv
        # Draw the stamp border (Qualified look)
        c.setStrokeColor(self.color)
        c.setLineWidth(1)
        c.roundRect(0, 0, self.width, self.height, self.radius, fill=0, stroke=1)

        # Text matching the border color
        c.setFillColor(self.color)
        font_name = "CJK"
        font_size = 8
        try:
            c.setFont(font_name, font_size)
        except Exception:
            c.setFont("Helvetica", font_size)

        text_width = c.stringWidth(self.value, font_name, font_size)
        x = (self.width - text_width) / 2
        y = (self.height - font_size) / 2 + 1.2
        c.drawString(x, y, self.value)


class RiskBarFlowable(Flowable):
    """Risk bar chart showing indicator position relative to reference range.

    Supports:
    - Dual range (lower, upper): bidirectional gradient
    - Upper only (<X, ≤X): single upward gradient
    - Lower only (>X, ≥X): single downward gradient

    Visual design inspired by medical examination reports.
    """
    # Standard dimensions (in points)
    BAR_WIDTH = 100
    BAR_HEIGHT = 8
    SLIDER_WIDTH = 8
    SLIDER_HEIGHT = 14
    MARKER_SIZE = 4

    def __init__(self, raw_result=None, raw_reference=None, risk_status=None,
                 width=None, height=None):
        Flowable.__init__(self)
        self.raw_result = raw_result
        self.raw_reference = raw_reference
        self.risk_status = risk_status
        self.width = width or self.BAR_WIDTH
        self.height = height or self.BAR_HEIGHT

    def draw(self):
        c = self.canv
        # Shift bar up to leave space for triangle below
        # Triangle height is ~5.2, gap is 1.0, so bar_y should be >= 6.2
        by = 6.5

        # Parse reference range
        ref_info = self._parse_reference(self.raw_reference)
        if not ref_info:
            self._draw_no_data(c)
            return

        ref_type = ref_info['type']  # 'dual', 'upper', 'lower', 'none'
        lower = ref_info.get('lower')
        upper = ref_info.get('upper')
        value = self._parse_value(self.raw_result)

        # Calculate positions
        if ref_type == 'dual':
            self._draw_dual_bar(c, value, lower, upper, bar_y=by)
        elif ref_type == 'upper':
            self._draw_upper_only_bar(c, value, upper, bar_y=by)
        elif ref_type == 'lower':
            self._draw_lower_only_bar(c, value, lower, bar_y=by)
        else:
            self._draw_no_data(c)

    def _parse_reference(self, raw_ref):
        """Parse reference string into range info."""
        if not raw_ref or raw_ref in ('--', '/', '-'):
            return None

        raw_ref = str(raw_ref).strip()

        # Dual range: "3.5-7.5" or "3.5~7.5"
        for sep in ['-', '~', '—']:
            if sep in raw_ref:
                parts = raw_ref.split(sep)
                if len(parts) == 2:
                    try:
                        lower = float(parts[0].strip())
                        upper = float(parts[1].strip())
                        if lower < upper:
                            if lower == 0:
                                return {'type': 'upper', 'upper': upper}
                            return {'type': 'dual', 'lower': lower, 'upper': upper}
                    except ValueError:
                        pass

        # Upper only: "<8.5" or "< 8.5" or "≤8.5"
        m = re.match(r'^<\s*([\d.]+)$', raw_ref)
        if m:
            return {'type': 'upper', 'upper': float(m.group(1))}
        # ≤ (less than or equal)
        m = re.match(r'^≤\s*([\d.]+)$', raw_ref)
        if m:
            return {'type': 'upper', 'upper': float(m.group(1))}

        # Lower only: ">2.5" or "> 2.5" or "≥2.5"
        m = re.match(r'^>\s*([\d.]+)$', raw_ref)
        if m:
            return {'type': 'lower', 'lower': float(m.group(1))}
        # ≥ (greater than or equal)
        m = re.match(r'^≥\s*([\d.]+)$', raw_ref)
        if m:
            return {'type': 'lower', 'lower': float(m.group(1))}

        return None

    def _parse_value(self, raw_result):
        """Parse numeric value from result string, handling prefixes like '<'."""
        if raw_result is None:
            return None
        s = str(raw_result).strip()
        if not s or s in ('--', '/', '-'):
            return None

        # Handle prefix like '<1.20' -> 1.20; and avoid issues with regex if no digit
        m = re.search(r'[\d.]+', s)
        if m:
            try:
                return float(m.group(0))
            except ValueError:
                return None
        return None

    def _get_position(self, value, lower, upper):
        """Get slider position (0-1) for value within range."""
        if value is None:
            return 0.5

        range_val = upper - lower
        # Clamp value to 120% of range for display
        max_display = lower + range_val * 1.2

        if value >= upper:
            return 1.0  # At right end
        elif value <= lower:
            return 0.0  # At left end
        else:
            return (value - lower) / range_val

    def _get_overflow(self, value, lower, upper):
        """Get overflow amount if value exceeds range (0-1 scale)."""
        if value is None:
            return 0
        range_val = upper - lower
        max_display = lower + range_val * 1.2

        if value > upper:
            excess = value - upper
            return min(1.0, excess / (max_display - upper)) if max_display > upper else 1.0
        elif value < lower:
            excess = lower - value
            return min(1.0, excess / (lower - (max_display - range_val))) if max_display > lower else 1.0
        return 0

    def _draw_gradient_bar(self, c, x, y, w, h, color_stops, direction='horizontal'):
        """Draw a gradient bar using color stops."""
        # For simplicity, draw segments with interpolated colors
        n_segments = 20
        segment_w = w / n_segments

        for i in range(n_segments):
            t = i / (n_segments - 1)
            color = self._interpolate_color(color_stops, t)
            c.setFillColor(color)
            c.setStrokeColor(color)
            if direction == 'horizontal':
                c.rect(x + i * segment_w, y, segment_w, h, fill=1, stroke=0)

    def _interpolate_color(self, color_stops, t):
        """Interpolate color from stops at position t (0-1)."""
        # Find surrounding stops
        for i in range(len(color_stops) - 1):
            if color_stops[i][0] <= t <= color_stops[i + 1][0]:
                t1, c1 = color_stops[i]
                t2, c2 = color_stops[i + 1]
                if t2 == t1:
                    return c1
                local_t = (t - t1) / (t2 - t1)
                # Color objects use .red, .green, .blue attributes
                return Color(
                    c1.red + (c2.red - c1.red) * local_t,
                    c1.green + (c2.green - c1.green) * local_t,
                    c1.blue + (c2.blue - c1.blue) * local_t,
                )
        return color_stops[-1][1]

    def _draw_slider(self, c, x, y, w, h, is_above=False, is_below=False):
        """Draw a small equilateral triangle below the bar pointing up."""
        # Slider color based on status: red for abnormal, dark gray for normal
        if is_above or is_below:
            slider_color = Color(0.85, 0.1, 0.1)  # Slightly better red
        else:
            slider_color = Color(0.2, 0.2, 0.2)  # Dark gray

        c.setFillColor(slider_color)
        c.setStrokeColor(slider_color)

        cx = x + w / 2  # Center X

        # Equilateral triangle dimensions
        s = 6.0  # side length
        th = s * 0.866  # triangle height (sqrt(3)/2)

        # Position: Peak points UP towards the bar bottom (y)
        gap = 1.0
        peak_y = y - gap
        base_y = peak_y - th

        path = c.beginPath()
        path.moveTo(cx, peak_y)                  # Peak point
        path.lineTo(cx - s/2, base_y)            # Left base point
        path.lineTo(cx + s/2, base_y)            # Right base point
        path.close()
        c.drawPath(path, fill=1, stroke=0)

    def _draw_dual_bar(self, c, value, lower, upper, bar_y=0):
        """Draw bar with dual range (both lower and upper limits)."""
        w = self.width
        h = self.BAR_HEIGHT
        x, y = 0, bar_y

        # Color gradient: green -> yellow -> red
        # The reference range is in the middle, extremes are red
        color_stops = [
            (0.0, Color(1, 0, 0)),        # 0%: red (far below)
            (0.2, Color(1, 1, 0)),        # 20%: yellow (lower limit)
            (0.5, Color(0.2, 0.8, 0.2)),  # 50%: green (center)
            (0.8, Color(1, 1, 0)),        # 80%: yellow (upper limit)
            (1.0, Color(1, 0, 0)),        # 100%: red (far above)
        ]

        # Draw gradient bar
        self._draw_gradient_bar(c, x, y, w, h, color_stops)

        # Draw range markers
        range_start_pct = 0.2  # lower bound starts at 20%
        range_end_pct = 0.8    # upper bound ends at 80%

        c.setStrokeColor(Color(0.3, 0.3, 0.3))
        c.setLineWidth(1)

        # Lower limit marker
        lx = x + w * range_start_pct
        c.line(lx, y - 2, lx, y + h + 2)

        # Upper limit marker
        ux = x + w * range_end_pct
        c.line(ux, y - 2, ux, y + h + 2)

        # Draw slider
        is_above = value is not None and value > upper
        is_below = value is not None and value < lower

        if value is not None:
            if is_above:
                slider_x = x + w - 2  # At right end
            elif is_below:
                slider_x = x + 2  # At left end
            else:
                # Map value to position within range
                if upper == lower:
                    pos = 0.5
                else:
                    pos = (value - lower) / (upper - lower)
                    pos = 0.2 + pos * 0.6  # Scale to range portion (20-80%)
                slider_x = x + w * pos
        else:
            slider_x = x + w / 2

        # Draw slider
        self._draw_slider(c, slider_x - 4, y, 8, h, is_above, is_below)

    def _draw_upper_only_bar(self, c, value, upper, bar_y=0):
        """Draw bar with upper limit only (<X). Gradient: green -> red downward."""
        w, h = self.width, self.BAR_HEIGHT
        x, y = 0, bar_y

        # Gradient: green (left, safe) -> yellow -> red (right, danger)
        color_stops = [
            (0.0, Color(0.2, 0.8, 0.2)),  # 0%: green (safe)
            (0.7, Color(1, 1, 0)),          # 70%: yellow
            (1.0, Color(1, 0, 0)),          # 100%: red (danger)
        ]

        self._draw_gradient_bar(c, x, y, w, h, color_stops)

        # Draw upper limit marker
        limit_x = x + w * 0.8  # Upper limit at 80%
        c.setStrokeColor(Color(0.3, 0.3, 0.3))
        c.setLineWidth(1)
        c.line(limit_x, y - 2, limit_x, y + h + 2)

        # Draw slider
        is_above = value is not None and value > upper

        if value is not None:
            if value >= upper:
                slider_x = x + w - 2
            else:
                # Map value to position (max display is 120% of upper)
                max_display = upper * 1.2
                pos = min(1.0, value / max_display)
                slider_x = x + w * pos
        else:
            slider_x = x + w * 0.5

        self._draw_slider(c, slider_x - 4, y, 8, h, is_above=is_above)

    def _draw_lower_only_bar(self, c, value, lower, bar_y=0):
        """Draw bar with lower limit only (>X). Gradient: red -> yellow -> green upward."""
        w, h = self.width, self.BAR_HEIGHT
        x, y = 0, bar_y

        # Gradient: red (left, danger) -> yellow -> green (right, safe)
        color_stops = [
            (0.0, Color(1, 0, 0)),          # 0%: red (danger)
            (0.3, Color(1, 1, 0)),             # 30%: yellow
            (1.0, Color(0.2, 0.8, 0.2)),      # 100%: green (safe)
        ]

        self._draw_gradient_bar(c, x, y, w, h, color_stops)

        # Draw lower limit marker
        limit_x = x + w * 0.2  # Lower limit at 20%
        c.setStrokeColor(Color(0.3, 0.3, 0.3))
        c.setLineWidth(1)
        c.line(limit_x, y - 2, limit_x, y + h + 2)

        # Draw slider
        is_below = value is not None and value < lower

        if value is not None:
            if value <= lower:
                slider_x = x + 2
            else:
                # Map value to position (max display is 120% of range above lower)
                max_display = lower + (lower * 0.2) if lower > 0 else lower + 1
                pos = min(1.0, (value - lower) / (max_display - lower) * 0.8)
                slider_x = x + w * (0.2 + pos * 0.8)
        else:
            slider_x = x + w * 0.5

        self._draw_slider(c, slider_x - 4, y, 8, h, is_below=is_below)

    def _draw_no_data(self, c):
        """Draw placeholder when no data available."""
        w, h = self.width, self.height
        c.setFillColor(Color(0.9, 0.9, 0.9))
        c.rect(0, 0, w, h, fill=1, stroke=0)
        c.setFillColor(Color(0.5, 0.5, 0.5))
        c.setFont("Helvetica", 6)
        c.drawCentredString(w / 2, h / 2 - 3, "--")


class ChapterMark(Flowable):
    """Invisible flowable that sets a PDF bookmark and outline entry."""
    width = height = 0

    def __init__(self, t, level=0):
        Flowable.__init__(self); self.title = t; self.level = level
        _anchor_counter[0] += 1; self.key = f"anchor_{_anchor_counter[0]}"

    def draw(self):
        _cur_chapter[0] = self.title
        self.canv.bookmarkPage(self.key)
        target = min(self.level, _outline_level[0] + 1)
        _outline_level[0] = target
        self.canv.addOutlineEntry(self.title, self.key, level=target, closed=(target==0))


class TocEntry(Flowable):
    """TOC entry with title left-aligned, dot leaders, and page number right-aligned.

    Follows publication best-practice: title ·············· 12
    Uses _draw_mixed for proper CJK/Latin font switching.
    """
    def __init__(self, title, page, anchor_key, width,
                 font_size=10, bold=False,
                 title_color=None, dot_color=None, indent=0):
        Flowable.__init__(self)
        self._title = title
        self._page = str(page) if page else ""
        self._key = anchor_key
        self.width = width
        self.height = max(font_size + 8, 18)
        self._fsize = font_size
        self._bold = bold
        self._title_color = title_color or HexColor("#181818")
        self._dot_color = dot_color or HexColor("#C0C0C0")
        self._indent = indent

    def _title_font(self):
        return "CJKBold" if self._bold else "CJK"

    def _measure(self, c, text):
        """Measure mixed CJK/Latin text width."""
        from report_pipeline.pdf_utils import _measure_mixed
        return _measure_mixed(c, text, self._fsize)

    def _draw_text(self, c, x, y, text):
        """Draw mixed CJK/Latin text, returns end x position."""
        from report_pipeline.pdf_utils import _is_cjk
        segs, buf, in_cjk = [], [], False
        for ch in text:
            cj = _is_cjk(ch)
            if cj != in_cjk and buf:
                font = ("CJKBold" if self._bold else "CJK") if in_cjk else ("SansBold" if self._bold else "Sans")
                segs.append((font, ''.join(buf))); buf = []
            buf.append(ch); in_cjk = cj
        if buf:
            font = ("CJKBold" if self._bold else "CJK") if in_cjk else ("SansBold" if self._bold else "Sans")
            segs.append((font, ''.join(buf)))
        for font, txt in segs:
            c.setFont(font, self._fsize)
            c.drawString(x, y, txt)
            x += c.stringWidth(txt, font, self._fsize)
        return x

    def draw(self):
        c = self.canv
        y = self.height - self._fsize - 3

        # Internal link rectangle
        if self._key:
            c.linkRect("", self._key, (0, 0, self.width, self.height), relative=1)

        # Measure widths
        c.setFont("Sans", self._fsize)
        right_margin = 6
        page_w = c.stringWidth(self._page, "Sans", self._fsize) if self._page else 0
        max_title_w = self.width - self._indent - right_margin - page_w - 10

        # Truncate title if needed
        display_title = self._title
        title_w = self._measure(c, display_title)
        if title_w > max_title_w:
            while title_w > max_title_w and display_title:
                display_title = display_title[:-1]
                title_w = self._measure(c, display_title + "…")
            display_title += "…"
            title_w = self._measure(c, display_title)

        # Draw title (left)
        c.setFillColor(self._title_color)
        title_end_x = self._draw_text(c, self._indent, y, display_title)

        # Draw page number (right-aligned)
        if self._page:
            c.setFillColor(self._title_color)
            c.setFont("Sans", self._fsize)
            c.drawString(self.width - right_margin - page_w, y, self._page)

            # Dot leaders between title and page number
            c.setFillColor(self._dot_color)
            c.setFont("Sans", self._fsize)
            dot_x_start = title_end_x + 3
            dot_x_end = self.width - right_margin - page_w - 3
            dot_w = c.stringWidth(".", "Sans", self._fsize)
            if dot_w > 0 and dot_x_end > dot_x_start:
                x = dot_x_start
                while x + dot_w <= dot_x_end:
                    c.drawString(x, y, ".")
                    x += dot_w + 1.5


class HRule(Flowable):
    """Full-width horizontal rule."""
    def __init__(self, w, thick=0.5, clr=None):
        Flowable.__init__(self)
        self.width = w; self.height = 4*mm; self._t = thick; self._c = clr or HexColor("#E8E6DC")

    def draw(self):
        self.canv.setStrokeColor(self._c); self.canv.setLineWidth(self._t)
        self.canv.line(0, 2*mm, self.width, 2*mm)


class HRuleCentered(Flowable):
    """Horizontally centered rule within the frame width."""
    def __init__(self, frame_w, rule_w, thick=0.5, clr=None):
        Flowable.__init__(self)
        self.width = frame_w; self.height = 4*mm
        self._rw = rule_w; self._t = thick; self._c = clr or HexColor("#E8E6DC")

    def draw(self):
        self.canv.setStrokeColor(self._c); self.canv.setLineWidth(self._t)
        x0 = (self.width - self._rw) / 2
        self.canv.line(x0, 2*mm, x0 + self._rw, 2*mm)


class ClayDot(Flowable):
    """Small accent-colored dot separator."""
    def __init__(self, w, clr=None):
        Flowable.__init__(self)
        self.width = w; self.height = 6*mm
        self._c = clr or HexColor("#CC785C")

    def draw(self):
        self.canv.setFillColor(self._c)
        cx = self.width / 2
        self.canv.circle(cx, 3*mm, 1.5*mm, fill=1, stroke=0)


class LeftBorderParagraph(Flowable):
    """Paragraph with a left accent border line (for code blocks in 'border' style)."""
    def __init__(self, para, border_color, border_width=2):
        Flowable.__init__(self)
        self._para = para
        self._bc = border_color; self._bw = border_width

    def wrap(self, aw, ah):
        w, h = self._para.wrap(aw, ah)
        self.width = w; self.height = h
        return w, h

    def draw(self):
        self._para.drawOn(self.canv, 0, 0)
        self.canv.setStrokeColor(self._bc); self.canv.setLineWidth(self._bw)
        self.canv.line(2, -2, 2, self.height + 2)
