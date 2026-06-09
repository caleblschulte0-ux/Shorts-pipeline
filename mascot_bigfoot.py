"""Bigfoot mascot — procedural cartoon news anchor for baller_bro_2.0.

Same draw-by-code approach as data_learning/mascot.py — deterministic,
identical every render, no image model, no asset drift. The character
is a cute Saturday-morning-cartoon Bigfoot in a navy suit + red tie,
with chibi proportions (big head, small body) and an animated idle
loop (bob + blink + arm wiggle) so he feels alive in the corner of
every shot.

:func:`build_bigfoot_loop` renders a short seamless idle loop to a .mov
with an alpha channel (qtrle) the explainer renderer overlays via
``-stream_loop``. ``point_angle`` aims the raised arm (degrees: 0=right,
90=up, 135=up-left). ``flip`` mirrors so he can stand on either side
of the frame.
"""
from __future__ import annotations

import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

# Palette — warm browns for fur, navy/red for the news-anchor outfit.
# Solid fills only (no gradients) so the silhouette stays crisp when
# scaled down and overlaid on busy B-roll.
FUR = (132, 92, 60, 255)
FUR_DK = (88, 58, 36, 255)
FUR_LT = (162, 118, 82, 255)
SUIT = (28, 48, 92, 255)
SUIT_DK = (18, 32, 64, 255)
SHIRT = (248, 245, 236, 255)
TIE = (182, 38, 32, 255)
TIE_LT = (220, 64, 54, 255)
WHITE = (248, 250, 252, 255)
DARK = (18, 14, 10, 255)
BLUSH = (220, 150, 110, 200)
NOSE = (52, 32, 22, 255)
TONGUE = (255, 120, 140, 255)
SS = 3                            # supersample for smooth edges


def _circle(d, cx, cy, r, fill):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)


