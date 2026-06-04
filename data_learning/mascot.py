"""Mascot — a deterministic, always-identical cute humanoid host.

Drawn purely from code (PIL), so it looks exactly the same every render —
no image model, no drift. It's a small, lovable humanoid: round head with a
simple face, a little teal body, two arms (one raised and *pointing* at the
chart), stubby legs, and a gold-tasseled graduation cap. It does a gentle
idle (bob + blink + a small "presenting" arm wiggle) so it feels active
rather than just parked on screen.

The renderer places it inside the data and the raised arm + an in-chart
arrow tell viewers where to look.

:func:`build_mascot_loop` renders a short seamless idle loop to a .mov with
an alpha channel (qtrle) the studio renderer overlays and ``-stream_loop``s.
``point_angle`` aims the raised arm (degrees: 0=right, 90=up, 135=up-left).
"""
from __future__ import annotations

import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

# Palette (matches the chart house style).
BODY = (79, 209, 197, 255)        # #4FD1C5 teal
BODY_DK = (45, 160, 150, 255)     # shading
LIMB = (60, 185, 175, 255)        # arms / legs
SKIN = BODY
WHITE = (248, 250, 252, 255)
DARK = (11, 16, 32, 255)          # #0B1020 pupils + hat
BLUSH = (249, 168, 212, 220)
GOLD = (245, 158, 11, 255)
SS = 3                            # supersample for smooth edges


def _circle(d, cx, cy, r, fill):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)


