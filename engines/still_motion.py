"""Canonical Ken Burns (zoompan) implementation.

This is the future single home of the effect that today exists as three
private copies (make_explainer_stacked.py:1574, data_learning/
longform_render.py:526, data_learning/studio_render.py:1029). Those
renderers have NOT been migrated — doing so is Ticket E1 in
docs/ENGINE_REGISTRY.md (parity render first, then one renderer behind a
flag, then the rest). Until then this module is the callable other
consumers should build against.

Design notes carried over from the renderer copies:
- Work at 2x resolution then let zoompan scale down, so the zoom doesn't
  quantize into stair-stepped frames.
- Composite the (possibly transparent) source onto a solid canvas first so
  alpha never reaches the H.264 encoder as black.
- Alternate zoom-in / zoom-out via `direction` so successive shots vary.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

DEFAULT_BG = "0x1f2a3a"  # slate blue used across the pipeline — never black


def kenburns(
    image: str | Path,
    out: str | Path,
    duration: float,
    *,
    size: tuple[int, int] = (1080, 1920),
    fps: int = 30,
    direction: str = "in",       # "in" | "out"
    max_zoom: float = 1.18,
    bg_color: str = DEFAULT_BG,
    crf: int = 20,
) -> Path:
    """Render `image` as a `duration`-second H.264 clip with a slow push.

    Raises on failure (corrupt image, missing ffmpeg). Callers that need
    the best-effort contract should use `maybe_kenburns`.
    """
    w, h = int(size[0]), int(size[1])
    frames = max(2, int(duration * fps))
    if direction == "in":
        step = (max_zoom - 1.0) / frames
        z_expr = f"min(zoom+{step:.6f},{max_zoom})"
    else:
        step = (max_zoom - 1.0) / frames
        z_expr = f"if(eq(on,0),{max_zoom},max(zoom-{step:.6f},1.0))"
    filt = (
        f"[1:v]scale={w * 2}:{h * 2}[canvas];"
        f"[0:v]scale={w * 2}:{h * 2}:force_original_aspect_ratio=decrease[fg];"
        f"[canvas][fg]overlay=(W-w)/2:(H-h)/2:format=auto[stage];"
        f"[stage]zoompan=z='{z_expr}'"
        f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={w}x{h}:fps={fps},"
        f"setsar=1,format=yuv420p[outv]"
    )
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-loop", "1", "-i", str(image),
            "-f", "lavfi", "-i", f"color=c={bg_color}:s={w * 2}x{h * 2}:r={fps}",
            "-t", f"{duration:.3f}",
            "-filter_complex", filt, "-map", "[outv]",
            "-an", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", str(crf), str(out),
        ],
        check=True,
    )
    return out


def maybe_kenburns(image, out, duration, **kwargs) -> Path | None:
    """Best-effort wrapper: result on success, None on any failure."""
    try:
        return kenburns(image, out, duration, **kwargs)
    except Exception as e:  # noqa: BLE001 — contract: never raise into a caller
        print(f"[engines.still_motion] kenburns failed: {e}")
        return None


def available() -> bool:
    import shutil
    return shutil.which("ffmpeg") is not None
