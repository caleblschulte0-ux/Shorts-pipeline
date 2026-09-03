"""RETIRED 2026-08-25 — the camera float is gone, and must not come back.

Operator ruling, verbatim: *"that camera shake that keeps plaguing our
videos — rip it out all the way, it's a cancer, I want no semblance of the
camera shake to exist."*

WHAT IT WAS, AND WHY IT WAS WRONG
---------------------------------
The showrunner's temporal grade measures change between CONSECUTIVE frames,
so a chart that finishes drawing and then HOLDS reads as duplicate frames
and fails. Instead of making the content move, this module manufactured the
motion the detector wanted: a slow Lissajous drift of the whole frame (the
last tuning was 44px at 2.1/1.7 rad/s), applied to the explainer master and
to every chart race.

That is gaming a gate, and it never fooled the person watching. The
operator called it out twice — "a weird shaking motion" on 2026-08-16, and
again as a cancer on 2026-08-25 — across two retunes that only ever traded
amplitude against frequency, because the axis the eye objects to
(acceleration) and the axis the meter reads (pixels per frame) are not the
same axis. Two independent oscillations (frame drift + a mascot hover) was
the worst of it; one was still wrong.

WHAT REPLACES IT
----------------
Real motion, which the content now actually has:

  * the mascot performs struggle reps across the whole beat rather than one
    arc spread over fifteen seconds (`charts._perf_phase`);
  * his anchor TOURS the ranking instead of parking on the winner the
    moment the build finishes (`charts._tour_index` / `_tour_tip`);
  * a chart race whose opening is a near-empty plot is now REFUSED before
    a slot is spent, by the composition floors in `engines.chart_race`
    (`OPEN_AREA_MIN` / `TRAVEL_MIN`), instead of being shaken into a pass.

The rule that follows, and the reason this file still exists as a headstone
rather than being deleted outright: **if a beat measures short on the
temporal grade, the answer is more REAL motion in that beat.** Never a
camera that moves to fool the meter, never a per-layer bob, never a
"breathing" crop. The gate is not the audience.

`tests/test_camera_float.py` holds this shut: nothing in the render paths
may import this module or reimplement its shape.
"""
from __future__ import annotations

RETIRED = True
RETIRED_ON = "2026-08-25"
RETIRED_BECAUSE = (
    "operator ruling: no camera shake, at all — manufactured motion is "
    "gaming the temporal gate, and it always looked like what it was"
)


def _refuse(*_a, **_k):
    raise RuntimeError(
        "shared.camera_float is RETIRED (2026-08-25 operator ruling: no "
        "camera shake, at all). A beat that measures short on the temporal "
        "grade needs more REAL motion — see the module docstring for what "
        "replaced this."
    )


# The old public surface, kept as loud refusals so a future caller fails at
# the import site with the reason instead of silently reintroducing shake.
px_per_frame = _refuse
overlay_xy = _refuse
crop_vf = _refuse
