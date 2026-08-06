#!/usr/bin/env python3
"""THE FRAME IS NOT EMPTY ANY MORE — and the proof is pixels, not opinion.

`shared/scene_depth.py` exists because BORING (5 of 5 judged renders),
LOW_ENERGY (4 of 5) and EMPTY_COMPOSITION (3 of 5) outlived every fix in the
sprint, and because four blind judges across two films independently wrote
some version of "a stick figure on an empty blue slide".

Everything here is checkable in milliseconds with no ffmpeg, no film and no
judge, which is the whole point of `docs/SYSTEM_AUDIT.md`'s ruling that a
render is only ever spent on a plan not already known to be broken.

    python scripts/test_scene_depth.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from PIL import Image  # noqa: E402

from shared import scene_depth as sd  # noqa: E402


def _wash():
    """The background the channel shipped for months: a two-stop gradient."""
    import numpy as np
    yy = np.linspace(0, 1, 1080)[:, None]
    g = np.zeros((1080, 1920, 3), np.uint8)
    for c, (t, b) in enumerate(((22, 10), (26, 12), (46, 22))):
        g[..., c] = np.clip(t + (b - t) * yy, 0, 255)
    return Image.fromarray(g, "RGB")


def test_the_empty_slide_measures_as_empty():
    """The NEGATIVE CONTROL, and it comes first.

    A measure that cannot show the defect cannot show the fix. `occupancy`
    reports ~0 on the wash because a gradient is constant along every row —
    so anything it reports later is something that was PUT in the frame, not
    an artefact of how it counts.
    """
    assert sd.occupancy(_wash()) < 0.005, sd.occupancy(_wash())
    print("ok  the flat wash measures as an empty frame (the control)")


def test_every_world_populates_the_frame():
    base = _wash()
    for key in ("scene_sleep", "scene_work", "scene_screen", "scene_free",
                "scene_queue", "scene_traffic", "scene_hold", "scene_money"):
        occ = sd.occupancy(sd.Depth(base, key, 0).at(base, 0.0))
        assert occ > 0.04, f"{key} ({sd.name_for(key)}) still nearly empty: {occ}"
    print("ok  every scene kind gets a world with real objects in it")


def test_something_MOVES_in_the_wide_field():
    """LOW_ENERGY, measured. A colour ramp shifts every pixel by a fraction of
    a level; strata sliding at different rates move real edges."""
    base = _wash()
    for key in ("scene_work", "scene_free", "scene_queue", "scene_money"):
        d = sd.Depth(base, key, 0)
        e = sd.parallax_energy([d.at(base, 0.0), d.at(base, 1.0)])
        assert e > 0.2, f"{key} background is static: {e}"
    print("ok  the background moves, and by more than a colour ramp does")


def test_the_strata_move_at_DIFFERENT_rates():
    """The depth cue itself. Identical parallax across strata is one flat card
    sliding — it fills the frame and still reads as a slide."""
    for env in sd.ENVIRONMENTS:
        rates = {round(s[4], 4) for s in env}
        assert len(rates) >= 3, f"{env} slides as one plane: {rates}"
        # ...with one deliberate exception: lit windows ride the tower they
        # are cut into. A `windows` stratum on its own rate would slide off
        # its building, which is a worse artefact than a missing plane.
        by = {s[0]: s[4] for s in env}
        if "windows" in by:
            assert by["windows"] == by.get("towers"), \
                "lit windows must share their towers' parallax"
    print("ok  every world has three parallax planes; windows ride their towers")


def test_two_scenes_in_the_SAME_world_do_not_draw_the_same_picture():
    """The regression this module could most easily have become.

    `scene_queue` and `scene_hold` are both pinned to HALL, and the first
    version seeded the drawing on `len(scene_key)`, so they rendered a
    pixel-identical background: a fix for EMPTY_COMPOSITION that shipped
    SAMENESS. `_seed` + the per-stratum phase are what stop it.
    """
    import numpy as np
    base = _wash()

    def px(k):
        return np.asarray(sd.Depth(base, k, 0).at(base, 0.0), np.float32)

    for a, b in (("scene_queue", "scene_hold"), ("scene_sleep", "scene_work")):
        assert sd.name_for(a) == sd.name_for(b), "fixture assumes a shared world"
        assert float(np.abs(px(a) - px(b)).mean()) > 1.0, \
            f"{a} and {b} draw the same background"
    print("ok  two scenes sharing a world still draw two different pictures")


def test_a_scene_that_MEANS_a_place_keeps_it_across_repeats():
    """A bedroom that becomes a field on its second visit is not variety."""
    assert sd.name_for("scene_sleep", 0) == sd.name_for("scene_sleep", 3)
    assert sd.name_for("scene_sleep") == "room"
    assert sd.name_for("scene_traffic") == "street"
    print("ok  a pinned scene keeps its place on every repeat")


def test_the_pinned_names_are_reached_BY_BOTH_SPELLINGS():
    """`pro_render` says `scene_free`; `scenes` says `free_scene`.

    PLACES was first keyed on one of them only, so every pin silently missed
    and fell through to the hash rotation — a bed as likely to be outdoors as
    in. Nothing raised and no test existed; it was caught by printing the
    table and reading it.
    """
    for a, b, c in (("scene_free", "free_scene", "free"),
                    ("scene_sleep", "sleep_scene", "sleep")):
        assert sd.name_for(a) == sd.name_for(b) == sd.name_for(c), a
    print("ok  every spelling of a scene name reaches the same world")


def test_an_unpinned_scene_MOVES_between_repeats():
    """The other direction: a kind with no meaningful place must not stand in
    the same nowhere every time it appears."""
    got = {sd.name_for("scene_unknown_thing", i) for i in range(4)}
    assert len(got) >= 3, got
    print("ok  an unpinned scene lands somewhere new on repeat visits")


def test_the_world_never_outshines_the_character():
    """The failure mode where the fix becomes the complaint.

    The pictogram is (240, 244, 252). A stratum that approached it would make
    the environment the brightest thing in frame — busy instead of empty, and
    the judges would be just as right.
    """
    base = _wash()
    for key in ("scene_screen", "scene_money", "scene_traffic"):
        im = sd.Depth(base, key, 0).at(base, 0.0)
        peak = max(sum(p) / 3 for p in im.convert("RGB").getdata())
        assert peak < 170, f"{key} background peaks at {peak}, near the figure"
    print("ok  no stratum comes near the figure's brightness")


def test_strata_cover_the_whole_width_at_BOTH_ends_of_the_slide():
    """The off-screen bug, pinned.

    Strata are drawn into a tile three screens wide and composited at -w, so
    only the middle third is ever visible. The first version authored in
    SCREEN space (-w..2w), which put the room's window — a single, unrepeated
    element — in a third the camera never sees. It measured as an empty room
    and looked like one.
    """
    base = _wash()
    d = sd.Depth(base, "scene_sleep", 0)
    for t in (0.0, 0.5, 1.0):
        occ = sd.occupancy(d.at(base, t))
        assert occ > 0.04, f"room is empty at t={t}: {occ}"
    print("ok  the world is on camera at both ends of the parallax slide")


def test_it_never_raises_on_junk():
    """Staging is best-effort: a bad key costs a background, never a render."""
    base = _wash()
    for key in ("", None, "!!!", 42):
        sd.Depth(base, key, 0).at(base, 0.5)          # must not raise
    sd.Depth(base, "scene_free", -1).at(base, 2.0)    # clamped, not raised
    print("ok  junk input degrades to a plain background instead of raising")


if __name__ == "__main__":
    test_the_empty_slide_measures_as_empty()
    test_every_world_populates_the_frame()
    test_something_MOVES_in_the_wide_field()
    test_the_strata_move_at_DIFFERENT_rates()
    test_two_scenes_in_the_SAME_world_do_not_draw_the_same_picture()
    test_a_scene_that_MEANS_a_place_keeps_it_across_repeats()
    test_the_pinned_names_are_reached_BY_BOTH_SPELLINGS()
    test_an_unpinned_scene_MOVES_between_repeats()
    test_the_world_never_outshines_the_character()
    test_strata_cover_the_whole_width_at_BOTH_ends_of_the_slide()
    test_it_never_raises_on_junk()
    print("all scene-depth checks pass")
