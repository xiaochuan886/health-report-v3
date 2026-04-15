"""
pdf_themes.py — Color themes and layout presets for md2pdf.

Each theme defines colors (canvas, ink, accent, border) and an optional
'layout' dict that overrides _DEFAULT_LAYOUT keys.

Layout keys:
  margins: (left, right, top, bottom) in mm
  body_font: "Serif" or "Sans"
  body_size / body_leading: body text dimensions
  h1_size / h2_size / h3_size: heading sizes
  heading_align: "center" or "left"
  heading_decoration: "rules" | "underline" | "dot" | "none"
  header_style: "full" | "minimal" | "none"
  code_style: "bg" (background fill) | "border" (left border only)
  cover_style: "centered" | "left-aligned" | "minimal"
  page_decoration: "none" | "top-bar" | "left-stripe" | "side-rule" | "corner-marks"
"""

import json
import os
import sys

from reportlab.lib.colors import Color, HexColor

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
    """Load and resolve a theme by name or from a JSON file.

    Returns a dict with resolved Color objects and merged layout settings.
    """
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
