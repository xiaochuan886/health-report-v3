"""
pdf_fonts.py — Cross-platform font discovery and registration for ReportLab.

Supports macOS, Windows, and Linux with CJK/Latin/Mono font families.
"""

import os
import sys
import platform as _platform

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

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
    """Discover and register all font roles. Prints warnings for missing fonts."""
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
