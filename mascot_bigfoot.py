"""Bigfoot mascot — minimal port of the Short_explainer mascot.

Same character DESIGN as data_learning/mascot.py (the teal humanoid host
the data channel uses). Only swaps:
  * teal body/limbs → warm brown fur
  * graduation cap → kept as the anchor's "cred" prop (or remove if
    you'd rather; flip CAP=True/False at top)
  * glasses → kept (reads serious + smart for a news anchor)
  * NEW: red anchor tie down the chest

Everything else (head/eyes/blush/smile/horns/animation) is structurally
identical to the working data mascot, just retoned. Deterministic, no
image-model drift, animates with bob + blink + arm wiggle.
"""
from __future__ import annotations

import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

# Palette — muted/desaturated. Saturday-morning brown shifted toward
# grounded teen-show brown (less candy, more cocoa).
BODY = (108, 78, 58, 255)         # darker, more muted brown
BODY_DK = (72, 50, 34, 255)
LIMB = (90, 64, 46, 255)
SKIN = BODY
WHITE = (236, 236, 230, 255)      # slightly off-white (not eye-catching glossy)
DARK = (12, 10, 8, 255)
GOLD = (212, 158, 60, 255)        # muted gold for glasses
HORN = (52, 36, 24, 255)          # dark fur tufts
TIE = (158, 32, 28, 255)          # darker red — less candy
TIE_DK = (112, 20, 16, 255)
TIE_LT = (192, 48, 42, 255)
SS = 3                            # supersample for smooth edges

CAP = False                       # flip True to draw the graduation cap


def _circle(d, cx, cy, r, fill):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)