def _thick_line(d, p0, p1, w, fill):
    d.line([p0, p1], fill=fill, width=w)
    _circle(d, p0[0], p0[1], w // 2, fill)
    _circle(d, p1[0], p1[1], w // 2, fill)


def _draw(size: int, bob: float, blink: float, point_angle: float,
          wiggle: float) -> Image.Image:
    """One Bigfoot frame.

    bob: vertical px; blink: 0..1; point_angle: deg (0=right, 90=up);
    wiggle: -1..1 small arm sway.
    """
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = S // 2
    oy = int(bob * SS)

    # Vertical anatomy (fractions of S).
    head_cy = int(S * 0.30) + oy
    head_r = int(S * 0.185)
    shoulder_y = int(S * 0.52) + oy
    torso_top = int(S * 0.48) + oy
    torso_bot = int(S * 0.80) + oy
    torso_w = int(S * 0.40)
    hip_y = torso_bot
    foot_y = int(S * 0.94) + oy
    limb_w = max(2, int(S * 0.062))

    # ---------- Legs (suit pants + dark shoes) ----------
    for sgn in (-1, 1):
        lx = cx + sgn * int(torso_w * 0.26)
        _thick_line(d, (lx, hip_y - int(S * 0.02)), (lx, foot_y), limb_w, SUIT)
        d.ellipse([lx - int(limb_w * 1.0), foot_y - int(limb_w * 0.45),
                   lx + int(limb_w * 1.2), foot_y + int(limb_w * 0.65)],
                  fill=DARK)

    # ---------- Torso: navy suit jacket ----------
    d.rounded_rectangle(
        [cx - torso_w // 2, torso_top, cx + torso_w // 2, torso_bot],
        radius=int(torso_w * 0.38), fill=SUIT)
    # Subtle center-button shadow stripe
    d.line([(cx, torso_top + int(torso_w * 0.32)),
            (cx, torso_bot - int(torso_w * 0.08))],
           fill=SUIT_DK, width=max(2, S // 260))

    # ---------- White shirt V-collar ----------
    d.polygon([
        (cx - int(torso_w * 0.30), torso_top + int(torso_w * 0.04)),
        (cx + int(torso_w * 0.30), torso_top + int(torso_w * 0.04)),
        (cx, torso_top + int(torso_w * 0.36)),
    ], fill=SHIRT)

    # ---------- Red tie (knot + body + highlight) ----------
    knot_top = torso_top + int(torso_w * 0.08)
    knot_w = int(torso_w * 0.16)
    d.polygon([
        (cx - knot_w, knot_top),
        (cx + knot_w, knot_top),
        (cx, knot_top + int(torso_w * 0.20)),
    ], fill=TIE)
    tie_top_y = knot_top + int(torso_w * 0.20)
    tie_bot_y = torso_bot - int(torso_w * 0.08)
    tie_top_w = int(torso_w * 0.07)
    tie_bot_w = int(torso_w * 0.13)
    d.polygon([
        (cx - tie_top_w, tie_top_y),
        (cx + tie_top_w, tie_top_y),
        (cx + tie_bot_w, tie_bot_y),
        (cx - tie_bot_w, tie_bot_y),
    ], fill=TIE)
    d.line([(cx, tie_top_y + int(torso_w * 0.02)),
            (cx - int(tie_bot_w * 0.3), tie_bot_y - int(torso_w * 0.03))],
           fill=TIE_LT, width=max(2, S // 340))

    # ---------- Resting arm (viewer-left) ----------
    rest_sx = cx - torso_w // 2 + int(limb_w * 0.3)
    _thick_line(d, (rest_sx, shoulder_y),
                (rest_sx - int(S * 0.04), shoulder_y + int(S * 0.17)),
                limb_w, FUR)
    _circle(d, rest_sx - int(S * 0.04), shoulder_y + int(S * 0.17),
            int(limb_w * 0.85), FUR)

    # ---------- Pointing arm (viewer-right, animated) ----------
    point_sx = cx + torso_w // 2 - int(limb_w * 0.3)
    ang = math.radians(point_angle + wiggle * 6)
    arm_len = int(S * 0.33)
    ex = int(point_sx + math.cos(ang - math.radians(10)) * arm_len * 0.52)
    ey = int(shoulder_y - math.sin(ang - math.radians(10)) * arm_len * 0.52)
    hx = int(point_sx + math.cos(ang) * arm_len)
    hy = int(shoulder_y - math.sin(ang) * arm_len)
    _thick_line(d, (point_sx, shoulder_y), (ex, ey), limb_w, FUR)
    _thick_line(d, (ex, ey), (hx, hy), limb_w, FUR)
    _circle(d, hx, hy, int(limb_w * 0.95), FUR)
    # Pointing finger jutting in the aim direction
    fx = int(hx + math.cos(ang) * limb_w * 2.2)
    fy = int(hy - math.sin(ang) * limb_w * 2.2)
    _thick_line(d, (hx, hy), (fx, fy), max(2, int(limb_w * 0.65)), FUR)

    # ---------- Head ----------
    # Fur tufts sticking up from the top of the head (3 little peaks,
    # behind the head dome so they read as silhouette).
    for sgn in (-1, 0, 1):
        bx = cx + sgn * int(head_r * 0.55)
        by = head_cy - int(head_r * 0.85)
        tx = cx + sgn * int(head_r * 0.62)
        ty = head_cy - int(head_r * 1.35)
        tw_ = int(head_r * 0.30)
        d.polygon([
            (bx - tw_ // 2, by),
            (bx + tw_ // 2, by),
            (tx, ty),
        ], fill=FUR_DK)

    # Main head dome
    _circle(d, cx, head_cy, head_r, FUR)

    # Lighter "muzzle" patch around mouth + nose for depth
    d.ellipse([cx - int(head_r * 0.68), head_cy - int(head_r * 0.05),
               cx + int(head_r * 0.68), head_cy + int(head_r * 0.82)],
              fill=FUR_LT)

    # Side ears
    for sgn in (-1, 1):
        bx = cx + sgn * int(head_r * 0.96)
        by = head_cy - int(head_r * 0.10)
        _circle(d, bx, by, int(head_r * 0.18), FUR_DK)
        _circle(d, bx, by, int(head_r * 0.10), NOSE)

    # ---------- Brow ridge ----------
    brow_y = head_cy - int(head_r * 0.30)
    brow_w = int(head_r * 1.34)
    brow_h = int(head_r * 0.20)
    d.rounded_rectangle(
        [cx - brow_w // 2, brow_y - brow_h // 2,
         cx + brow_w // 2, brow_y + brow_h // 2],
        radius=int(brow_h * 0.5), fill=FUR_DK)

    # ---------- Eyes ----------
    eye_dx = int(head_r * 0.42)
    eye_y = head_cy + int(head_r * 0.02)
    eye_r = int(head_r * 0.28)
    pup_r = int(head_r * 0.15)
    for sgn in (-1, 1):
        ex2 = cx + sgn * eye_dx
        if blink > 0.6:
            d.arc([ex2 - eye_r, eye_y - eye_r, ex2 + eye_r, eye_y + eye_r],
                  start=200, end=340, fill=DARK, width=max(3, S // 110))
        else:
            _circle(d, ex2, eye_y, eye_r, WHITE)
            _circle(d, ex2, eye_y + int(eye_r * 0.16), pup_r, DARK)
            # Catchlight gives it life
            _circle(d, ex2 - pup_r // 2, eye_y - pup_r // 3,
                    max(2, int(pup_r * 0.38)), WHITE)

    # Small black eyebrows on top of the brow ridge (extra expression)
    bw = int(eye_r * 1.05)
    for sgn in (-1, 1):
        ex2 = cx + sgn * eye_dx
        by0 = eye_y - int(eye_r * 1.40)
        d.line([(ex2 - bw // 2, by0 + int(eye_r * 0.20)),
                (ex2 + bw // 2, by0)], fill=DARK, width=max(3, S // 120))

    # ---------- Nose — small dark triangle ----------
    d.polygon([
        (cx - int(head_r * 0.12), head_cy + int(head_r * 0.28)),
        (cx + int(head_r * 0.12), head_cy + int(head_r * 0.28)),
        (cx, head_cy + int(head_r * 0.50)),
    ], fill=NOSE)

    # ---------- Mouth — open smile w/ tongue + one tiny fang ----------
    mw = int(head_r * 0.44)
    my = head_cy + int(head_r * 0.66)
    d.pieslice([cx - mw, my - mw, cx + mw, my + mw], start=20, end=160,
               fill=DARK)
    tw_ = int(mw * 0.42)
    d.chord([cx - tw_, my + int(mw * 0.10), cx + tw_, my + int(mw * 0.74)],
            start=0, end=180, fill=TONGUE)
    # One small fang on the left so he reads as Bigfoot-not-bear
    d.polygon([
        (cx - int(mw * 0.55), my - int(mw * 0.03)),
        (cx - int(mw * 0.30), my - int(mw * 0.03)),
        (cx - int(mw * 0.42), my + int(mw * 0.32)),
    ], fill=WHITE)

    # ---------- Cheek blush ----------
    for sgn in (-1, 1):
        bx = cx + sgn * int(head_r * 0.62)
        d.ellipse([bx - int(head_r * 0.14), my - int(head_r * 0.20),
                   bx + int(head_r * 0.14), my - int(head_r * 0.04)],
                  fill=BLUSH)

    return img.resize((size, size), Image.LANCZOS)


def build_bigfoot_loop(out_path: Path, *, size: int = 480, fps: int = 30,
                       seconds: float = 3.0, point_angle: float = 75.0,
                       flip: bool = False) -> Path:
    """Render a seamless idle loop (.mov, alpha) — bob + blink + arm wiggle.
    ``flip`` mirrors horizontally so the pointing arm aims the other way
    (used when the mascot stands on the right side of the canvas)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = int(fps * seconds)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for i in range(n):
            t = i / n
            bob = math.sin(t * 2 * math.pi) * (size * 0.028)
            wiggle = math.sin(t * 2 * math.pi * 2)
            blink = 1.0 if 0.72 <= t <= 0.76 else 0.0
            im = _draw(size, bob, blink, point_angle, wiggle)
            if flip:
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
            im.save(td / f"m{i:04d}.png")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
             "-i", str(td / "m%04d.png"),
             "-c:v", "qtrle", "-pix_fmt", "argb", str(out_path)],
            check=True)
    return out_path


def save_static(out_path: Path, size: int = 480,
                point_angle: float = 75.0) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _draw(size, 0.0, 0.0, point_angle, 0.0).save(out_path)
    return out_path


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/bigfoot.png")
    ang = float(sys.argv[2]) if len(sys.argv) > 2 else 75.0
    save_static(out, point_angle=ang)
    print("wrote", out)
