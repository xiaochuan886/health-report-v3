"""
pdf_fonts.py — Cross-platform font discovery and registration for ReportLab.

CJK fonts (思源黑体 / Noto Sans CJK SC) are bundled in ``fonts/`` alongside
this module.  Latin and Mono fonts fall back to system paths.
"""

import os
import sys
import platform as _platform
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_PLAT = _platform.system()  # "Darwin", "Linux", "Windows"

# ── Bundled font directory ──────────────────────────────────────────────
_BUNDLED_DIR = Path(__file__).parent / "fonts"
_VF_INSTANCE_DIR = _BUNDLED_DIR / "instances"


def _find_font(candidates):
    """Return first existing path from candidates list.
    Each candidate is either a string path or a (path, subfontIndex) tuple."""
    for c in candidates:
        path = c[0] if isinstance(c, tuple) else c
        if os.path.exists(path):
            return c
    return None


# Font candidates per role — ordered by preference, first match wins.
# CJK roles prefer bundled Noto Sans CJK SC (思源黑体).
# Latin/Mono roles rely on system font paths.
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
        str(_BUNDLED_DIR / "NotoSansCJKsc-Regular.ttf"),                        # Bundled 思源黑体 Regular (wght=400)
        str(_BUNDLED_DIR / "NotoSansCJKsc-VF.ttf"),                            # Fallback: variable TTF
        ("/System/Library/Fonts/STHeiti Light.ttc", 0),                           # macOS fallback
        "C:/Windows/Fonts/msyh.ttc",                                             # Windows fallback
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",               # Linux fallback
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ],
    "CJKBold": [
        str(_BUNDLED_DIR / "NotoSansCJKsc-Bold.ttf"),                           # Bundled 思源黑体 Bold (wght=700)
        str(_BUNDLED_DIR / "NotoSansCJKsc-VF.ttf"),                            # Fallback: variable TTF
        ("/System/Library/Fonts/STHeiti Medium.ttc", 0),                          # macOS fallback
        "C:/Windows/Fonts/msyhbd.ttc",                                           # Windows fallback
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",                  # Linux fallback
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


def _build_vf_instance(vf_path: str, weight: int) -> str | None:
    """Materialize a static TTF from a variable font at target weight.

    ReportLab's TTFont does not expose axis selection for variable fonts,
    so we instantiate fixed-weight files (e.g. wght=400/700) via fontTools.
    Returns generated file path on success, or None on failure.
    """
    try:
        from fontTools.ttLib import TTFont as FTFont
        from fontTools.varLib import instancer
    except Exception:
        return None

    try:
        _VF_INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
        vf = Path(vf_path)
        out = _VF_INSTANCE_DIR / f"{vf.stem}-w{int(weight)}.ttf"
        if out.exists():
            return str(out)

        font = FTFont(vf_path)
        if "fvar" not in font:
            return None

        axes = {a.axisTag: a for a in font["fvar"].axes}
        wght_axis = axes.get("wght")
        if wght_axis is None:
            return None

        target = min(max(float(weight), wght_axis.minValue), wght_axis.maxValue)
        instanced = instancer.instantiateVariableFont(font, {"wght": target}, inplace=False)
        instanced.save(str(out))
        return str(out)
    except Exception:
        return None


def _vf_instance_path(vf_stem: str, weight: int) -> str:
    return str(_VF_INSTANCE_DIR / f"{vf_stem}-w{int(weight)}.ttf")


def register_fonts():
    """Discover and register all font roles. Prints warnings for missing fonts."""
    candidates_map = {name: list(cands) for name, cands in _FONT_CANDIDATES.items()}

    # Prefer variable-font instances for CJK when available.
    # This avoids relying on potentially mismatched static files and gives
    # deterministic control over Chinese weight (regular/bold).
    vf_path = str(_BUNDLED_DIR / "NotoSansCJKsc-VF.ttf")
    vf_stem = Path(vf_path).stem
    if os.path.exists(vf_path):
        cjk_regular = _vf_instance_path(vf_stem, 400)
        cjk_bold = _vf_instance_path(vf_stem, 700)

        # If pre-generated files do not exist, lazily generate them once.
        if not os.path.exists(cjk_regular):
            cjk_regular = _build_vf_instance(vf_path, 400)
        if not os.path.exists(cjk_bold):
            cjk_bold = _build_vf_instance(vf_path, 700)

        if cjk_regular:
            candidates_map["CJK"].insert(0, cjk_regular)
        if cjk_bold:
            candidates_map["CJKBold"].insert(0, cjk_bold)

    missing = []
    for name, candidates in candidates_map.items():
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

    # Register optional CJK weight aliases from pre-generated VF instances.
    # Example aliases: CJK100, CJK200, ... CJK900
    if os.path.exists(vf_path):
        for w in (100, 200, 300, 400, 500, 600, 700, 800, 900):
            alias = f"CJK{w}"
            inst = _vf_instance_path(vf_stem, w)
            if not os.path.exists(inst):
                continue
            try:
                if alias not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(alias, inst))
            except Exception as e:
                print(f"Warning: Font {alias} — {e}", file=sys.stderr)
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
