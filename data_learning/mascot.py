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

from PIL import Image, ImageDraw, ImageFilter

# Palette (matches the chart house style).
BODY = (79, 209, 197, 255)        # #4FD1C5 teal
BODY_DK = (45, 160, 150, 255)     # shading
LIMB = (60, 185, 175, 255)        # arms / legs
SKIN = BODY
WHITE = (248, 250, 252, 255)
DARK = (11, 16, 32, 255)          # #0B1020 pupils + hat
OUTLINE = (13, 17, 24, 255)       # clean dark sticker outline around the char
BELLY = (198, 240, 232, 255)      # lighter teal belly patch (dimension)
BLUSH = (249, 168, 212, 220)
GOLD = (245, 158, 11, 255)        # glasses + tassel
HORN = (124, 92, 196, 255)        # little monster horns (violet)
FANG = (252, 252, 255, 255)
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
    limb_w = max(2, int(S * 0.082))     # thicker, rounder limbs = polished, not sticky

    # --- CHUNKY rounded body (a friendly egg-blob) — no stick limbs. ---
    body_top = head_cy + int(head_r * 0.60)
    body_bot = int(S * 0.87) + oy
    body_w = int(S * 0.50)
    arm_w = int(body_w * 0.30)                      # stubby rounded arms

    # Stubby feet first (behind the body).
    fw = int(body_w * 0.34)
    for sgn in (-1, 1):
        fxc = cx + sgn * int(body_w * 0.24)
        d.ellipse([fxc - fw // 2, body_bot - int(fw * 0.30),
                   fxc + fw // 2, body_bot + int(fw * 0.62)], fill=BODY_DK)

    # Resting arm (viewer-left): a short capsule tucked at the side.
    ax0 = cx - body_w // 2
    ay0 = body_top + int(body_w * 0.42)
    d.rounded_rectangle([ax0 - int(arm_w * 0.7), ay0,
                         ax0 + int(arm_w * 0.5), ay0 + int(arm_w * 2.0)],
                        radius=arm_w // 2, fill=BODY)

    # Body.
    d.rounded_rectangle([cx - body_w // 2, body_top, cx + body_w // 2, body_bot],
                        radius=int(body_w * 0.48), fill=BODY)
    # Lighter belly patch for dimension.
    d.ellipse([cx - int(body_w * 0.30), body_bot - int(body_w * 0.66),
               cx + int(body_w * 0.30), body_bot - int(body_w * 0.06)], fill=BELLY)

    # Pointing arm (viewer-right): a stubby capsule aimed by point_angle,
    # ending in a clean round hand (NO fingers — nothing to mangle).
    psx = cx + body_w // 2 - int(arm_w * 0.2)
    psy = body_top + int(body_w * 0.30)
    ang = math.radians(point_angle + wiggle * 5)
    arm_len = int(S * 0.26)
    hx = int(psx + math.cos(ang) * arm_len)
    hy = int(psy - math.sin(ang) * arm_len)
    _thick_line(d, (psx, psy), (hx, hy), arm_w, BODY)
    _circle(d, hx, hy, int(arm_w * 0.62), BODY)

    # Sharp little monster horns (behind the head).
    for sgn in (-1, 1):
        bx = cx + sgn * int(head_r * 0.52)
        by = head_cy - int(head_r * 0.58)
        tx = cx + sgn * int(head_r * 1.08)
        ty = head_cy - int(head_r * 1.78)        # taller + pointed (no tip)
        hw = int(head_r * 0.40)
        d.polygon([(bx - hw // 2, by), (bx + hw // 2, by), (tx, ty)], fill=HORN)

    # Head.
    _circle(d, cx, head_cy, head_r, SKIN)
    d.ellipse([cx - int(head_r * 0.7), head_cy + int(head_r * 0.1),
               cx + int(head_r * 0.7), head_cy + int(head_r * 0.95)],
              fill=BODY_DK)
    _circle(d, cx, head_cy - int(head_r * 0.05), int(head_r * 0.96), SKIN)

    # Eyes — big and shiny for a friendly look.
    eye_dx = int(head_r * 0.42)
    eye_y = head_cy - int(head_r * 0.04)
    eye_r = int(head_r * 0.27)               # smaller = less baby-cute
    pup_r = int(head_r * 0.15)
    for sgn in (-1, 1):
        ex2 = cx + sgn * eye_dx
        if blink > 0.6:
            d.arc([ex2 - eye_r, eye_y - eye_r, ex2 + eye_r, eye_y + eye_r],
                  start=200, end=340, fill=DARK, width=max(3, S // 110))
        else:
            _circle(d, ex2, eye_y, eye_r, WHITE)
            _circle(d, ex2, eye_y + int(eye_r * 0.16), pup_r, DARK)
            _circle(d, ex2 - pup_r // 2, eye_y - pup_r // 3,
                    max(2, int(pup_r * 0.34)), WHITE)   # single catchlight
    # Flat, slightly angled brows — drops the cuddly look a notch.
    bw = int(eye_r * 1.05)
    for sgn in (-1, 1):
        ex2 = cx + sgn * eye_dx
        by0 = eye_y - int(eye_r * 1.30)
        d.line([(ex2 - bw // 2, by0 + int(eye_r * 0.16)),
                (ex2 + bw // 2, by0)], fill=DARK, width=max(3, S // 120))

    # Professor glasses — round gold frames over the eyes.
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

    # Small, subtle blush.
    for sgn in (-1, 1):
        bx = cx + sgn * int(head_r * 0.70)
        d.ellipse([bx - int(head_r * 0.12), eye_y + int(head_r * 0.30),
                   bx + int(head_r * 0.12), eye_y + int(head_r * 0.48)],
                  fill=BLUSH)

    # Smaller, cooler smile (filled) with a little tongue.
    mw = int(head_r * 0.40)
    my = head_cy + int(head_r * 0.44)
    d.pieslice([cx - mw, my - mw, cx + mw, my + mw], start=18, end=162,
               fill=DARK)
    tw = int(mw * 0.42)
    d.chord([cx - tw, my + int(mw * 0.10), cx + tw, my + int(mw * 0.74)],
            start=0, end=180, fill=(255, 120, 140, 255))
    # Two little monster fangs at the top of the smile.
    for sgn in (-1, 1):
        fxx = cx + sgn * int(mw * 0.5)
        d.polygon([(fxx - int(mw * 0.13), my - int(mw * 0.04)),
                   (fxx + int(mw * 0.13), my - int(mw * 0.04)),
                   (fxx, my + int(mw * 0.40))], fill=FANG)

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

    img = img.resize((size, size), Image.LANCZOS)
    # Clean vector-sticker OUTLINE: a dark silhouette, dilated behind the
    # character — the single biggest "professional brand mascot" upgrade.
    try:
        alpha = img.split()[-1]
        k = max(3, int(size * 0.028)) | 1          # odd kernel
        dil = alpha.filter(ImageFilter.MaxFilter(k))
        sil = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sil.paste(Image.new("RGBA", img.size, OUTLINE), (0, 0), dil)
        img = Image.alpha_composite(sil, img)
    except Exception:  # noqa: BLE001
        pass
    return img


def build_mascot_loop(out_path: Path, *, size: int = 360, fps: int = 30,
                      seconds: float = 3.0, point_angle: float = 70.0,
                      flip: bool = False) -> Path:
    """Render a seamless idle loop (.mov, alpha) — bob + blink + arm wiggle.
    ``flip`` mirrors it horizontally so the pointing arm aims the other way
    (used when the mascot stands to the right of what it points at)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = int(fps * seconds)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for i in range(n):
            t = i / n
            bob = math.sin(t * 2 * math.pi) * (size * 0.026)   # livelier bob
            wiggle = math.sin(t * 2 * math.pi * 2)             # 2x lively arm
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
