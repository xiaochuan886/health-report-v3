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
"""

import re, os, sys, json, argparse, io
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
from reportlab.pdfbase.ttfonts import TTFont

# ═══════════════════════════════════════════════════════════════════════
# FONTS — cross-platform font discovery (macOS / Linux / Windows)
# ═══════════════════════════════════════════════════════════════════════
import platform as _platform
_PLAT = _platform.system()  # "Darwin", "Linux", "Windows"

def _find_font(candidates):
    """Return first existing path from candidates list.
    Each candidate is either a string path or a (path, subfontIndex) tuple."""
    for c in candidates:
        path = c[0] if isinstance(c, tuple) else c
        if os.path.exists(path):
            return c
    return None

# Font candidates per role — ordered by preference, first match wins.
# Each role lists candidates for macOS, Windows, Linux in one flat list.
_FONT_CANDIDATES = {
    "Sans": [
        ("/System/Library/Fonts/Helvetica.ttc", 0),                               # macOS
        "C:/Windows/Fonts/arial.ttf",                                            # Windows
        "/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf",               # Linux Debian
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",                   # Linux Noto
        "/usr/share/fonts/noto/NotoSans-Regular.ttf",                            # Linux Fedora
    ],
    "SansBold": [
        ("/System/Library/Fonts/Helvetica.ttc", 1),                               # macOS Bold
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/crosextra/Carlito-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/noto/NotoSans-Bold.ttf",
    ],
    "SansIt": [
        ("/System/Library/Fonts/Helvetica.ttc", 2),                               # macOS Oblique
        "C:/Windows/Fonts/ariali.ttf",
        "/usr/share/fonts/truetype/crosextra/Carlito-Italic.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Italic.ttf",
    ],
    "SansBI": [
        ("/System/Library/Fonts/Helvetica.ttc", 3),                               # macOS Bold Oblique
        "C:/Windows/Fonts/arialbi.ttf",
        "/usr/share/fonts/truetype/crosextra/Carlito-BoldItalic.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-BoldItalic.ttf",
    ],
    "Serif": [
        ("/System/Library/Fonts/Palatino.ttc", 0),                               # macOS Palatino
        "C:/Windows/Fonts/times.ttf",                                            # Windows TNR
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf",     # Linux
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf",
        "/usr/share/fonts/noto/NotoSerif-Regular.ttf",
    ],
    "SerifBold": [
        ("/System/Library/Fonts/Palatino.ttc", 2),
        "C:/Windows/Fonts/timesbd.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf",
    ],
    "SerifIt": [
        ("/System/Library/Fonts/Palatino.ttc", 1),
        "C:/Windows/Fonts/timesi.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Italic.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
    ],
    "SerifBI": [
        ("/System/Library/Fonts/Palatino.ttc", 3),
        "C:/Windows/Fonts/timesbi.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-BoldItalic.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-BoldItalic.ttf",
    ],
    "CJK": [
        ("/System/Library/Fonts/STHeiti Light.ttc", 0),                           # macOS STHeiti
        "C:/Windows/Fonts/msyh.ttc",                                             # Windows MSYH (微软雅黑)
        ("/System/Library/Fonts/Supplemental/Songti.ttc", 0),                   # macOS Songti SC
        "C:/Windows/Fonts/simsun.ttc",                                           # Windows SimSun (宋体)
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",               # Linux Noto Sans CJK
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",                  # macOS fallback
    ],
    "CJKBold": [
        ("/System/Library/Fonts/STHeiti Medium.ttc", 0),                          # macOS STHeiti Medium
        "C:/Windows/Fonts/msyhbd.ttc",                                           # Windows MSYH Bold
        ("/System/Library/Fonts/Supplemental/Songti.ttc", 1),
        "C:/Windows/Fonts/simsunb.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    ],
    "Mono": [
        ("/System/Library/Fonts/Menlo.ttc", 0),                                  # macOS
        "C:/Windows/Fonts/consola.ttf",                                          # Windows Consolas
        "C:/Windows/Fonts/cour.ttf",                                             # Windows Courier New
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",                  # Linux
        "/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf",
    ],
    "MonoBold": [
        ("/System/Library/Fonts/Menlo.ttc", 1),
        "C:/Windows/Fonts/consolab.ttf",
        "C:/Windows/Fonts/courbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansMono-Bold.ttf",
    ],
}

def register_fonts():
    missing = []
    for name, candidates in _FONT_CANDIDATES.items():
        spec = _find_font(candidates)
        if spec is None:
            missing.append(name)
            continue
        try:
            if isinstance(spec, tuple):
                pdfmetrics.registerFont(TTFont(name, spec[0], subfontIndex=spec[1]))
            else:
                pdfmetrics.registerFont(TTFont(name, spec))
        except Exception as e:
            missing.append(name)
            print(f"Warning: Font {name} — {e}", file=sys.stderr)
    if missing:
        print(f"Warning: Missing fonts: {', '.join(missing)}. PDF may have □ characters.", file=sys.stderr)
        if _PLAT == "Linux":
            print("  Fix: sudo apt install fonts-noto fonts-noto-cjk fonts-dejavu-core", file=sys.stderr)
        elif _PLAT == "Windows":
            print("  Fix: Install Noto fonts from https://fonts.google.com/noto", file=sys.stderr)
    pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="SansBold",
                                  italic="SansIt", boldItalic="SansBI")
    pdfmetrics.registerFontFamily("Serif", normal="Serif", bold="SerifBold",
                                  italic="SerifIt", boldItalic="SerifBI")
    pdfmetrics.registerFontFamily("CJK", normal="CJK", bold="CJKBold",
                                  italic="CJK", boldItalic="CJKBold")

# ═══════════════════════════════════════════════════════════════════════
# THEMES — each theme has colors + layout for real typographic difference
# ═══════════════════════════════════════════════════════════════════════
# Layout keys:
#   margins: (left, right, top, bottom) in mm
#   body_font: "Serif" or "Sans"
#   body_size / body_leading: body text dimensions
#   h1_size / h2_size / h3_size: heading sizes
#   heading_align: TA_CENTER or TA_LEFT
#   heading_decoration: "rules" | "underline" | "dot" | "none"
#   header_style: "full" | "minimal" | "none"
#   code_style: "bg" (background fill) | "border" (left border only)
#   cover_style: "centered" | "left-aligned" | "minimal"
#   page_decoration: "none" | "top-bar" | "left-stripe" | "side-rule" | "corner-marks"

_DEFAULT_LAYOUT = {
    "margins": (25, 22, 28, 25),
    "body_font": "Sans", "body_size": 10.5, "body_leading": 17,
    "h1_size": 26, "h2_size": 18, "h3_size": 12,
    "heading_align": "center", "heading_decoration": "rules",
    "header_style": "full", "code_style": "bg", "cover_style": "centered",
    "page_decoration": "none",
}

THEMES = {
    "warm-academic": {
        "canvas":"#F9F9F7","canvas_sec":"#F0EEE6","ink":"#181818","ink_faded":"#87867F",
        "accent":"#CC785C","accent_light":"#D99A82","border":"#E8E6DC",
        "watermark_rgba":(0.82,0.80,0.76,0.12),
        "layout": {
            "body_font":"Sans","body_size":10.5,"body_leading":17,
            "heading_align":"center","heading_decoration":"rules",
            "header_style":"full","code_style":"bg","cover_style":"centered",
            "page_decoration":"top-bar",
        }
    },
    "nord-frost": {
        "canvas":"#ECEFF4","canvas_sec":"#E5E9F0","ink":"#2E3440","ink_faded":"#4C566A",
        "accent":"#5E81AC","accent_light":"#81A1C1","border":"#D8DEE9",
        "watermark_rgba":(0.74,0.78,0.85,0.10),
        "layout": {
            "body_font":"Sans","body_size":10,"body_leading":16,
            "h3_size":11,"heading_align":"left","heading_decoration":"underline",
            "header_style":"minimal","code_style":"border","cover_style":"left-aligned",
            "page_decoration":"left-stripe",
        }
    },
    "github-light": {
        "canvas":"#FFFFFF","canvas_sec":"#F6F8FA","ink":"#1F2328","ink_faded":"#656D76",
        "accent":"#0969DA","accent_light":"#218BFF","border":"#D0D7DE",
        "watermark_rgba":(0.80,0.82,0.85,0.08),
        "layout": {
            "body_font":"Sans","body_size":10,"body_leading":16.5,
            "heading_align":"left","heading_decoration":"none",
            "header_style":"minimal","code_style":"bg","cover_style":"left-aligned",
            "page_decoration":"left-stripe",
        }
    },
    "corporate-blue": {
        "canvas":"#FFFFFF","canvas_sec":"#F0F8FA","ink":"#1A1A1A","ink_faded":"#5A6A75",
        "accent":"#007ec0","accent_light":"#8cba77","border":"#D0D7DE",
        "watermark_rgba":(0.80,0.85,0.85,0.08),
        "layout": {
            "body_font":"Sans","body_size":10.5,"body_leading":17,
            "heading_align":"center","heading_decoration":"rules",
            "header_style":"full","code_style":"bg","cover_style":"centered",
            "page_decoration":"top-bar",
        }
    },
    "solarized-light": {
        "canvas":"#FDF6E3","canvas_sec":"#EEE8D5","ink":"#657B83","ink_faded":"#93A1A1",
        "accent":"#CB4B16","accent_light":"#DC322F","border":"#EEE8D5",
        "watermark_rgba":(0.85,0.82,0.72,0.10),
    },
    "paper-classic": {
        "canvas":"#FFFFFF","canvas_sec":"#FAFAFA","ink":"#000000","ink_faded":"#666666",
        "accent":"#CC0000","accent_light":"#FF3333","border":"#DDDDDD",
        "watermark_rgba":(0.85,0.85,0.85,0.08),
    },
    "ocean-breeze": {
        "canvas":"#F0F7F4","canvas_sec":"#E0EDE8","ink":"#1A2E35","ink_faded":"#5A7D7C",
        "accent":"#2A9D8F","accent_light":"#64CCBF","border":"#C8DDD6",
        "watermark_rgba":(0.75,0.85,0.80,0.10),
        "layout": {
            "body_font":"Sans","body_size":10.5,"body_leading":17,
            "heading_align":"left","heading_decoration":"underline",
            "header_style":"full","code_style":"bg","cover_style":"centered",
            "page_decoration":"top-bar",
        }
    },
    "monokai-warm": {
        "canvas":"#272822","canvas_sec":"#1E1F1C","ink":"#F8F8F2","ink_faded":"#75715E",
        "accent":"#F92672","accent_light":"#FD971F","border":"#49483E",
        "watermark_rgba":(0.30,0.30,0.28,0.08),
    },
    "dracula-soft": {
        "canvas":"#282A36","canvas_sec":"#21222C","ink":"#F8F8F2","ink_faded":"#6272A4",
        "accent":"#BD93F9","accent_light":"#FF79C6","border":"#44475A",
        "watermark_rgba":(0.35,0.30,0.45,0.08),
    },
    # --- Inspired by classic LaTeX templates ---
    "tufte": {
        "canvas":"#FFFFF8","canvas_sec":"#F7F7F0","ink":"#111111","ink_faded":"#999988",
        "accent":"#980000","accent_light":"#C04040","border":"#E0DDD0",
        "watermark_rgba":(0.88,0.87,0.82,0.08),
        "layout": {
            "margins":(30, 55, 25, 25),  # wide right margin (Tufte sidenote style)
            "body_font":"Serif","body_size":11,"body_leading":18,
            "h1_size":24,"h2_size":16,"h3_size":11,
            "heading_align":"left","heading_decoration":"none",
            "header_style":"none","code_style":"border","cover_style":"minimal",
            "page_decoration":"side-rule",
        }
    },
    "classic-thesis": {
        "canvas":"#FEFEFE","canvas_sec":"#F5F2EB","ink":"#2B2B2B","ink_faded":"#7A7568",
        "accent":"#8B4513","accent_light":"#A0522D","border":"#D6CFC2",
        "watermark_rgba":(0.82,0.78,0.72,0.10),
        "layout": {
            "body_font":"Serif","body_size":10.5,"body_leading":17,
            "h1_size":28,"h2_size":20,
            "heading_align":"center","heading_decoration":"rules",
            "header_style":"full","code_style":"bg","cover_style":"centered",
            "page_decoration":"corner-marks",
        }
    },
    "ieee-journal": {
        "canvas":"#FFFFFF","canvas_sec":"#F5F5F5","ink":"#000000","ink_faded":"#555555",
        "accent":"#003366","accent_light":"#336699","border":"#CCCCCC",
        "watermark_rgba":(0.82,0.82,0.82,0.08),
        "layout": {
            "margins":(20, 20, 22, 20),  # tight margins like journal papers
            "body_font":"Serif","body_size":9.5,"body_leading":14,
            "h1_size":22,"h2_size":14,"h3_size":11,
            "heading_align":"left","heading_decoration":"underline",
            "header_style":"minimal","code_style":"border","cover_style":"left-aligned",
            "page_decoration":"top-band",
        }
    },
    "elegant-book": {
        "canvas":"#FBF9F1","canvas_sec":"#F0ECE0","ink":"#1A1A1A","ink_faded":"#6E6B5E",
        "accent":"#5B3A29","accent_light":"#7D5642","border":"#DDD8C8",
        "watermark_rgba":(0.85,0.82,0.75,0.10),
        "layout": {
            "margins":(28, 24, 30, 28),  # generous margins for book feel
            "body_font":"Serif","body_size":10.5,"body_leading":18,
            "h1_size":28,"h2_size":20,
            "heading_align":"center","heading_decoration":"dot",
            "header_style":"full","code_style":"bg","cover_style":"centered",
            "page_decoration":"double-rule",
        }
    },
    "chinese-red": {
        "canvas":"#FFFDF5","canvas_sec":"#F8F0E0","ink":"#1A1009","ink_faded":"#8C7A5E",
        "accent":"#B22222","accent_light":"#D44040","border":"#E8DCC8",
        "watermark_rgba":(0.88,0.82,0.72,0.10),
        "layout": {
            "body_font":"Serif","body_size":11,"body_leading":18,
            "h1_size":28,"h2_size":20,
            "heading_align":"center","heading_decoration":"rules",
            "header_style":"full","code_style":"bg","cover_style":"centered",
            "page_decoration":"top-bar",
        }
    },
    "ink-wash": {
        "canvas":"#F8F6F0","canvas_sec":"#EEEAE0","ink":"#2C2C2C","ink_faded":"#8A8A80",
        "accent":"#404040","accent_light":"#666660","border":"#D8D4C8",
        "watermark_rgba":(0.80,0.80,0.76,0.10),
        "layout": {
            "margins":(30, 30, 30, 28),  # symmetric, generous whitespace
            "body_font":"Serif","body_size":10.5,"body_leading":18,
            "h1_size":24,"h2_size":16,"h3_size":11,
            "heading_align":"center","heading_decoration":"dot",
            "header_style":"none","code_style":"border","cover_style":"minimal",
            "page_decoration":"none",
        }
    },
}

def load_theme(name, theme_file=None):
    if theme_file and os.path.exists(theme_file):
        with open(theme_file) as f:
            t = json.load(f)
    elif name in THEMES:
        t = THEMES[name]
    else:
        print(f"Unknown theme '{name}', falling back to warm-academic", file=sys.stderr)
        t = THEMES["warm-academic"]
    # Merge layout with defaults
    layout = dict(_DEFAULT_LAYOUT)
    layout.update(t.get("layout", {}))
    return {
        "canvas":    HexColor(t["canvas"]),
        "canvas_sec":HexColor(t["canvas_sec"]),
        "ink":       HexColor(t["ink"]),
        "ink_faded": HexColor(t["ink_faded"]),
        "accent":    HexColor(t["accent"]),
        "accent_light":HexColor(t.get("accent_light", t["accent"])),
        "border":    HexColor(t["border"]),
        "wm_color":  Color(*t.get("watermark_rgba", (0.82,0.80,0.76,0.12))),
        "layout":    layout,
    }

# ═══════════════════════════════════════════════════════════════════════
# CJK DETECTION + FONT WRAPPING
# ═══════════════════════════════════════════════════════════════════════
_CJK_RANGES = [
    (0x2190,0x21FF), # Arrows (↑, ↓, etc.)
    (0x4E00,0x9FFF),(0x3400,0x4DBF),(0xF900,0xFAFF),(0x3000,0x303F),
    (0xFF00,0xFFEF),(0x2E80,0x2EFF),(0x2F00,0x2FDF),(0xFE30,0xFE4F),
    (0x20000,0x2A6DF),(0x2A700,0x2B73F),(0x2B740,0x2B81F),
]

def _is_cjk(ch):
    cp = ord(ch)
    for lo, hi in _CJK_RANGES:
        if lo <= cp <= hi:
            return True
    return False

def _font_wrap(text):
    """Wrap CJK runs in <font name='CJK'> tags for reportlab Paragraph."""
    out, buf, in_cjk = [], [], False
    for ch in text:
        c = _is_cjk(ch)
        if c != in_cjk and buf:
            seg = ''.join(buf)
            out.append(f"<font name='CJK'>{seg}</font>" if in_cjk else seg)
            buf = []
        buf.append(ch); in_cjk = c
    if buf:
        seg = ''.join(buf)
        out.append(f"<font name='CJK'>{seg}</font>" if in_cjk else seg)
    return ''.join(out)

def _draw_mixed(c, x, y, text, size, anchor="left", max_w=0):
    """Draw mixed CJK/Latin text on canvas with font switching.
    If max_w > 0, wrap into multiple lines. Returns bottom y of drawn text."""
    if max_w > 0:
        return _draw_mixed_wrap(c, x, y, text, size, anchor, max_w)
    segs, buf, in_cjk = [], [], False
    for ch in text:
        cj = _is_cjk(ch)
        if cj != in_cjk and buf:
            segs.append(("CJK" if in_cjk else "Sans", ''.join(buf))); buf = []
        buf.append(ch); in_cjk = cj
    if buf: segs.append(("CJK" if in_cjk else "Sans", ''.join(buf)))
    total_w = sum(c.stringWidth(t, f, size) for f, t in segs)
    if anchor == "right": x -= total_w
    elif anchor == "center": x -= total_w / 2
    for font, txt in segs:
        c.setFont(font, size); c.drawString(x, y, txt)
        x += c.stringWidth(txt, font, size)

def _measure_mixed(c, text, size):
    """Measure width of mixed CJK/Latin text."""
    w = 0
    buf, in_cjk = [], False
    for ch in text:
        cj = _is_cjk(ch)
        if cj != in_cjk and buf:
            w += c.stringWidth(''.join(buf), "CJK" if in_cjk else "Sans", size); buf = []
        buf.append(ch); in_cjk = cj
    if buf: w += c.stringWidth(''.join(buf), "CJK" if in_cjk else "Sans", size)
    return w

def _draw_mixed_wrap(c, x, y, text, size, anchor, max_w):
    """Word-wrap mixed text into multiple lines, shrink font if single word overflows."""
    words = text.split(' ')
    # Shrink font until longest word fits (floor 16pt)
    while size > 16:
        longest = max(_measure_mixed(c, w, size) for w in words)
        if longest <= max_w: break
        size -= 1
    # Greedy line breaking
    lines, cur = [], []
    cur_w = 0
    space_w = c.stringWidth(' ', 'Sans', size)
    for word in words:
        ww = _measure_mixed(c, word, size)
        test_w = cur_w + (space_w if cur else 0) + ww
        if cur and test_w > max_w:
            lines.append(' '.join(cur)); cur = [word]; cur_w = ww
        else:
            cur.append(word); cur_w = test_w
    if cur: lines.append(' '.join(cur))
    # Draw lines downward from y (top line at y)
    line_h = size * 1.3
    for i, line in enumerate(lines):
        _draw_mixed(c, x, y - i * line_h, line, size, anchor)
    return y - (len(lines) - 1) * line_h

def _draw_mixed_segs(c, x, y, segs):
    """Draw pre-defined (font, text, size) segments on canvas.
    Used for mixed-font subtitle rendering."""
    total_w = sum(c.stringWidth(txt, font, sz) for font, txt, sz in segs)
    x = x - total_w / 2  # always centered
    for font, txt, sz in segs:
        c.setFont(font, sz)
        c.drawString(x, y, txt)
        x += c.stringWidth(txt, font, sz)

# ═══════════════════════════════════════════════════════════════════════
# INLINE MARKDOWN + ESCAPING
# ═══════════════════════════════════════════════════════════════════════
def esc(text):
    # Preserve <br/> and <br> tags through escaping
    text = text.replace('<br/>', '\x00BRSLASH\x00').replace('<br>', '\x00BR\x00')
    text = text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    text = text.replace('\x00BRSLASH\x00', '<br/>').replace('\x00BR\x00', '<br/>')
    return text

def esc_code(text):
    """Escape for code blocks: preserve indentation and newlines."""
    out = []
    for line in text.split('\n'):
        e = esc(line)
        stripped = e.lstrip(' ')
        indent = len(e) - len(stripped)
        out.append('&nbsp;' * indent + stripped)
    return '<br/>'.join(out)


def _flatten_transparency(img_path: str):
    """Convert transparent PNG (or images with alpha/transparency) to white background
    for consistent PDF rendering. Handles RGBA, LA, PA, and P (with trans) modes.

    Returns the original path if no conversion needed or PIL missing, or a BytesIO
    with the flattened RGB image.
    """
    if not img_path or not os.path.exists(img_path):
        return img_path
    try:
        from PIL import Image as PILImage
        img = PILImage.open(img_path)
        
        # Check if translation is needed: alpha channel or palette transparency
        has_alpha = img.mode in ('RGBA', 'LA', 'PA')
        has_trans = (img.mode == 'P' and 'transparency' in img.info)
        
        if has_alpha or has_trans:
            # Convert to RGBA to normalize all transparency types
            rgba = img.convert('RGBA')
            # Composite onto pure white background
            bg = PILImage.new('RGB', img.size, (255, 255, 255))
            bg.paste(rgba, mask=rgba.split()[3])
            
            buf = io.BytesIO()
            bg.save(buf, format='PNG')
            buf.seek(0)
            return buf
    except Exception:
        pass
    return img_path

def md_inline(text, accent_hex="#CC785C"):
    text = esc(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'`(.+?)`',
        rf"<font name='Mono' size='8' color='{accent_hex}'>\1</font>", text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'<u>\1</u>', text)

    text = text.replace("[RED]", "<font color='#E53E3E'><b>")
    text = text.replace("[/RED]", "</b></font>")
    text = text.replace("[ORANGE]", "<font color='#DD6B20'><b>")
    text = text.replace("[/ORANGE]", "</b></font>")
    
    text = text.replace("[TITLE]", "<font size='14'><b>")
    text = text.replace("[/TITLE]", "</b></font>")

    return _font_wrap(text)

# ═══════════════════════════════════════════════════════════════════════
# CUSTOM FLOWABLES
# ═══════════════════════════════════════════════════════════════════════
_anchor_counter = [0]
_outline_level = [-1]
_cur_chapter = [""]


class MedicalResultFlowable(Flowable):
    """Modern medical report result style: bold text, arrows, and optional background pills."""
    def __init__(self, value="", arrow="", status_text="", color="#2D3748", width=62, height=26, show_pill=True):
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
        import re
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
        import re
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
        from reportlab.lib.colors import Color

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
        from reportlab.lib.colors import Color

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

class HRule(Flowable):
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

# ═══════════════════════════════════════════════════════════════════════
# PDF BUILDER
# ═══════════════════════════════════════════════════════════════════════
class PDFBuilder:
    def __init__(self, config):
        self.cfg = config
        self.T = config["theme"]  # resolved theme colors
        self.L = self.T["layout"]  # layout parameters
        self.page_w, self.page_h = config["page_size"]
        lm, rm, tm, bm = self.L["margins"]
        self.lm, self.rm, self.tm, self.bm = lm*mm, rm*mm, tm*mm, bm*mm
        self.body_w = self.page_w - self.lm - self.rm
        self.body_h = self.page_h - self.tm - self.bm
        self.accent_hex = config.get("accent_hex", "#CC785C")
        self.ST = self._build_styles()

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

    # ── Page callbacks ──
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
                logo_w = 40*mm
                c.drawImage(img_src, cx - logo_w/2, self.page_h - 40*mm, width=logo_w, height=logo_w/3, preserveAspectRatio=True, mask='auto', anchor='c')
            except Exception:
                pass


        title_y = self.page_h * 0.62
        c.setFillColor(T["ink"])
        btm = _draw_mixed(c, cx, title_y, self.cfg.get("title", "Document"), 38, anchor="center", max_w=self.page_w - 40*mm)

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

        dt = self.cfg.get("date", str(date.today()))
        c.setFillColor(T["ink_faded"]); _draw_mixed(c, cx, 28*mm, dt, 9, anchor="center")

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
        btm = _draw_mixed(c, lx, title_y, self.cfg.get("title", "Document"), 34, anchor="left", max_w=self.page_w - lx - 20*mm)

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
        btm = _draw_mixed(c, cx, title_y, self.cfg.get("title", "Document"), 32, anchor="center", max_w=self.page_w - 50*mm)

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
            ch = _cur_chapter[0]
            if ch:
                c.setFillColor(white)
                _draw_mixed(c, self.page_w - self.rm, self.page_h - 6*mm, ch[:40], 7.5, anchor="right")
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
                except Exception:
                    pass

            header_title = self.cfg.get("header_title", "")
            if header_title:
                _draw_mixed(c, title_lx, self.page_h - 15*mm, header_title, 8)

            ch = _cur_chapter[0]
            if ch:
                _draw_mixed(c, self.page_w - self.rm, self.page_h - 18*mm, ch[:40], 8, anchor="right")
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

        # Header left: report title
        header_title = self.cfg.get("header_title", "")
        if header_title:
            _draw_mixed(c, self.lm, self.page_h - 18*mm, header_title, 8)

        # Header right: "目  录"
        c.setFont("CJK", 8)
        c.drawRightString(self.page_w - self.rm, self.page_h - 18*mm, "\u76ee  \u5f55")

        # Footer
        c.setStrokeColor(T["border"])
        c.line(self.lm, self.bm - 8*mm, self.page_w - self.rm, self.bm - 8*mm)
        c.setFillColor(T["accent"]); c.setFont("Serif", 9)
        c.drawCentredString(self.page_w/2, self.bm - 16*mm, f"\u2014  {pg}  \u2014")

        c.restoreState()

    # ── Table parser ──
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
            return Paragraph(md_inline(cell, self.accent_hex), style)

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

    # ── Markdown → Story ──
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
                cm = ChapterMark(title, level=0); story.append(cm)
                
                # Normal top spacer instead of centered
                h1_top_ratio = self.cfg.get("h2_top_ratio", 0.05)
                story.append(Spacer(1, self.body_h * h1_top_ratio))
                
                hdeco = self.L["heading_decoration"]
                story.append(Paragraph(md_inline(title, ah), ST['part']))
                
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
                story.append(Paragraph(md_inline(title, ah), ST['chapter']))
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
                story.append(Paragraph(md_inline(stripped[4:].strip(), ah), ST['h3']))
                story.append(Spacer(1, 1*mm))
                i += 1; continue

            # H4-H6 Heading
            if stripped.startswith('#### '):
                story.append(Spacer(1, 2*mm))
                story.append(Paragraph(md_inline(stripped[5:].strip(), ah), ST['h3']))
                story.append(Spacer(1, 1*mm))
                i += 1; continue
            if stripped.startswith('##### '):
                story.append(Spacer(1, 2*mm))
                story.append(Paragraph(md_inline(stripped[6:].strip(), ah), ST['h3']))
                story.append(Spacer(1, 1*mm))
                i += 1; continue
            if stripped.startswith('###### '):
                story.append(Spacer(1, 1*mm))
                story.append(Paragraph(md_inline(stripped[7:].strip(), ah), ST['h3']))
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
                            img_elements.append(Paragraph(_font_wrap(esc(img_caption)), cap_style))
                        story.append(KeepTogether(img_elements))
                        story.append(Spacer(1, 4*mm))
                    except Exception as e:
                        story.append(Paragraph(_font_wrap(esc(f"[Image: {img_caption or img_path}]")), ST['body']))
                i += 1; continue

            # Bullets
            if stripped.startswith('- ') or stripped.startswith('* '):
                story.append(Spacer(1, 1*mm))
                while i < len(lines):
                    l = lines[i].strip()
                    if l.startswith('- ') or l.startswith('* '):
                        txt = l[2:].strip()
                        story.append(Paragraph(md_inline(txt, ah), ST['bullet']))
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
                        story.append(Paragraph(md_inline(txt, ah), ST['bullet'], bulletText=m.group(1)+'.'))
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
                story.append(Paragraph(md_inline(merged, ah), ST['body_indent']))
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
                story.append(Paragraph(md_inline(merged, ah), ST['body']))
            else:
                # If we didn't match anything else and plines is empty,
                # we MUST increment i to avoid infinite loop.
                i += 1

        return story, toc

    def build_toc(self, toc):
        ST = self.ST; ah = self.accent_hex; ink = self.T["ink"]
        s = [Spacer(1, 15*mm)]
        s.append(Paragraph(md_inline("\u76ee    \u5f55", ah), ST['part']))
        s.append(HRule(self.body_w * 0.12, 1, self.T["accent"]))
        s.append(Spacer(1, 8*mm))
        ink_hex = f"#{int(ink.red*255):02x}{int(ink.green*255):02x}{int(ink.blue*255):02x}" if hasattr(ink,'red') else "#181818"
        for etype, title, key in toc:
            style = ST['toc1'] if etype == 'part' else ST['toc2']
            linked = f"<a href=\"#{key}\" color=\"{ink_hex}\">{_font_wrap(esc(title))}</a>"
            s.append(Paragraph(linked, style))
        return s

    # ── Build PDF ──
    def build(self, md_text, output_path):
        register_fonts()
        print("Parsing markdown...")
        story_content, toc = self.parse_md(md_text)
        print(f"  {len(story_content)} elements, {len(toc)} TOC entries")

        body_frame = Frame(self.lm, self.bm, self.body_w, self.body_h, id='body')
        full_frame = Frame(0, 0, self.page_w, self.page_h, leftPadding=0,
                           rightPadding=0, topPadding=0, bottomPadding=0, id='full')

        doc = BaseDocTemplate(output_path, pagesize=(self.page_w, self.page_h),
                              leftMargin=self.lm, rightMargin=self.rm,
                              topMargin=self.tm, bottomMargin=self.bm,
                              title=self.cfg.get("title", ""),
                              author=self.cfg.get("author", ""))

        templates = [
            PageTemplate(id='normal', frames=[body_frame], onPage=self._normal_page),
        ]

        story = []
        has_frontis = self.cfg.get("frontispiece") and os.path.exists(self.cfg["frontispiece"])
        has_banner = self.cfg.get("banner") and os.path.exists(self.cfg["banner"])
        has_toc = self.cfg.get("toc", True) and toc

        # Cover page
        if self.cfg.get("cover", True):
            templates.insert(0, PageTemplate(id='cover', frames=[full_frame], onPage=self._cover_page))
            story.append(Spacer(1, self.page_h))

            # Determine next page after cover
            if has_frontis:
                templates.append(PageTemplate(id='frontis', frames=[full_frame], onPage=self._frontispiece_page))
                story.append(NextPageTemplate('frontis'))
                story.append(PageBreak())
                story.append(Spacer(1, self.page_h))
                # After frontispiece, go to toc or normal
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

        # TOC
        if has_toc:
            story.extend(self.build_toc(toc))
            story.append(NextPageTemplate('normal'))
            story.append(PageBreak())

        # Strip leading PageBreak from body content to avoid blank page
        while story_content and isinstance(story_content[0], (PageBreak, Spacer)):
            if isinstance(story_content[0], PageBreak):
                story_content.pop(0)
                break
            story_content.pop(0)

        story.extend(story_content)

        # Back cover
        if has_banner:
            templates.append(PageTemplate(id='backcover', frames=[full_frame], onPage=self._backcover_page))
            story.append(NextPageTemplate('backcover'))
            story.append(PageBreak())
            story.append(Spacer(1, 1))

        doc.addPageTemplates(templates)
        print("Building PDF...")
        doc.build(story)
        size = os.path.getsize(output_path)
        print(f"Done! {output_path} ({size/1024/1024:.1f} MB)")

# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="md2pdf \u2014 Markdown to Professional PDF")
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
