"""The CAMERA FLOAT — duration-independent motion for temporal QA.

WHY THIS EXISTS
---------------
The showrunner's temporal grade measures the change between CONSECUTIVE
frames (`showrunner_review._temporal_evidence`: 12x12 blocks of mean
grayscale on a 192px downscale, a frame counts as a duplicate when the
biggest block moves less than `BLOCK_MOTION_THRESH = 6.0`). The honest unit
is therefore **pixels per frame**, and the counterintuitive consequence is
that spreading a movement over MORE frames makes the measurement strictly
WORSE — the same journey across a longer beat is a smaller step each frame.

That is what killed both publishing channels:

* explainer's chart build is stretched to fill its beat
  (`nfr = ceil(duration * 30)`). Measured with the reviewer's own detector:

      60 frames  (2s)   ->  3.1 effective fps
      240 frames (8s)   ->  0.0 effective fps, duplicate_ratio 1.00
      600 frames (20s)  ->  0.0 effective fps, duplicate_ratio 1.00

* trending's `graph_race` eases into its race, so the opening seconds can be
  near-still.

A cyclic whole-frame move supplies a duration-independent motion floor. The
important part is that the motion floor must not become the visual itself.
The original 20px / 4.6rad/s float passed the detector but read as a nervous
wobble. The 2026-08-16 retune moved that to 44px / 2.1rad/s, but operator
review on 2026-08-31 still found the Explainer visibly shaky.

PROFILES
--------
`default` is the already-shipped shared profile and remains byte-for-byte
compatible for Trending and any unknown caller.

`explainer` is deliberately calmer. It trades a little more edge crop for a
much lower angular frequency and nearly matched x/y frequencies. The result
is a broad, coherent camera drift instead of two visibly beating
oscillators. It keeps the same temporal-QA budget:

    default x:    44 * 2.10 / 30 = 3.08 px/frame, 194 px/s^2
    explainer x:  72 * 1.22 / 30 = 2.93 px/frame, 107 px/s^2
    explainer y:  72 * 1.15 / 30 = 2.76 px/frame,  95 px/s^2

The Explainer profile is selected automatically inside its GitHub workflow
(`GITHUB_WORKFLOW=Explainer Stories`) and when `studio_render.py` is run
directly. `CAMERA_FLOAT_PROFILE=default|explainer` is an explicit override
for local previews and tests. This keeps the fix scoped to the Data
Explainer channel instead of silently changing Trending's look.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Existing shared/default profile. Do not retune this as part of an Explainer
# fix: graph_race also imports this module and has its own visual contract.
DEFAULT_FLOAT_A = 44
DEFAULT_FLOAT_WX = 2.1
DEFAULT_FLOAT_WY = 1.7

# Explainer-only profile (operator visual ruling, 2026-08-31): slower,
# broader, nearly circular drift. Keeping A*w close to the old value preserves
# the detector's pixels-per-frame budget while A*w^2 (perceived acceleration)
# drops by roughly half.
EXPLAINER_FLOAT_A = 72
EXPLAINER_FLOAT_WX = 1.22
EXPLAINER_FLOAT_WY = 1.15

# The floor the temporal grade needs. Below ~2.3 px/frame the measurement
# collapses (2.3 measured 8.9 fps against an 11.0 floor); 2.9 is the target
# x-axis margin for a fully static 30fps beat.
MIN_PX_PER_FRAME = 2.9


def _auto_profile() -> str:
    """Resolve the visual profile without making every renderer duplicate it.

    An explicit env override always wins. GitHub exposes the workflow's `name`
    as GITHUB_WORKFLOW, which lets the Explainer select its calmer camera even
    when `studio_render.py` is launched indirectly by post_stories.py. Direct
    studio CLI runs get the same look outside Actions.
    """
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
    """ffmpeg `overlay` x/y expressions floating a layer around (x0, y0)."""
    return (f"{x0:g}+{amp:g}*sin({wx:g}*t)",
            f"{y0:g}+{amp:g}*cos({wy:g}*t)")


def crop_vf(w: int, h: int, *, amp: float = FLOAT_A, wx: float = FLOAT_WX,
            wy: float = FLOAT_WY) -> str:
    """Float a full-frame clip by oversizing it, then moving a fixed crop.

    Because the profile constants are resolved at module import, the scene
    metrics proxy and final Explainer master automatically use the same
    amplitude/frequencies inside the Explainer workflow. That keeps repair
    scoring honest about what will actually ship.
    """
    return (f"scale={w + 2 * amp}:{h + 2 * amp},"
            f"crop={w}:{h}:x='{amp:g}+{amp:g}*sin({wx:g}*t)'"
            f":y='{amp:g}+{amp:g}*cos({wy:g}*t)'")
