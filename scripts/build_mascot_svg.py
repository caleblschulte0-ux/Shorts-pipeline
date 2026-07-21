#!/usr/bin/env python3
"""The channel host mascot — 'Data', a teal monster-professor in a lab coat,
drawn as parametric SVG so he is byte-for-byte identical in every pose.

This is the SINGLE SOURCE OF TRUTH for the mascot's look. It emits one
standalone SVG per pose. Those SVGs are rasterised once to transparent
square PNGs under ``assets/mascot/host/`` (committed), which the video
renderer (`data_learning/mascot.py`) composites at run time — so CI needs
no SVG rasteriser, and the character can never drift between renders.

The character is a fixed rig: the head, horns, eyes, glasses, lab coat,
tie and legs are the same code in every pose; only the arms, eyes and
mouth change (that's expression, not a different character). New poses =
new arm coordinates, nothing more.

    python scripts/build_mascot_svg.py            # write assets/mascot/host/*.svg
    python scripts/build_mascot_svg.py --png      # also rasterise to PNG (needs
                                                  # cairosvg OR playwright)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "mascot" / "host"

TEAL = "#38B6A6"; TEALHI = "#57CBBC"; MINT = "#C9F3E9"
OUTLINE = "#17272E"; WHITE = "#FFFFFF"; PUPIL = "#17272E"
RED = "#EF5C46"; MOUTH = "#3B2126"; TONGUE = "#F58C8C"
COAT = "#F5F8F7"; COATSH = "#DCE7E3"; SHIRT = "#D8E4E0"; PEN = "#2E7DD1"

SW = 6
LEX, REX, EY = 144, 196, 110
CX = 170


def limb(sx, sy, wx, wy, bend, w_out, w_in, hand_r, inner=TEAL, hand=TEAL):
    mx, my = (sx + wx) / 2, (sy + wy) / 2
    dx, dy = wx - sx, wy - sy
    L = max((dx * dx + dy * dy) ** 0.5, 1)
    cx_, cy_ = mx - dy / L * bend, my + dx / L * bend
    d = f"M{sx},{sy} Q{cx_:.0f},{cy_:.0f} {wx},{wy}"
    s = (f'<path d="{d}" fill="none" stroke="{OUTLINE}" stroke-width="{w_out}" '
         f'stroke-linecap="round"/>'
         f'<path d="{d}" fill="none" stroke="{inner}" stroke-width="{w_in}" '
         f'stroke-linecap="round"/>')
    if hand_r:
        s += (f'<circle cx="{wx}" cy="{wy}" r="{hand_r}" fill="{hand}" '
              f'stroke="{OUTLINE}" stroke-width="{SW}"/>')
    return s


def arm(sx, sy, wx, wy, bend):
    return limb(sx, sy, wx, wy, bend, 32, 23, 19, inner=COAT, hand=TEAL)


def horns():
    return (f'<path d="M138,66 Q134,34 148,24 Q160,34 158,66 Z" fill="{TEAL}" '
            f'stroke="{OUTLINE}" stroke-width="{SW}" stroke-linejoin="round"/>'
            f'<path d="M202,66 Q206,34 192,24 Q180,34 182,66 Z" fill="{TEAL}" '
            f'stroke="{OUTLINE}" stroke-width="{SW}" stroke-linejoin="round"/>')


def legs():
    return (limb(152, 300, 138, 352, 0, 36, 27, 0) +
            limb(188, 300, 202, 352, 0, 36, 27, 0))


def feet():
    return (f'<ellipse cx="136" cy="356" rx="28" ry="14" fill="{TEAL}" '
            f'stroke="{OUTLINE}" stroke-width="{SW}"/>'
            f'<ellipse cx="204" cy="356" rx="28" ry="14" fill="{TEAL}" '
            f'stroke="{OUTLINE}" stroke-width="{SW}"/>')


def torso():
    return (f'<rect x="118" y="190" width="104" height="112" rx="40" '
            f'fill="{TEAL}" stroke="{OUTLINE}" stroke-width="{SW}"/>')


def coat():
    left = ("M122,210 Q122,199 132,199 L152,199 L165,247 L165,320 "
            "L134,320 Q122,320 122,309 Z")
    right = ("M218,210 Q218,199 208,199 L188,199 L175,247 L175,320 "
             "L206,320 Q218,320 218,309 Z")
    return (f'<rect x="151" y="198" width="38" height="120" rx="14" '
            f'fill="{SHIRT}"/>'
            f'<path d="{left}" fill="{COAT}" stroke="{OUTLINE}" '
            f'stroke-width="{SW}" stroke-linejoin="round"/>'
            f'<path d="{right}" fill="{COAT}" stroke="{OUTLINE}" '
            f'stroke-width="{SW}" stroke-linejoin="round"/>'
            f'<path d="M152,199 L165,247" fill="none" stroke="{COATSH}" '
            f'stroke-width="4"/>'
            f'<path d="M188,199 L175,247" fill="none" stroke="{COATSH}" '
            f'stroke-width="4"/>'
            f'<rect x="182" y="270" width="26" height="22" rx="4" fill="none" '
            f'stroke="{OUTLINE}" stroke-width="4"/>'
            f'<rect x="190" y="262" width="6" height="16" rx="2" fill="{PEN}" '
            f'stroke="{OUTLINE}" stroke-width="3"/>')


def neck():
    return (f'<rect x="153" y="166" width="34" height="36" rx="12" '
            f'fill="{TEAL}" stroke="{OUTLINE}" stroke-width="{SW}"/>')


def head():
    return (f'<circle cx="170" cy="114" r="62" fill="{TEAL}" '
            f'stroke="{OUTLINE}" stroke-width="{SW}"/>'
            f'<ellipse cx="146" cy="80" rx="22" ry="15" fill="{TEALHI}" '
            f'opacity="0.6"/>')


def cheeks():
    return (f'<ellipse cx="131" cy="137" rx="13" ry="8" fill="#8CE0D1" '
            f'opacity="0.55"/>'
            f'<ellipse cx="209" cy="137" rx="13" ry="8" fill="#8CE0D1" '
            f'opacity="0.55"/>')


def _frame(ex):
    return (f'<rect x="{ex-24}" y="{EY-21}" width="48" height="42" rx="12" '
            f'fill="none" stroke="{OUTLINE}" stroke-width="{SW}"/>')


def glasses():
    return (_frame(LEX) + _frame(REX) +
            f'<path d="M{LEX+24},{EY-3} L{REX-24},{EY-3}" stroke="{OUTLINE}" '
            f'stroke-width="{SW}" stroke-linecap="round"/>'
            f'<path d="M{LEX-24},{EY-3} L{LEX-42},{EY+3}" stroke="{OUTLINE}" '
            f'stroke-width="{SW}" stroke-linecap="round"/>'
            f'<path d="M{REX+24},{EY-3} L{REX+42},{EY+3}" stroke="{OUTLINE}" '
            f'stroke-width="{SW}" stroke-linecap="round"/>')


def tie():
    return (f'<path d="M160,182 L180,182 L174,196 L166,196 Z" fill="{RED}" '
            f'stroke="{OUTLINE}" stroke-width="5" stroke-linejoin="round"/>'
            f'<path d="M166,196 L174,196 L179,246 L170,260 L161,246 Z" '
            f'fill="{RED}" stroke="{OUTLINE}" stroke-width="5" '
            f'stroke-linejoin="round"/>')


def brow(ex):
    return (f'<path d="M{ex-15},{EY-32} Q{ex},{EY-37} {ex+15},{EY-32}" '
            f'fill="none" stroke="{OUTLINE}" stroke-width="6" '
            f'stroke-linecap="round"/>')


def eye_open(ex, pdx, pdy, r=22):
    return (brow(ex) +
            f'<circle cx="{ex}" cy="{EY}" r="{r}" fill="{WHITE}" '
            f'stroke="{OUTLINE}" stroke-width="5"/>'
            f'<circle cx="{ex+pdx}" cy="{EY+pdy}" r="9" fill="{PUPIL}"/>'
            f'<circle cx="{ex+pdx+3}" cy="{EY+pdy-3}" r="3" fill="{WHITE}"/>')


def eye_closed(ex):
    return (brow(ex) +
            f'<path d="M{ex-15},{EY+4} Q{ex},{EY-11} {ex+15},{EY+4}" '
            f'fill="none" stroke="{OUTLINE}" stroke-width="6" '
            f'stroke-linecap="round"/>')


def mouth_smile():
    return (f'<path d="M156,142 Q170,158 184,142" fill="none" '
            f'stroke="{OUTLINE}" stroke-width="6" stroke-linecap="round"/>')


def mouth_o():
    return (f'<ellipse cx="170" cy="148" rx="11" ry="14" fill="{MOUTH}" '
            f'stroke="{OUTLINE}" stroke-width="5"/>')


def mouth_grin():
    return (f'<path d="M150,140 Q170,138 190,140 Q184,166 170,168 '
            f'Q156,166 150,140 Z" fill="{MOUTH}" stroke="{OUTLINE}" '
            f'stroke-width="5" stroke-linejoin="round"/>'
            f'<path d="M157,157 Q170,176 183,157 Z" fill="{TONGUE}"/>')


def mouth_open_smile():
    return (f'<path d="M152,141 Q170,138 188,141 Q181,162 170,164 '
            f'Q159,162 152,141 Z" fill="{MOUTH}" stroke="{OUTLINE}" '
            f'stroke-width="5" stroke-linejoin="round"/>')


def mouth_line():
    return (f'<path d="M158,148 Q170,154 182,148" fill="none" '
            f'stroke="{OUTLINE}" stroke-width="6" stroke-linecap="round"/>')


def mouth_pursed():
    return (f'<ellipse cx="170" cy="148" rx="7" ry="6" fill="{MOUTH}" '
            f'stroke="{OUTLINE}" stroke-width="5"/>')


SHL, SHR = (128, 206), (212, 206)

POSES = {
 "idle":  (lambda: arm(*SHL, 114, 300, -4) + arm(*SHR, 226, 300, 4),
           lambda: eye_open(LEX, 0, 2) + eye_open(REX, 0, 2), mouth_smile),
 "point": (lambda: arm(*SHL, 150, 252, -14) + arm(*SHR, 286, 150, 8),
           lambda: eye_open(LEX, 5, 0) + eye_open(REX, 5, 0), mouth_open_smile),
 "shock": (lambda: arm(*SHL, 116, 90, -14) + arm(*SHR, 224, 90, 14),
           lambda: eye_open(LEX, 0, 0, 25) + eye_open(REX, 0, 0, 25), mouth_o),
 "laugh": (lambda: arm(*SHL, 150, 252, -6) + arm(*SHR, 218, 272, 8),
           lambda: eye_closed(LEX) + eye_closed(REX), mouth_grin),
 "think": (lambda: arm(*SHL, 150, 252, -14) + arm(*SHR, 176, 158, 14),
           lambda: eye_open(LEX, 2, -5) + eye_open(REX, 2, -5), mouth_pursed),
 "cheer": (lambda: arm(*SHL, 116, 82, -12) + arm(*SHR, 224, 82, 12),
           lambda: eye_open(LEX, 0, -2) + eye_open(REX, 0, -2), mouth_open_smile),
 "duck":  (lambda: arm(*SHL, 138, 316, -6) + arm(*SHR, 202, 316, 6),
           lambda: eye_open(LEX, 0, 6) + eye_open(REX, 0, 6), mouth_line),
 "ride":  (lambda: arm(*SHL, 152, 240, -18) + arm(*SHR, 188, 240, 18),
           lambda: eye_open(LEX, 0, 3) + eye_open(REX, 0, 3), mouth_open_smile),
}

INVARIANT_BACK = (horns() + legs() + feet() + torso() + coat() +
                  neck() + head() + cheeks())


def pose_svg(pose: str) -> str:
    arms, eyes, mouth = POSES[pose]
    inner = f'{INVARIANT_BACK}{eyes()}{glasses()}{mouth()}{tie()}{arms()}'
    inner = inner.replace(TEAL, f'url(#T{pose})').replace(COAT, f'url(#C{pose})')
    defs = (f'<defs>'
            f'<linearGradient id="T{pose}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="#4AC6B4"/>'
            f'<stop offset="1" stop-color="#2E9C8D"/></linearGradient>'
            f'<linearGradient id="C{pose}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="#FFFFFF"/>'
            f'<stop offset="1" stop-color="#E4ECE9"/></linearGradient>'
            f'<radialGradient id="G{pose}" cx="0.5" cy="0.5" r="0.5">'
            f'<stop offset="0" stop-color="#0D1A17" stop-opacity="0.30"/>'
            f'<stop offset="1" stop-color="#0D1A17" stop-opacity="0"/>'
            f'</radialGradient></defs>')
    ground = f'<ellipse cx="170" cy="373" rx="82" ry="13" fill="url(#G{pose})"/>'
    return (f'<svg viewBox="0 0 340 388" xmlns="http://www.w3.org/2000/svg" '
            f'role="img" aria-label="Data mascot {pose} pose">'
            f'{defs}{ground}{inner}</svg>')


def write_svgs() -> list[Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    out = []
    for p in POSES:
        f = OUT / f"{p}.svg"
        f.write_text(pose_svg(p))
        out.append(f)
    return out


def _rasterise(paths: list[Path]) -> None:
    """Best-effort SVG -> square transparent PNG (cairosvg, else playwright)."""
    from PIL import Image
    import io
    def to_png_bytes(svg: str) -> bytes:
        try:
            import cairosvg
            return cairosvg.svg2png(bytestring=svg.encode(), output_width=680,
                                    output_height=776)
        except Exception:
            from playwright.sync_api import sync_playwright
            html = ("<!doctype html><body style='margin:0'>"
                    f"<div style='width:680px'>{svg}</div></body>")
            with sync_playwright() as pw:
                import os
                exe = "/opt/pw-browsers/chromium"
                b = (pw.chromium.launch(executable_path=exe)
                     if os.path.exists(exe) else pw.chromium.launch())
                pg = b.new_page(viewport={"width": 680, "height": 776},
                                device_scale_factor=2)
                pg.set_content(html); pg.wait_for_timeout(200)
                png = pg.screenshot(omit_background=True,
                                    clip={"x": 0, "y": 0, "width": 680,
                                          "height": 776})
                b.close()
                return png
    for p in paths:
        img = Image.open(io.BytesIO(to_png_bytes(p.read_text()))).convert("RGBA")
        side = max(img.size)
        sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        sq.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
        sq = sq.resize((600, 600), Image.LANCZOS)
        sq.save(p.with_suffix(".png"))
        print(f"  rasterised {p.with_suffix('.png').name}")


def main() -> int:
    paths = write_svgs()
    print(f"wrote {len(paths)} pose SVGs -> {OUT}")
    if "--png" in sys.argv:
        _rasterise(paths)
    return 0


if __name__ == "__main__":
    sys.exit(main())