def _thick_line(d, p0, p1, w, fill):
    d.line([p0, p1], fill=fill, width=w)
    _circle(d, p0[0], p0[1], w // 2, fill)
    _circle(d, p1[0], p1[1], w // 2, fill)


def _draw(size: int, bob: float, blink: float, point_angle: float,
          wiggle: float) -> Image.Image:
    """One humanoid frame.

    bob: vertical px; blink: 0..1; point_angle: deg (0=right,90=up);
    wiggle: -1..1 small arm sway.
    """
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = S // 2
    oy = int(bob * SS)

    # Vertical anatomy (fractions of S).
    head_cy = int(S * 0.30) + oy
    head_r = int(S * 0.168)             # bigger head = cuter/friendlier
    shoulder_y = int(S * 0.50) + oy
    torso_top = int(S * 0.46) + oy
    torso_bot = int(S * 0.74) + oy
    torso_w = int(S * 0.30)
    hip_y = torso_bot
    foot_y = int(S * 0.90) + oy
    limb_w = max(2, int(S * 0.055))

    # Legs.
    for sgn in (-1, 1):
        lx = cx + sgn * int(torso_w * 0.30)
        _thick_line(d, (lx, hip_y - int(S * 0.02)), (lx, foot_y), limb_w, LIMB)
        # foot
        d.ellipse([lx - int(limb_w * 0.9), foot_y - int(limb_w * 0.5),
                   lx + int(limb_w * 1.1), foot_y + int(limb_w * 0.6)],
                  fill=BODY_DK)

    # Torso (rounded).
    d.rounded_rectangle(
        [cx - torso_w // 2, torso_top, cx + torso_w // 2, torso_bot],
        radius=int(torso_w * 0.45), fill=BODY)
    # subtle belly shading
    d.ellipse([cx - int(torso_w * 0.30), torso_bot - int(torso_w * 0.55),
               cx + int(torso_w * 0.30), torso_bot - int(torso_w * 0.02)],
              fill=BODY_DK)

    # Resting arm (left, viewer-left): hangs with a slight bend.
    rest_sx = cx - torso_w // 2
    _thick_line(d, (rest_sx, shoulder_y),
                (rest_sx - int(S * 0.02), shoulder_y + int(S * 0.16)),
                limb_w, LIMB)
    _circle(d, rest_sx - int(S * 0.02), shoulder_y + int(S * 0.16),
            int(limb_w * 0.75), SKIN)

    # Pointing arm (right): a clean, nearly-straight raised arm toward the
    # chart, ending in a hand with an extended pointing finger.
    point_sx = cx + torso_w // 2
    ang = math.radians(point_angle + wiggle * 5)
    arm_len = int(S * 0.30)
    # slight elbow bend (8 deg) keeps it characterful but still clearly points
    ex = int(point_sx + math.cos(ang - math.radians(8)) * arm_len * 0.52)
    ey = int(shoulder_y - math.sin(ang - math.radians(8)) * arm_len * 0.52)
    hx = int(point_sx + math.cos(ang) * arm_len)
    hy = int(shoulder_y - math.sin(ang) * arm_len)
    _thick_line(d, (point_sx, shoulder_y), (ex, ey), limb_w, LIMB)
    _thick_line(d, (ex, ey), (hx, hy), limb_w, LIMB)
    # hand + a longer pointing finger in the aim direction
    _circle(d, hx, hy, int(limb_w * 0.85), SKIN)
    fx = int(hx + math.cos(ang) * limb_w * 2.2)
    fy = int(hy - math.sin(ang) * limb_w * 2.2)
    _thick_line(d, (hx, hy), (fx, fy), max(2, int(limb_w * 0.65)), SKIN)

    # Head.
    _circle(d, cx, head_cy, head_r, SKIN)
    d.ellipse([cx - int(head_r * 0.7), head_cy + int(head_r * 0.1),
               cx + int(head_r * 0.7), head_cy + int(head_r * 0.95)],
              fill=BODY_DK)
    _circle(d, cx, head_cy - int(head_r * 0.05), int(head_r * 0.96), SKIN)

    # Eyes — big and shiny for a friendly look.
    eye_dx = int(head_r * 0.42)
    eye_y = head_cy - int(head_r * 0.06)
    eye_r = int(head_r * 0.32)
    pup_r = int(head_r * 0.16)
    for sgn in (-1, 1):
        ex2 = cx + sgn * eye_dx
        if blink > 0.6:
            d.arc([ex2 - eye_r, eye_y - eye_r, ex2 + eye_r, eye_y + eye_r],
                  start=200, end=340, fill=DARK, width=max(3, S // 110))
        else:
            _circle(d, ex2, eye_y, eye_r, WHITE)
            _circle(d, ex2, eye_y + int(eye_r * 0.18), pup_r, DARK)
            # two catchlights = sparkly, friendly eyes
            _circle(d, ex2 - pup_r // 2, eye_y - pup_r // 3,
                    max(2, int(pup_r * 0.42)), WHITE)
            _circle(d, ex2 + pup_r // 2, eye_y + pup_r // 3,
                    max(2, int(pup_r * 0.22)), WHITE)

    # Big rosy blush.
    for sgn in (-1, 1):
        bx = cx + sgn * int(head_r * 0.66)
        d.ellipse([bx - int(head_r * 0.20), eye_y + int(head_r * 0.26),
                   bx + int(head_r * 0.20), eye_y + int(head_r * 0.54)],
                  fill=BLUSH)

    # Open, happy smile (filled) with a little tongue.
    mw = int(head_r * 0.46)
    my = head_cy + int(head_r * 0.40)
    d.pieslice([cx - mw, my - mw, cx + mw, my + mw], start=18, end=162,
               fill=DARK)
    tw = int(mw * 0.42)
    d.chord([cx - tw, my + int(mw * 0.10), cx + tw, my + int(mw * 0.74)],
            start=0, end=180, fill=(255, 120, 140, 255))

    # Graduation cap.
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


def build_mascot_loop(out_path: Path, *, size: int = 360, fps: int = 30,
                      seconds: float = 3.0, point_angle: float = 70.0) -> Path:
    """Render a seamless idle loop (.mov, alpha) — bob + blink + arm wiggle."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = int(fps * seconds)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for i in range(n):
            t = i / n
            bob = math.sin(t * 2 * math.pi) * (size * 0.026)   # livelier bob
            wiggle = math.sin(t * 2 * math.pi * 2)             # 2x lively arm
            blink = 1.0 if 0.70 <= t <= 0.74 else 0.0
            _draw(size, bob, blink, point_angle, wiggle).save(td / f"m{i:04d}.png")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
             "-i", str(td / "m%04d.png"),
             "-c:v", "qtrle", "-pix_fmt", "argb", str(out_path)],
            check=True)
    return out_path


def save_static(out_path: Path, size: int = 360, point_angle: float = 70.0) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _draw(size, 0.0, 0.0, point_angle, 0.0).save(out_path)
    return out_path


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/mascot.png")
    ang = float(sys.argv[2]) if len(sys.argv) > 2 else 70.0
    save_static(out, point_angle=ang)
    print("wrote", out)
