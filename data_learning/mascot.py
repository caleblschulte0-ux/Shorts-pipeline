"""Mascot — a deterministic, always-identical cute host character.

Drawn purely from code (PIL), so it looks exactly the same every render —
no image model, no drift. Simple and lovable: a round teal blob, big eyes,
blush, a little smile, and a tiny graduation cap (on-theme for a learning
channel). It does a gentle idle: a slow vertical bob plus an occasional
blink.

:func:`build_mascot_loop` renders a short seamless idle loop to a .mov with
an alpha channel (qtrle) so the studio renderer can overlay it on the
ambient background and ``-stream_loop`` it for the whole video.
"""
from __future__ import annotations

import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

# Palette (matches the chart house style).
BODY = (79, 209, 197, 255)        # #4FD1C5 teal
BODY_DK = (45, 160, 150, 255)     # shading / outline
WHITE = (248, 250, 252, 255)
DARK = (11, 16, 32, 255)          # #0B1020 pupils + hat
BLUSH = (249, 168, 212, 200)      # soft pink
GOLD = (245, 158, 11, 255)        # tassel
SS = 3                            # supersample factor for smooth edges


def _draw(size: int, bob: float, blink: float) -> Image.Image:
    """One mascot frame. ``bob`` in px (vertical), ``blink`` 0..1 (1=closed)."""
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = S // 2
    cy = S // 2 + int(bob * SS)
    r = int(S * 0.30)              # body radius

    # Feet.
    fw = int(r * 0.42)
    fy = cy + int(r * 0.86)
    for sgn in (-1, 1):
        fx = cx + sgn * int(r * 0.42)
        d.ellipse([fx - fw // 2, fy - fw // 3, fx + fw // 2, fy + fw // 3],
                  fill=BODY_DK)

    # Body (egg-ish: slightly taller than wide).
    d.ellipse([cx - r, cy - int(r * 1.12), cx + r, cy + int(r * 1.05)],
              fill=BODY)
    # Subtle bottom shading.
    d.ellipse([cx - int(r * 0.7), cy + int(r * 0.2),
               cx + int(r * 0.7), cy + int(r * 1.0)], fill=BODY_DK)
    d.ellipse([cx - r, cy - int(r * 1.12), cx + r, cy + int(r * 1.0)],
              fill=BODY)

    # Eyes.
    eye_dx = int(r * 0.42)
    eye_y = cy - int(r * 0.18)
    eye_r = int(r * 0.26)
    pup_r = int(r * 0.12)
    for sgn in (-1, 1):
        ex = cx + sgn * eye_dx
        if blink > 0.6:
            # Closed eye: a happy downward arc.
            d.arc([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r],
                  start=200, end=340, fill=DARK, width=max(2, S // 110))
        else:
            d.ellipse([ex - eye_r, eye_y - eye_r, ex + eye_r, eye_y + eye_r],
                      fill=WHITE)
            d.ellipse([ex - pup_r, eye_y - pup_r + int(eye_r * 0.2),
                       ex + pup_r, eye_y + pup_r + int(eye_r * 0.2)], fill=DARK)
            # Catchlight.
            hl = max(2, int(pup_r * 0.5))
            d.ellipse([ex - pup_r + hl // 2, eye_y - pup_r + int(eye_r * 0.1),
                       ex - pup_r + hl + hl, eye_y - pup_r + hl + int(eye_r * 0.1)],
                      fill=WHITE)

    # Blush.
    bl_r = int(r * 0.14)
    bl_y = cy + int(r * 0.12)
    for sgn in (-1, 1):
        bx = cx + sgn * int(r * 0.66)
        d.ellipse([bx - bl_r, bl_y - bl_r // 2, bx + bl_r, bl_y + bl_r // 2],
                  fill=BLUSH)

    # Smile.
    mw = int(r * 0.36)
    my = cy + int(r * 0.30)
    d.arc([cx - mw, my - mw, cx + mw, my + mw], start=20, end=160,
          fill=DARK, width=max(2, S // 120))

    # Graduation cap.
    cap_y = cy - int(r * 1.05)
    board_w = int(r * 1.5)
    board_h = int(r * 0.18)
    # Cap crown.
    d.ellipse([cx - int(r * 0.5), cap_y - board_h, cx + int(r * 0.5),
               cap_y + int(r * 0.34)], fill=DARK)
    # Mortarboard (a diamond / rotated square).
    bx = cx
    by = cap_y - int(board_h * 0.2)
    diamond = [(bx, by - board_h), (bx + board_w // 2, by),
               (bx, by + board_h), (bx - board_w // 2, by)]
    d.polygon(diamond, fill=DARK)
    # Button + tassel.
    d.ellipse([bx - SS * 2, by - SS * 2, bx + SS * 2, by + SS * 2], fill=GOLD)
    tx = bx + board_w // 2
    d.line([(bx, by), (tx, by), (tx, by + int(r * 0.45))], fill=GOLD,
           width=max(2, S // 150))
    d.ellipse([tx - SS * 3, by + int(r * 0.45) - SS * 2,
               tx + SS * 3, by + int(r * 0.45) + SS * 4], fill=GOLD)

    return img.resize((size, size), Image.LANCZOS)


def build_mascot_loop(out_path: Path, *, size: int = 320, fps: int = 30,
                      seconds: float = 3.0) -> Path:
    """Render a seamless idle loop (.mov, alpha) used by the studio renderer."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = int(fps * seconds)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for i in range(n):
            t = i / n
            bob = math.sin(t * 2 * math.pi) * (size * 0.018)   # gentle bob
            # One blink near 70% through the loop.
            blink = 0.0
            bphase = (t - 0.70) * n / fps
            if 0 <= bphase <= 0.18:
                blink = 1.0
            _draw(size, bob, blink).save(td / f"m{i:04d}.png")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
             "-i", str(td / "m%04d.png"),
             "-c:v", "qtrle", "-pix_fmt", "argb", str(out_path)],
            check=True)
    return out_path


def save_static(out_path: Path, size: int = 320) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _draw(size, 0.0, 0.0).save(out_path)
    return out_path


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/mascot.png")
    save_static(out)
    print("wrote", out)
