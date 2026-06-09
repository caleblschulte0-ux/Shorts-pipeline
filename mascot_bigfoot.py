"""Bigfoot mascot — minimal iconic cartoon anchor for baller_bro_2.0.

Style is deliberately Bluey/Pocoyo/Pingu-minimal: ONE solid silhouette,
two oversized eyes, one small mouth, a tiny red tie tab. No separate
brow ridge / muzzle / nose / cheeks — stacking detail on top of
procedural shapes only makes it look like assembled clipart. The
character lives in the silhouette + eyes.

Drawn purely from code (PIL), deterministic — looks identical every
render. Animation: subtle vertical bob + periodic blink. No flailing
limbs to look stiff.

:func:`build_bigfoot_loop` renders a seamless idle loop to a .mov with
alpha (qtrle) the explainer overlays via ``-stream_loop``.
"""
from __future__ import annotations

import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

# Palette — three brown tones for body depth, one red for the tie tab,
# white + black for eyes. That's it. Fewer colors = stronger silhouette.
FUR = (148, 102, 64, 255)         # main body
FUR_DK = (96, 62, 38, 255)        # silhouette + soft shadow
FUR_LT = (188, 142, 100, 255)     # tiny highlight on top of head
TIE = (188, 38, 32, 255)          # red tie tab
TIE_DK = (138, 22, 18, 255)
WHITE = (252, 252, 252, 255)
DARK = (16, 14, 12, 255)
SS = 3                             # supersample for smooth edges


def _circle(d, cx, cy, r, fill):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)


