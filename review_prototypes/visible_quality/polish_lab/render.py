from __future__ import annotations

from html import escape

from .models import Box, CaptionLayout, StoryArchetype

W, H = 1080, 1920
BG = "#07101E"
TEXT = "#F8FAFC"
MUTED = "#9FB0C8"
ACCENT = "#F2C14E"
CYAN = "#63D8E8"
RED = "#F06464"


def _text(x: float, y: float, value: str, size: int, color: str = TEXT, anchor: str = "middle") -> str:
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="Arial,sans-serif" font-size="{size}" font-weight="900" fill="{color}">{escape(value)}</text>'


def _caption_svg(caption: CaptionLayout) -> str:
    lines = caption.text.split("\n")
    body = f'<rect x="{caption.box.x}" y="{caption.box.y}" width="{caption.box.width}" height="{caption.box.height}" rx="34" fill="#07101E" opacity="{caption.style.background_opacity}"/>'
    y = caption.box.y + caption.style.line_height
    for line in lines:
        body += _text(caption.box.x + 34, y, line, caption.style.font_size, TEXT, "start")
        y += caption.style.line_height
    return body


def render_polished_frame(archetype: StoryArchetype, mechanic: str, caption: CaptionLayout, hero_box: Box, progress: float = 1.0) -> str:
    p = max(0.0, min(1.0, progress))
    body = f'<rect width="{W}" height="{H}" fill="{BG}"/><rect x="{hero_box.x}" y="{hero_box.y}" width="{hero_box.width}" height="{hero_box.height}" rx="56" fill="#111C31"/>'
    if mechanic in {"receipt_roll", "before_after_collision", "callback_bridge"}:
        body += f'<rect x="170" y="370" width="740" height="{420 + 420*p}" rx="34" fill="#FAF3DF"/>'
        body += _text(540, 530, "$680 → $1,030", 86, "#17272E")
        body += f'<path d="M250 710 C430 {820-180*p}, 650 {620+180*p}, 830 900" fill="none" stroke="{RED}" stroke-width="22"/>'
    elif mechanic in {"share_squeeze", "waffle_takeover", "opening_grid_resolves"}:
        for i in range(20):
            x = 140 + (i % 5) * 155
            y = 430 + (i // 5) * 155
            fill = ACCENT if i < int(20*p*.8) else "#25324A"
            body += f'<rect x="{x}" y="{y}" width="122" height="122" rx="24" fill="{fill}"/>'
        body += _text(540, 1130, "80%", 118, ACCENT)
    elif mechanic in {"rank_race", "finish_gap", "winner_gap_callback"}:
        widths = (720, 540, 390, 280)
        for i, width in enumerate(widths):
            y = 430 + i * 220
            body += f'<rect x="150" y="{y}" width="{width*p}" height="110" rx="55" fill="{CYAN if i else ACCENT}"/>'
            body += _text(160, y+78, f"#{i+1}", 46, TEXT, "start")
    elif mechanic in {"scale_collision", "column_shove", "side_by_side_resolution"}:
        body += f'<circle cx="{310 + 160*p}" cy="790" r="150" fill="{CYAN}"/>'
        body += f'<circle cx="{820 - 90*p}" cy="790" r="250" fill="{ACCENT}"/>'
        body += _text(310 + 160*p, 820, "42%", 72)
        body += _text(820 - 90*p, 820, "68%", 82, "#17272E")
    else:
        body += f'<path d="M220 1140 A330 330 0 0 1 {220+660*p} 1140" fill="none" stroke="{ACCENT}" stroke-width="80" stroke-linecap="round"/>'
        body += _text(540, 860, "73%", 140, ACCENT)
    body += _caption_svg(caption)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><title>{escape(archetype.name)} {escape(mechanic)}</title>{body}</svg>'
