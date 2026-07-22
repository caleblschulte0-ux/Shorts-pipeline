"""Mascot — 'Data', the channel host: a teal monster-professor in a lab coat.

The look is defined once as parametric SVG in ``scripts/build_mascot_svg.py``
and rasterised to transparent square PNGs under ``assets/mascot/host/``
(committed). This module composites those PNGs into the alpha ``.mov`` loop
the studio renderer overlays — so the host is byte-for-byte identical in
every render (no image model, no drift) and CI needs no SVG rasteriser.

He is a fixed rig with named poses (idle / point / shock / laugh / think /
cheer / duck / ride). The renderer picks a pose per beat so the host reacts
through the video instead of standing still — he's the main character, not a
side piece.

:func:`build_mascot_loop` renders a short seamless idle loop (gentle breath
bob) to a ``.mov`` with an alpha channel (qtrle) the renderer overlays and
``-stream_loop``s. ``point_angle`` is kept for backward compatibility: when
no explicit ``pose`` is given it maps a side angle to the pointing pose.
"""
from __future__ import annotations

import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

HOST_DIR = Path(__file__).resolve().parent.parent / "assets" / "mascot" / "host"
POSES = ("idle", "point", "shock", "laugh", "think", "cheer", "duck", "ride")
DEFAULT_POSE = "idle"

_CACHE: dict[str, Image.Image] = {}


def _load(pose: str) -> Image.Image:
    """Load a pose PNG (RGBA), cached. Falls back to idle if a pose file is
    missing so a render never dies over a typo'd pose name."""
    if pose not in POSES:
        pose = DEFAULT_POSE
    if pose not in _CACHE:
        p = HOST_DIR / f"{pose}.png"
        if not p.exists():
            p = HOST_DIR / f"{DEFAULT_POSE}.png"
        _CACHE[pose] = Image.open(p).convert("RGBA")
    return _CACHE[pose]


def _pose_for_angle(point_angle: float) -> str:
    """Legacy mapping: callers that only pass an angle get 'point' when the
    arm aims to the side (< ~55 deg from horizontal), else the idle host."""
    return "point" if point_angle < 55.0 else DEFAULT_POSE


def _frame(size: int, pose: str, bob: float, flip: bool) -> Image.Image:
    """One composited frame: the pose PNG scaled to size, nudged vertically by
    ``bob`` px (breathing), optionally mirrored, on a transparent size canvas."""
    src = _load(pose).resize((size, size), Image.LANCZOS)
    if flip:
        src = src.transpose(Image.FLIP_LEFT_RIGHT)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(src, (0, max(0, int(bob))))
    return canvas


def _bob_loop(out_path: Path, base: Image.Image, size: int, fps: int,
              seconds: float, flip: bool) -> Path:
    """Loop a single mascot frame with a gentle seamless breathing bob."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    base = base.resize((size, size), Image.LANCZOS)
    if flip:
        base = base.transpose(Image.FLIP_LEFT_RIGHT)
    n = max(1, int(fps * seconds))
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for i in range(n):
            t = i / n
            bob = (1 - math.cos(t * 2 * math.pi)) * 0.5 * (size * 0.022)
            canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            canvas.alpha_composite(base, (0, max(0, int(bob))))
            canvas.save(td / f"m{i:04d}.png")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
             "-i", str(td / "m%04d.png"),
             "-c:v", "qtrle", "-pix_fmt", "argb", str(out_path)],
            check=True)
    return out_path


def build_mascot_loop(out_path: Path, *, size: int = 360, fps: int = 30,
                      seconds: float = 3.0, point_angle: float = 90.0,
                      flip: bool = False, pose: str | None = None) -> Path:
    """Render a seamless idle loop (.mov, alpha) — a gentle breathing bob.
    ``pose`` selects the expression; if omitted it is derived from
    ``point_angle`` for backward compatibility. ``flip`` mirrors horizontally."""
    pose = pose or _pose_for_angle(point_angle)
    return _bob_loop(out_path, _load(pose), size, fps, seconds, flip)


def build_scene_loop(out_path: Path, spec: dict, *, size: int = 360,
                     fps: int = 20, seconds: float = 1.0,
                     flip: bool = False) -> Path:
    """Render Data ANIMATED — performing a director-chosen scene action (moving,
    with props, grounded in a little environment) — as a seamless alpha loop.
    Every animator is periodic so frame N wraps to frame 0. Falls back to the
    idle host (bobbed still) if the director/rasteriser is unavailable, so a
    render never dies over a prop."""
    import io
    n = max(2, int(fps * seconds))
    try:
        from data_learning import mascot_director as director
        frames = director.render_frames(spec, size, n=n)
    except Exception as e:  # noqa: BLE001
        print(f"[mascot] scene anim failed ({e}); idle host", flush=True)
        return _bob_loop(out_path, _load(DEFAULT_POSE), size, fps, seconds, flip)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for i, b in enumerate(frames):
            im = Image.open(io.BytesIO(b)).convert("RGBA")
            if flip:
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
            im.save(td / f"m{i:04d}.png")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
             "-i", str(td / "m%04d.png"),
             "-c:v", "qtrle", "-pix_fmt", "argb", str(out_path)],
            check=True)
    return out_path


def save_static(out_path: Path, size: int = 360, point_angle: float = 90.0,
                pose: str | None = None) -> Path:
    """Write a single still PNG of the host (used by the v2 / cinematic paths)."""
    pose = pose or _pose_for_angle(point_angle)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _frame(size, pose, 0.0, False).save(out_path)
    return out_path


if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/mascot.png")
    pz = sys.argv[2] if len(sys.argv) > 2 else "idle"
    save_static(out, pose=pz)
    print("wrote", out)
