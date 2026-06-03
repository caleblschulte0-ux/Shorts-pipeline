"""Ambient background — calming, "zone-out" motion behind the data.

A deep flowing gradient (slow colour drift) plus soft blurred bokeh orbs
that drift gently upward. It's meant to be pleasant to rest your eyes on
while listening — satisfying but low-contrast, never a game and never
fighting the chart for attention.

The orbs are pre-rendered once to a vertically-seamless strip (PIL); ffmpeg
scrolls and loops that strip over the animated gradient, so per-frame cost
stays in ffmpeg (fast) rather than Python.
"""
from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

W, H = 1080, 1920

# Soft orb colours (R,G,B). Mostly cool, a couple warm for life.
ORB_COLORS = [
    (79, 209, 197),    # teal
    (96, 165, 250),    # blue
    (79, 209, 197),
    (165, 180, 252),   # periwinkle
    (245, 158, 11),    # amber (sparse)
]


def make_bokeh_strip(out_path: Path, *, n: int = 20, seed: int = 7) -> Path:
    """A 1080 x (2*H) RGBA strip of soft orbs, vertically seamless so a
    scrolling 1080xH window loops forever. Each orb is also drawn one tile
    up/down so it wraps across the seam."""
    rng = random.Random(seed)
    tile = H
    strip = Image.new("RGBA", (W, tile * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(strip)
    for _ in range(n):
        x = rng.randint(-80, W + 80)
        y = rng.randint(0, tile)
        r = rng.randint(70, 230)
        col = rng.choice(ORB_COLORS)
        alpha = rng.randint(34, 78)
        for yy in (y, y + tile):       # wrap copy for a seamless loop
            d.ellipse([x - r, yy - r, x + r, yy + r], fill=col + (alpha,))
    strip = strip.filter(ImageFilter.GaussianBlur(46))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    strip.save(out_path)
    return out_path


def gradient_lavfi(total: float, fps: int = 30) -> str:
    """lavfi source string for the flowing base gradient."""
    return (
        f"gradients=s={W}x{H}:c0=0x0A0E1C:c1=0x12325a:c2=0x1d6e69:c3=0x0c1230:"
        f"x0=140:y0=240:x1=940:y1=1680:nb_colors=4:speed=0.008:"
        f"duration={total:.2f}:rate={fps}")


def bg_filter(bokeh_idx: int, *, fps: int = 30, scroll: float = 26.0) -> list[str]:
    """Filtergraph snippet: combines lavfi input 0 (gradient) with input
    ``bokeh_idx`` (the orb strip) into a labelled ``[bg]`` chain.

    The orbs scroll upward (``mod`` keeps it looping), get a slow hue drift
    for life, and a vignette focuses the eye toward the centre.
    """
    return [
        f"[0:v]format=gbrp,eq=saturation=1.12:brightness=-0.015,format=rgba[grad]",
        # Scroll a 1080xH window up the 2*H strip; loops via mod().
        f"[{bokeh_idx}:v]format=rgba,"
        f"crop={W}:{H}:0:'mod(n*{scroll/fps:.4f}*{fps}\\,{H})'[orbs]",
        f"[grad][orbs]overlay=0:0:format=auto[lit]",
        f"[lit]gblur=sigma=2,vignette=PI/4.5[bg]",
    ]


if __name__ == "__main__":
    import subprocess
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/ambient_demo.mp4")
    strip = make_bokeh_strip(Path("/tmp/_bokeh.png"))
    total = 6.0
    fc = ";".join(bg_filter(1))
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", gradient_lavfi(total),
         "-loop", "1", "-i", str(strip),
         "-filter_complex", fc, "-map", "[bg]", "-t", f"{total}",
         "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)],
        check=True)
    print("wrote", out)