def _draw(size: int, bob: float, blink: float) -> Image.Image:
    """One Bigfoot frame. Single silhouette + huge eyes + minimal mouth.

    bob: vertical px (whole character translates).
    blink: 0..1, >0.6 = closed.
    """
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = S // 2
    oy = int(bob * SS)

    # ---------- Soft drop shadow under the silhouette ----------
    # A blurred dark blob slightly offset down — gives the character
    # weight on screen instead of floating like a sticker.
    shadow_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    s_cx = cx + int(S * 0.01)
    s_cy = int(S * 0.55) + oy + int(S * 0.025)
    sw = int(S * 0.40)
    sh = int(S * 0.46)
    sd.ellipse([s_cx - sw, s_cy - sh, s_cx + sw, s_cy + sh],
               fill=(0, 0, 0, 110))
    shadow_layer = shadow_layer.filter(
        ImageFilter.GaussianBlur(radius=int(S * 0.020)))
    img.alpha_composite(shadow_layer)

    # ---------- Tiny red tie tab peeking out the bottom ----------
    # Drawn BEFORE the body so the silhouette overlaps it — only the
    # bottom of the tie is visible, which is the iconic "anchor" hint
    # without needing a separate suit shape.
    tie_top_y = int(S * 0.78) + oy
    tie_bot_y = int(S * 0.95) + oy
    tie_top_w = int(S * 0.04)
    tie_bot_w = int(S * 0.075)
    d.polygon([
        (cx - tie_top_w, tie_top_y),
        (cx + tie_top_w, tie_top_y),
        (cx + tie_bot_w, tie_bot_y),
        (cx - tie_bot_w, tie_bot_y),
    ], fill=TIE)
    # tie shadow stripe (depth)
    d.line([(cx + int(tie_top_w * 0.2), tie_top_y + int(S * 0.005)),
            (cx + int(tie_bot_w * 0.3), tie_bot_y - int(S * 0.005))],
           fill=TIE_DK, width=max(2, S // 280))

    # ---------- The silhouette — ONE big merged head+body blob ----------
    # An ellipse for the body + an ellipse for the head, both in the
    # same color, blended into one shape. The whole point is that the
    # character reads as a single creature, not assembled pieces.

    # Body ellipse (wider, lower)
    body_cy = int(S * 0.66) + oy
    body_w = int(S * 0.38)
    body_h = int(S * 0.32)
    d.ellipse([cx - body_w, body_cy - body_h,
               cx + body_w, body_cy + body_h], fill=FUR)

    # Head ellipse (slightly narrower, sits on top, overlaps body so
    # the two merge into one rounded silhouette)
    head_cy = int(S * 0.40) + oy
    head_w = int(S * 0.34)
    head_h = int(S * 0.32)
    d.ellipse([cx - head_w, head_cy - head_h,
               cx + head_w, head_cy + head_h], fill=FUR)

    # Three small fur peaks on the top of the head (Bigfoot mane hint).
    # Same FUR color so they merge into the silhouette, with the dark
    # peak tips that just barely poke above.
    for i, offset in enumerate((-0.50, 0.0, 0.50)):
        bx = cx + int(head_w * offset)
        by = head_cy - head_h + int(S * 0.01)
        tip_x = bx + int(S * 0.005 * (-1 if i % 2 else 1))
        tip_y = head_cy - head_h - int(S * 0.06)
        tw = int(S * 0.045)
        d.polygon([
            (bx - tw // 2, by),
            (bx + tw // 2, by),
            (tip_x, tip_y),
        ], fill=FUR_DK)

    # Subtle lighter top-of-head highlight (gives volume)
    hl_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hl_layer)
    hd.ellipse([cx - int(head_w * 0.65), head_cy - int(head_h * 0.85),
                cx + int(head_w * 0.65), head_cy - int(head_h * 0.05)],
               fill=(FUR_LT[0], FUR_LT[1], FUR_LT[2], 90))
    hl_layer = hl_layer.filter(ImageFilter.GaussianBlur(radius=int(S * 0.012)))
    img.alpha_composite(hl_layer)

    # ---------- Eyes — oversized, the focal point of the whole design ----------
    # Big white circles, big black pupils, small white catchlight.
    # The catchlight is what makes them feel "alive" vs. dead dots.
    eye_dx = int(S * 0.08)
    eye_y = head_cy + int(S * 0.01)
    eye_r = int(S * 0.062)              # OVERSIZED — these are the character
    pup_r = int(eye_r * 0.55)

    if blink > 0.6:
        # Closed-eye arcs ^_^
        for sgn in (-1, 1):
            ex = cx + sgn * eye_dx
            d.arc([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r],
                  start=200, end=340, fill=DARK, width=max(5, S // 90))
    else:
        for sgn in (-1, 1):
            ex = cx + sgn * eye_dx
            _circle(d, ex, eye_y, eye_r, WHITE)
            # pupil sits slightly low for friendly downward gaze
            _circle(d, ex, eye_y + int(eye_r * 0.12), pup_r, DARK)
            # catchlight (small white highlight in upper-left of pupil)
            _circle(d, ex - int(pup_r * 0.40), eye_y - int(pup_r * 0.20),
                    max(2, int(pup_r * 0.42)), WHITE)

    # ---------- Mouth — ONE tiny dark curve ----------
    # No tongue, no fang, no lips. Just a curved line.
    mw = int(S * 0.035)
    my = head_cy + int(S * 0.12)
    d.arc([cx - mw, my - int(mw * 0.4),
           cx + mw, my + int(mw * 0.7)],
          start=20, end=160, fill=DARK, width=max(4, S // 110))

    # Downsample with high-quality filter for clean antialiased edges.
    return img.resize((size, size), Image.LANCZOS)


def build_bigfoot_loop(out_path: Path, *, size: int = 540, fps: int = 30,
                       seconds: float = 3.0, flip: bool = False) -> Path:
    """Render a seamless idle loop (.mov, alpha) — bob + blink."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = int(fps * seconds)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for i in range(n):
            t = i / n
            bob = math.sin(t * 2 * math.pi) * (size * 0.022)
            blink = 1.0 if 0.78 <= t <= 0.82 else 0.0
            im = _draw(size, bob, blink)
            if flip:
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
            im.save(td / f"m{i:04d}.png")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
             "-i", str(td / "m%04d.png"),
             "-c:v", "qtrle", "-pix_fmt", "argb", str(out_path)],
            check=True)
    return out_path


def save_static(out_path: Path, size: int = 540) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _draw(size, 0.0, 0.0).save(out_path)
    return out_path


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/bigfoot.png")
    save_static(out)
    print("wrote", out)