def _thick_line(d, p0, p1, w, fill):
    d.line([p0, p1], fill=fill, width=w)
    _circle(d, p0[0], p0[1], w // 2, fill)
    _circle(d, p1[0], p1[1], w // 2, fill)


def _draw(size: int, bob: float, blink: float, point_angle: float,
          wiggle: float) -> Image.Image:
    """One humanoid Bigfoot frame.

    bob: vertical px; blink: 0..1; point_angle: deg (0=right,90=up);
    wiggle: -1..1 small arm sway.
    """
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = S // 2
    oy = int(bob * SS)

    # Vertical anatomy (fractions of S) — identical to data_learning.
    head_cy = int(S * 0.30) + oy
    head_r = int(S * 0.168)
    shoulder_y = int(S * 0.50) + oy
    torso_top = int(S * 0.46) + oy
    torso_bot = int(S * 0.74) + oy
    torso_w = int(S * 0.30)
    hip_y = torso_bot
    foot_y = int(S * 0.90) + oy
    limb_w = max(2, int(S * 0.055))

    # ---------- Legs ----------
    for sgn in (-1, 1):
        lx = cx + sgn * int(torso_w * 0.30)
        _thick_line(d, (lx, hip_y - int(S * 0.02)), (lx, foot_y), limb_w, LIMB)
        d.ellipse([lx - int(limb_w * 0.9), foot_y - int(limb_w * 0.5),
                   lx + int(limb_w * 1.1), foot_y + int(limb_w * 0.6)],
                  fill=BODY_DK)

    # ---------- Torso ----------
    d.rounded_rectangle(
        [cx - torso_w // 2, torso_top, cx + torso_w // 2, torso_bot],
        radius=int(torso_w * 0.45), fill=BODY)
    # subtle belly shading
    d.ellipse([cx - int(torso_w * 0.30), torso_bot - int(torso_w * 0.55),
               cx + int(torso_w * 0.30), torso_bot - int(torso_w * 0.02)],
              fill=BODY_DK)

    # ---------- NEW: red tie strip down the chest ----------
    tie_top_y = torso_top + int(torso_w * 0.05)
    tie_bot_y = torso_bot - int(torso_w * 0.04)
    tie_top_w = int(torso_w * 0.10)
    tie_bot_w = int(torso_w * 0.18)
    # knot
    d.polygon([
        (cx - tie_top_w, tie_top_y),
        (cx + tie_top_w, tie_top_y),
        (cx + int(tie_top_w * 0.7), tie_top_y + int(torso_w * 0.12)),
        (cx - int(tie_top_w * 0.7), tie_top_y + int(torso_w * 0.12)),
    ], fill=TIE)
    # body
    d.polygon([
        (cx - int(tie_top_w * 0.7), tie_top_y + int(torso_w * 0.12)),
        (cx + int(tie_top_w * 0.7), tie_top_y + int(torso_w * 0.12)),
        (cx + tie_bot_w, tie_bot_y),
        (cx - tie_bot_w, tie_bot_y),
    ], fill=TIE)
    # highlight stripe
    d.line([(cx - int(tie_top_w * 0.3), tie_top_y + int(torso_w * 0.16)),
            (cx - int(tie_bot_w * 0.45), tie_bot_y - int(torso_w * 0.02))],
           fill=TIE_LT, width=max(2, S // 360))

    # ---------- Resting arm (left, viewer-left): hangs with slight bend ----------
    rest_sx = cx - torso_w // 2
    _thick_line(d, (rest_sx, shoulder_y),
                (rest_sx - int(S * 0.02), shoulder_y + int(S * 0.16)),
                limb_w, LIMB)
    _circle(d, rest_sx - int(S * 0.02), shoulder_y + int(S * 0.16),
            int(limb_w * 0.75), SKIN)

    # ---------- Pointing arm (right) ----------
    point_sx = cx + torso_w // 2
    ang = math.radians(point_angle + wiggle * 5)
    arm_len = int(S * 0.30)
    ex = int(point_sx + math.cos(ang - math.radians(8)) * arm_len * 0.52)
    ey = int(shoulder_y - math.sin(ang - math.radians(8)) * arm_len * 0.52)
    hx = int(point_sx + math.cos(ang) * arm_len)
    hy = int(shoulder_y - math.sin(ang) * arm_len)
    _thick_line(d, (point_sx, shoulder_y), (ex, ey), limb_w, LIMB)
    _thick_line(d, (ex, ey), (hx, hy), limb_w, LIMB)
    _circle(d, hx, hy, int(limb_w * 0.85), SKIN)
    fx = int(hx + math.cos(ang) * limb_w * 2.2)
    fy = int(hy - math.sin(ang) * limb_w * 2.2)
    _thick_line(d, (hx, hy), (fx, fy), max(2, int(limb_w * 0.65)), SKIN)

    # ---------- Fur tufts (was horns) — behind the head ----------
    for sgn in (-1, 1):
        bx = cx + sgn * int(head_r * 0.52)
        by = head_cy - int(head_r * 0.58)
        tx = cx + sgn * int(head_r * 1.08)
        ty = head_cy - int(head_r * 1.78)
        hw = int(head_r * 0.40)
        d.polygon([(bx - hw // 2, by), (bx + hw // 2, by), (tx, ty)], fill=HORN)
    # Center tuft so the mane reads as "fur" not "two horns"
    d.polygon([
        (cx - int(head_r * 0.22), head_cy - int(head_r * 0.70)),
        (cx + int(head_r * 0.22), head_cy - int(head_r * 0.70)),
        (cx, head_cy - int(head_r * 1.60)),
    ], fill=HORN)

    # ---------- Head ----------
    _circle(d, cx, head_cy, head_r, SKIN)
    d.ellipse([cx - int(head_r * 0.7), head_cy + int(head_r * 0.1),
               cx + int(head_r * 0.7), head_cy + int(head_r * 0.95)],
              fill=BODY_DK)
    _circle(d, cx, head_cy - int(head_r * 0.05), int(head_r * 0.96), SKIN)

    # ---------- Eyes — smaller + focused, no cute catchlight sparkle ----------
    eye_dx = int(head_r * 0.42)
    eye_y = head_cy - int(head_r * 0.04)
    eye_r = int(head_r * 0.21)            # smaller (was 0.27)
    pup_r = int(head_r * 0.13)
    for sgn in (-1, 1):
        ex2 = cx + sgn * eye_dx
        if blink > 0.6:
            d.arc([ex2 - eye_r, eye_y - eye_r, ex2 + eye_r, eye_y + eye_r],
                  start=200, end=340, fill=DARK, width=max(3, S // 110))
        else:
            _circle(d, ex2, eye_y, eye_r, WHITE)
            # Pupils sit centered (not downward-cute) and fill more of
            # the eye so he reads as focused, not doe-eyed.
            _circle(d, ex2, eye_y, pup_r, DARK)
            # NO catchlight — sparkle pupils are the #1 kids-show tell.

    # ---------- Heavy angled brows — the serious anchor look ----------
    bw = int(eye_r * 1.40)
    for sgn in (-1, 1):
        ex2 = cx + sgn * eye_dx
        by0 = eye_y - int(eye_r * 1.55)
        # Inner edge lower than outer = serious / focused
        inner_y = by0 + int(eye_r * 0.55)
        outer_y = by0
        if sgn < 0:
            p_inner = (ex2 + bw // 2, inner_y)
            p_outer = (ex2 - bw // 2, outer_y)
        else:
            p_inner = (ex2 - bw // 2, inner_y)
            p_outer = (ex2 + bw // 2, outer_y)
        d.line([p_outer, p_inner], fill=DARK, width=max(5, S // 80))

    # ---------- Professor glasses (keep — reads "news anchor smart") ----------
    if blink <= 0.6:
        gl_r = int(eye_r * 1.34)
        gw = max(3, S // 120)
        for sgn in (-1, 1):
            ex2 = cx + sgn * eye_dx
            d.ellipse([ex2 - gl_r, eye_y - gl_r, ex2 + gl_r, eye_y + gl_r],
                      outline=GOLD, width=gw)
            d.line([(ex2 + sgn * gl_r, eye_y),
                    (ex2 + sgn * int(head_r * 0.95), eye_y - int(head_r * 0.06))],
                   fill=GOLD, width=gw)
        d.line([(cx - eye_dx + gl_r, eye_y), (cx + eye_dx - gl_r, eye_y)],
               fill=GOLD, width=gw)

    # No blush (kids-show tell) and no fangs (cute-monster tell).

    # ---------- Mouth — neutral flat line with the faintest smile curl ----------
    mw = int(head_r * 0.30)
    my = head_cy + int(head_r * 0.48)
    d.line([(cx - mw, my), (cx + mw, my)], fill=DARK, width=max(4, S // 100))
    # Tiny upward tick at each corner — barely-there smile, more "amused
    # but composed" than "grinning".
    d.line([(cx - mw, my), (cx - int(mw * 0.80), my - int(mw * 0.10))],
           fill=DARK, width=max(4, S // 100))
    d.line([(cx + mw, my), (cx + int(mw * 0.80), my - int(mw * 0.10))],
           fill=DARK, width=max(4, S // 100))

    # ---------- Optional graduation cap ----------
    if CAP:
        cap_y = head_cy - head_r
        board_w = int(head_r * 2.3)
        bh = int(head_r * 0.26)
        _circle(d, cx, cap_y + int(head_r * 0.18), int(head_r * 0.66), DARK)
        by = cap_y - int(bh * 0.1)
        d.polygon([(cx, by - bh), (cx + board_w // 2, by),
                   (cx, by + bh), (cx - board_w // 2, by)], fill=DARK)
        _circle(d, cx, by, max(2, SS * 2), GOLD)
        tx = cx + board_w // 2
        d.line([(cx, by), (tx, by), (tx, by + int(head_r * 0.5))], fill=GOLD,
               width=max(2, S // 160))
        _circle(d, tx, by + int(head_r * 0.5), max(2, SS * 3), GOLD)

    return img.resize((size, size), Image.LANCZOS)


def build_bigfoot_loop(out_path: Path, *, size: int = 540, fps: int = 30,
                       seconds: float = 3.0, point_angle: float = 70.0,
                       flip: bool = False) -> Path:
    """Render a seamless idle loop (.mov, alpha) — bob + blink + arm wiggle.
    ``flip`` mirrors horizontally so the pointing arm aims the other way."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = int(fps * seconds)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for i in range(n):
            t = i / n
            bob = math.sin(t * 2 * math.pi) * (size * 0.026)
            wiggle = math.sin(t * 2 * math.pi * 2)
            blink = 1.0 if 0.70 <= t <= 0.74 else 0.0
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


def save_static(out_path: Path, size: int = 540,
                point_angle: float = 70.0) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _draw(size, 0.0, 0.0, point_angle, 0.0).save(out_path)
    return out_path


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/bigfoot.png")
    ang = float(sys.argv[2]) if len(sys.argv) > 2 else 70.0
    save_static(out, point_angle=ang)
    print("wrote", out)
