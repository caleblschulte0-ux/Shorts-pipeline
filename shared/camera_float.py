"""Shared camera-float helper.

Trending still uses the existing shared motion profile because its temporal
QA contract depends on it. Data Explainer does not: operator review on
2026-08-31 explicitly rejected added camera drift / float / shake of any
kind. Its profile is therefore a literal fixed frame.

Profile selection is channel-scoped so this visual ruling cannot silently
change Trending. `CAMERA_FLOAT_PROFILE=default|explainer` remains available
for explicit local/test selection.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Existing shared/default profile. Keep byte-for-byte behavior for Trending
# and unknown callers.
DEFAULT_FLOAT_A = 44
DEFAULT_FLOAT_WX = 2.1
DEFAULT_FLOAT_WY = 1.7

# Explainer-only profile (operator ruling, 2026-08-31): NO artificial camera
# motion. Data/chart builds, mascot performance, transitions, etc. may animate
# because they are actual content. The camera itself stays fixed.
EXPLAINER_FLOAT_A = 0
EXPLAINER_FLOAT_WX = 0.0
EXPLAINER_FLOAT_WY = 0.0

# Default-channel temporal gate calibration. This is intentionally not a
# requirement for the Explainer profile; the point of that profile is to stop
# manufacturing motion solely to satisfy the gate.
MIN_PX_PER_FRAME = 2.9


def _auto_profile() -> str:
    """Resolve the visual profile without duplicating channel logic."""
    explicit = os.environ.get("CAMERA_FLOAT_PROFILE", "").strip().lower()
    if explicit in {"default", "explainer"}:
        return explicit

    workflow = os.environ.get("GITHUB_WORKFLOW", "").strip().lower()
    if workflow == "explainer stories":
        return "explainer"

    try:
        argv0 = Path(sys.argv[0]).as_posix().lower()
    except Exception:  # pragma: no cover - defensive only
        argv0 = ""
    if argv0.endswith("data_learning/studio_render.py") or Path(argv0).name == "studio_render.py":
        return "explainer"
    return "default"


def profile_constants(profile: str) -> tuple[int, float, float]:
    """Return (amplitude, wx, wy) for a named profile."""
    p = (profile or "default").strip().lower()
    if p == "explainer":
        return EXPLAINER_FLOAT_A, EXPLAINER_FLOAT_WX, EXPLAINER_FLOAT_WY
    if p == "default":
        return DEFAULT_FLOAT_A, DEFAULT_FLOAT_WX, DEFAULT_FLOAT_WY
    raise ValueError(f"unknown camera-float profile: {profile!r}")


PROFILE = _auto_profile()
FLOAT_A, FLOAT_WX, FLOAT_WY = profile_constants(PROFILE)


def px_per_frame(amp: float = FLOAT_A, w: float = FLOAT_WX,
                 fps: float = 30.0) -> float:
    """Peak per-frame displacement of `amp*sin(w*t)` sampled at `fps`."""
    return amp * w / float(fps)


def overlay_xy(x0: float, y0: float, *, amp: float = FLOAT_A,
               wx: float = FLOAT_WX, wy: float = FLOAT_WY) -> tuple[str, str]:
    """Return ffmpeg overlay x/y expressions for the selected profile."""
    if not amp or (not wx and not wy):
        return (f"{x0:g}", f"{y0:g}")
    return (f"{x0:g}+{amp:g}*sin({wx:g}*t)",
            f"{y0:g}+{amp:g}*cos({wy:g}*t)")


def crop_vf(w: int, h: int, *, amp: float = FLOAT_A, wx: float = FLOAT_WX,
            wy: float = FLOAT_WY) -> str:
    """Return a full-frame crop filter.

    For the Explainer profile (`amp == 0`) this is deliberately static: no
    time variable, no overscan, no drift, and therefore no camera-generated
    motion at all. Other profiles retain the historical floating crop.
    """
    if not amp or (not wx and not wy):
        return f"scale={w}:{h},crop={w}:{h}:x=0:y=0"
    return (f"scale={w + 2 * amp}:{h + 2 * amp},"
            f"crop={w}:{h}:x='{amp:g}+{amp:g}*sin({wx:g}*t)'"
            f":y='{amp:g}+{amp:g}*cos({wy:g}*t)'")
