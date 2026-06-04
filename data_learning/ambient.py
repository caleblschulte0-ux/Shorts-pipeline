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


def make_bokeh_strip(out_path: Path, *, n: int = 28, seed: int = 7) -> Path:
    """A 1080 x (2*H) RGBA strip of soft orbs, vertically seamless so a
    scrolling 1080xH window loops forever. Each orb is also drawn one tile
    up/down so it wraps across the seam. Softer/larger = dreamier."""
    rng = random.Random(seed)
    tile = H
    strip = Image.new("RGBA", (W, tile * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(strip)
    for _ in range(n):
        x = rng.randint(-120, W + 120)
        y = rng.randint(0, tile)
        r = rng.randint(90, 300)
        col = rng.choice(ORB_COLORS)
        alpha = rng.randint(24, 60)            # softer → calmer
        for yy in (y, y + tile):               # wrap copy for a seamless loop
            d.ellipse([x - r, yy - r, x + r, yy + r], fill=col + (alpha,))
    strip = strip.filter(ImageFilter.GaussianBlur(54))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    strip.save(out_path)
    return out_path


def gradient_lavfi(total: float, fps: int = 30) -> str:
    """lavfi source string for the slow, flowing base gradient."""
    return (
        f"gradients=s={W}x{H}:c0=0x080A14:c1=0x0e2444:c2=0x175852:c3=0x0a0e20:"
        f"x0=140:y0=240:x1=940:y1=1680:nb_colors=4:speed=0.0035:"
        f"duration={total:.2f}:rate={fps}")


def bg_filter(bokeh_idx: int, *, fps: int = 30) -> list[str]:
    """Filtergraph snippet: combines lavfi input 0 (gradient) with input
    ``bokeh_idx`` (the orb strip) into a labelled ``[bg]`` chain.

    Two parallax orb layers drift up at different speeds (slow = dreamy), a
    soft blur melts them together, and a gentle vignette settles the eye.
    """
    near = 12.0   # px/sec, foreground layer (slow = dreamier)
    far = 6.5     # px/sec, background layer (parallax depth)
    return [
        "[0:v]format=gbrp,eq=saturation=1.08:brightness=-0.02,format=rgba[grad]",
        f"[{bokeh_idx}:v]format=rgba,split[bkN][bkF]",
        # Foreground orbs scroll up; mod() makes the loop seamless.
        f"[bkN]crop={W}:{H}:0:'mod(t*{near}\\,{H})'[oN]",
        # Background layer: scaled + offset + slower for parallax depth.
        f"[bkF]scale={int(W * 1.3)}:-1,"
        f"crop={W}:{H}:{int(W * 0.15)}:'mod(t*{far}\\,{H})'[oF]",
        "[grad][oF]overlay=0:0[d1]",
        "[d1][oN]overlay=0:0[lit]",
        "[lit]gblur=sigma=4,vignette=PI/5.5[bg]",
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
