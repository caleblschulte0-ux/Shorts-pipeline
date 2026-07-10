#!/usr/bin/env python3
"""Render the clip channel's procedural FX overlays (self-authored = CC0).

speedlines.png — anime-style radial motion lines on a transparent bg, drawn
outward from center with a clear hole in the middle so the subject stays
readable. The overlay layer flashes it (scale + fade) on the impact beat.
No external assets, so zero licensing risk.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
SIZE = 1080
CENTER = SIZE / 2
HOLE = SIZE * 0.30          # clear radius in the middle (subject stays visible)
EDGE = SIZE * 0.72          # lines reach out to here
N_LINES = 64


def speedlines() -> None:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # deterministic jitter so re-runs are identical (no RNG import needed)
    for i in range(N_LINES):
        ang = (i / N_LINES) * 2 * math.pi
        # vary length + width per line for a hand-drawn motion feel
        j = (i * 97) % 13
        r0 = HOLE + j * 4
        r1 = EDGE - (j % 5) * 10
        w = 3 + (j % 4)
        x0 = CENTER + r0 * math.cos(ang)
        y0 = CENTER + r0 * math.sin(ang)
        x1 = CENTER + r1 * math.cos(ang)
        y1 = CENTER + r1 * math.sin(ang)
        d.line([(x0, y0), (x1, y1)], fill=(255, 255, 255, 235), width=w)
    img.save(HERE / "speedlines.png")
    print(f"wrote speedlines.png {img.size}")


if __name__ == "__main__":
    speedlines()
