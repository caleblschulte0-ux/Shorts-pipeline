"""Generated abstract visual assets — no external media, no APIs.

Additive to the shared core. Used by the livestream module to produce themed
background loops entirely from ffmpeg's synthetic sources (the `gradients`
lavfi source + a vignette). The main app does NOT use this; adding it does not
change make_short.py's output (see tools/verify_identical.py).
"""
from __future__ import annotations

from pathlib import Path

from .constants import H, W
from .shell import run


def generate_abstract_clip(
    out: Path,
    duration: float,
    *,
    colors: list[str],
    speed: float = 0.012,
    fps: int = 30,
    w: int = W,
    h: int = H,
    vignette: bool = True,
) -> Path:
    """Render a themed abstract animated background (moving multi-stop gradient
    + optional vignette) to `out`. `colors` are hex strings ('0a1a3a' or
    '#0a1a3a'), 2-8 of them."""
    palette = [c.lstrip("#") for c in colors][:8]
    if len(palette) < 2:
        raise ValueError("generate_abstract_clip needs at least 2 colors")
    c_args = ":".join(f"c{i}=0x{c}" for i, c in enumerate(palette))
    src = (
        f"gradients=s={w}x{h}:{c_args}:n={len(palette)}"
        f":x0=0:y0=0:x1={w}:y1={h}:speed={speed}:d={duration:.3f}:r={fps}"
    )
    vf = "vignette" if vignette else "null"
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", src,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        str(out),
    ])
    return out


def make_seamless_loop(clip: Path, out: Path, *, fps: int = 30) -> Path:
    """Turn a clip into a perfectly seamless loop via boomerang (forward +
    reverse concat). The wrap returns to exactly the first frame, so an encoder
    can repeat the file 24/7 with no visible seam. Output length is 2x input."""
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(clip),
        "-filter_complex",
        "[0:v]split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1[v]",
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        str(out),
    ])
    return out
