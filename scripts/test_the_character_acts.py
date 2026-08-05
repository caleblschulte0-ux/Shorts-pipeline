#!/usr/bin/env python3
"""The "be extra" director added personality to the CHARTS and skipped the person.

THE DEFECT. `extra_director` says its job is to layer "CHARACTER and PHYSICS
onto the base animation, so the thing on screen reacts and has personality".
Every key in its `EXTRA_MOVES` table is a chart: flat_number, flat_compare,
flat_spin, flat_orbit. Not one `scene_*` kind — the kinds that literally put a
human being on screen.

On `shared-air` (10 scene shots, 0 flat shots) `apply()` therefore did
absolutely nothing, and the blind taste judge said NO_SOUL in three separate
verdicts. The rubric defines it as "nothing on screen has personality: no
character, no living scene, NO ACTING".

The acting engine already existed and was already wired into the scenes:
`expression.py` renders seven emotions as pose deltas, `scenes._expr_delta`
resolves them per frame, and `{"express": true}` fires it with the scene
choosing its own mood. Nothing ever set that flag except seven hand-authored
beats in `money-goes` — the one story that scored personality 3 and PASSED.

AND THE FIRST FIX APPEARED TO WORK WHILE CHANGING NOTHING. `exhaustion` is
rendered as arms_up / stride / head_drop, with `lean` left at zero. `_sit` only
accepted `lean`. So the on-hold scene resolved the emotion, read the flag,
computed the deltas — and drew an identical frame. ZERO pixels different. These
tests count pixels for that reason: a config that is set is not a performance.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from data_learning import extra_director as ed  # noqa: E402
from data_learning import planner, scenes  # noqa: E402


def _frame(fn, extra, d: Path, tag: str):
    import numpy as np
    from PIL import Image
    mp4 = d / f"{tag}.mp4"
    png = d / f"{tag}.png"
    fn(mp4, seconds=0.7, props=False, extra=extra)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.4",
                    "-i", str(mp4), "-frames:v", "1", str(png)], check=True)
    return np.asarray(Image.open(png).convert("RGB"), dtype=np.int16)


def test_the_director_reaches_the_CHARACTER_not_only_the_charts():
    for kind in ("scene_queue", "scene_hold", "scene_free", "scene_work"):
        spec = ed.extra_for(kind, 0, 10)
        assert spec.get("express") is True, (kind, spec)
        assert spec["expression"]["emotion"] == ed.SCENE_EMOTIONS[kind], spec
    # ...and the charts still get theirs
    assert ed.extra_for("flat_number", 0, 10).get("overshoot") is True
    # ...and footage is still left alone
    assert ed.extra_for("depict", 0, 10) == {}
    print("ok  scene kinds get an expression; charts keep theirs; footage untouched")


def test_the_intensity_RAMPS_like_everything_else():
    """The last scene should be the most felt, not the same as the first."""
    lo = ed.extra_for("scene_hold", 0, 10)["expression"]["intensity"]
    hi = ed.extra_for("scene_hold", 9, 10)["expression"]["intensity"]
    assert hi > lo, (lo, hi)
    assert 0.0 <= lo <= 1.0 and 0.0 <= hi <= 1.0, (lo, hi)
    print(f"ok  expression intensity ramps {lo} -> {hi} across the film")


def test_an_AUTHORED_expression_still_wins():
    """money-goes hand-authored seven of these and they must not be clobbered."""
    shots = [{"kind": "scene_hold",
              "extra": {"expression": {"emotion": "joy", "intensity": 1.0}}}]
    ed.apply(shots)
    assert shots[0]["extra"]["expression"]["emotion"] == "joy", shots[0]
    print("ok  an authored expression survives the director")


def test_IT_ACTUALLY_MOVES_PIXELS():
    """The one that matters, and the one the first attempt failed.

    A resolved emotion that the drawing code cannot express is not acting.
    """
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        import numpy as np
        for fn, name in ((scenes.queue_scene, "scene_queue"),
                         (scenes.hold_scene, "scene_hold"),
                         (scenes.free_scene, "scene_free")):
            emo = ed.SCENE_EMOTIONS[name]
            off = _frame(fn, None, d, f"{name}_off")
            on = _frame(fn, {"express": True,
                             "expression": {"emotion": emo, "intensity": 0.8}},
                        d, f"{name}_on")
            moved = int((np.abs(off - on).max(axis=2) > 12).sum())
            assert moved > 500, (
                f"{name} with emotion {emo!r} changed {moved} pixels — the "
                "expression is resolved but the drawing code cannot express "
                "it. `_sit` accepted only `lean`, and `exhaustion` does not "
                "move `lean`, so this read as wired while doing nothing.")
            print(f"ok  {name} ({emo}): {moved} pixels move when it acts")


def test_the_seated_figure_can_drop_its_head():
    """The specific missing degree of freedom, pinned."""
    import inspect
    assert "head_drop" in inspect.signature(scenes._sit).parameters, (
        "_sit lost its head_drop parameter — a seated figure cannot express "
        "exhaustion, resignation or burden without it")
    print("ok  _sit accepts head_drop")


def test_the_real_film_gets_a_performance():
    """Wiring, on the film that drew NO_SOUL three times."""
    beats = json.loads(
        (REPO / "data_learning" / "pro_stories" / "shared-air.beats.json")
        .read_text())["beats"]
    shots = ed.apply(planner.plan_story(beats, [5.0] * len(beats)))
    acting = [s for s in shots if (s.get("extra") or {}).get("expression")]
    figures = [s for s in shots if str(s.get("kind", "")).startswith("scene_")]
    assert figures, "no figure shots at all — a different regression"
    assert len(acting) == len(figures), (
        f"{len(acting)} of {len(figures)} figure shots act; every one should")
    print(f"ok  shared-air: all {len(acting)} figure shots carry a performance")


if __name__ == "__main__":
    test_the_director_reaches_the_CHARACTER_not_only_the_charts()
    test_the_intensity_RAMPS_like_everything_else()
    test_an_AUTHORED_expression_still_wins()
    test_the_seated_figure_can_drop_its_head()
    test_IT_ACTUALLY_MOVES_PIXELS()
    test_the_real_film_gets_a_performance()
    print("all character-acting checks pass")
