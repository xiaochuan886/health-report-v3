"""
pdf_utils.py — CJK text utilities, image helpers, and inline Markdown rendering.

Provides:
  - CJK character detection
  - Mixed CJK/Latin canvas drawing helpers
  - Image transparency flattening
  - Inline Markdown → ReportLab XML conversion
  - Code block escaping
"""

import re
import os
import sys


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
    """Return True if character falls within a known CJK Unicode range."""
    cp = ord(ch)
    for lo, hi in _CJK_RANGES:
        if lo <= cp <= hi:
            return True
    return False


def _font_wrap(text, cjk_font="CJK"):
    """Wrap CJK runs in <font name='...'> tags for ReportLab Paragraph."""
    out, buf, in_cjk = [], [], False
    for ch in text:
        c = _is_cjk(ch)
        if c != in_cjk and buf:
            seg = ''.join(buf)
            out.append(f"<font name='{cjk_font}'>{seg}</font>" if in_cjk else seg)
            buf = []
        buf.append(ch); in_cjk = c
    if buf:
        seg = ''.join(buf)
        out.append(f"<font name='{cjk_font}'>{seg}</font>" if in_cjk else seg)
    return ''.join(out)


def _draw_mixed(c, x, y, text, size, anchor="left", max_w=0, cjk_font="CJK", latin_font="Sans"):
    """Draw mixed CJK/Latin text on canvas with font switching.
    If max_w > 0, wrap into multiple lines. Returns bottom y of drawn text."""
    if max_w > 0:
        return _draw_mixed_wrap(c, x, y, text, size, anchor, max_w, cjk_font=cjk_font, latin_font=latin_font)
    segs, buf, in_cjk = [], [], False
    for ch in text:
        cj = _is_cjk(ch)
        if cj != in_cjk and buf:
            segs.append((cjk_font if in_cjk else latin_font, ''.join(buf))); buf = []
        buf.append(ch); in_cjk = cj
    if buf: segs.append((cjk_font if in_cjk else latin_font, ''.join(buf)))
    total_w = sum(c.stringWidth(t, f, size) for f, t in segs)
    if anchor == "right": x -= total_w
    elif anchor == "center": x -= total_w / 2
    for font, txt in segs:
        c.setFont(font, size); c.drawString(x, y, txt)
        x += c.stringWidth(txt, font, size)


def _measure_mixed(c, text, size, cjk_font="CJK", latin_font="Sans"):
    """Measure width of mixed CJK/Latin text."""
    w = 0
    buf, in_cjk = [], False
    for ch in text:
        cj = _is_cjk(ch)
        if cj != in_cjk and buf:
            w += c.stringWidth(''.join(buf), cjk_font if in_cjk else latin_font, size); buf = []
        buf.append(ch); in_cjk = cj
    if buf: w += c.stringWidth(''.join(buf), cjk_font if in_cjk else latin_font, size)
    return w


def _draw_mixed_wrap(c, x, y, text, size, anchor, max_w, cjk_font="CJK", latin_font="Sans"):
    """Word-wrap mixed text into multiple lines, shrink font if single word overflows."""
    words = text.split(' ')
    # Shrink font until longest word fits (floor 16pt)
    while size > 16:
        longest = max(_measure_mixed(c, w, size, cjk_font=cjk_font, latin_font=latin_font) for w in words)
        if longest <= max_w: break
        size -= 1
    # Greedy line breaking
    lines, cur = [], []
    cur_w = 0
    space_w = c.stringWidth(' ', 'Sans', size)
    for word in words:
        ww = _measure_mixed(c, word, size, cjk_font=cjk_font, latin_font=latin_font)
        test_w = cur_w + (space_w if cur else 0) + ww
        if cur and test_w > max_w:
            lines.append(' '.join(cur)); cur = [word]; cur_w = ww
        else:
            cur.append(word); cur_w = test_w
    if cur: lines.append(' '.join(cur))
    # Draw lines downward from y (top line at y)
    line_h = size * 1.3
    for i, line in enumerate(lines):
        _draw_mixed(c, x, y - i * line_h, line, size, anchor, cjk_font=cjk_font, latin_font=latin_font)
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
# IMAGE UTILITIES
# ═══════════════════════════════════════════════════════════════════════
def _flatten_transparency(img_path: str):
    """Convert transparent PNG (or images with alpha/transparency) to white background
    for consistent PDF rendering. Handles RGBA, LA, PA, and P (with trans) modes.

    Returns a PIL Image (RGB) when conversion is needed, or the original path when
    no conversion is needed / PIL is missing. Both are accepted by ReportLab's
    drawImage / RLImage / ImageReader. Uses in-memory image instead of temp files
    to avoid /tmp leaks on repeated builds.
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

            # Downsample oversized images — PDF only needs ~300 dpi at target size
            max_px = 1500
            if max(rgba.size) > max_px:
                ratio = max_px / max(rgba.size)
                new_size = (int(rgba.size[0] * ratio), int(rgba.size[1] * ratio))
                rgba = rgba.resize(new_size, PILImage.LANCZOS)

            # Composite onto pure white background
            bg = PILImage.new('RGB', rgba.size, (255, 255, 255))
            bg.paste(rgba, mask=rgba.split()[3])
            return bg  # 返回内存中的 PIL Image，避免临时文件泄漏
    except Exception as e:
        print(f"Warning: flatten transparency failed for {img_path}: {e}", file=sys.stderr)
    return img_path


# ═══════════════════════════════════════════════════════════════════════
# INLINE MARKDOWN + ESCAPING
# ═══════════════════════════════════════════════════════════════════════
def esc(text):
    """Escape text for ReportLab XML, preserving <br/> and <br> tags."""
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


def md_inline(text, accent_hex="#CC785C", cjk_font="CJK"):
    """Convert inline Markdown syntax to ReportLab XML markup."""
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

    return _font_wrap(text, cjk_font=cjk_font)
