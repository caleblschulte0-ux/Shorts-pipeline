#!/usr/bin/env python3
"""Turning a prop's TEXT off does not turn the prop off.

THE DEFECT, and it was mine. On 2026-08-02 the three neutral stagings gained a
`props=False` mode so an unlicensed beat could keep a person on screen without
asserting a subject the film never had ("NOW SERVING", "ON HOLD", "YEARS ARE
YOURS"). In `queue_scene` the counter's glowing orange panel was drawn OUTSIDE
the `if props:` block, so `props=False` stripped the words off it and left a
lit, saturated, empty rectangle floating at frame right.

That is not a smaller claim. It is precisely what the blind taste judge
described when it labelled an earlier render EMPTY_COMPOSITION and UI_WIDGET:
"a dashboard plate ... a template with the content not filled in."

Found by rendering the frame and looking at it. No metric in this repo would
have caught it — the shot kind was right, the person was present, the film
specific text was gone. This test therefore checks PIXELS, because that is
where the defect lives.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from data_learning import scenes  # noqa: E402

# The accent the counter panel is filled with, and the tolerance a JPEG-ish
# encode needs. Deliberately the literal value from `queue_scene` — if someone
# restyles the panel this test should be updated with it, not silently pass.
ACCENT = (228, 120, 92)
TOL = 40


def _frame(fn, props: bool, d: Path):
    """One mid-clip frame. 0.7s rather than a couple of seconds: these scenes
    generate every frame in Python, so the clip length IS the test's runtime,
    and one frame is all this checks."""
    from PIL import Image
    mp4 = d / f"s_{fn.__name__}_{int(props)}.mp4"
    png = mp4.with_suffix(".png")
    fn(mp4, seconds=0.7, props=props)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "0.35",
                    "-i", str(mp4), "-frames:v", "1", str(png)], check=True)
    return Image.open(png).convert("RGB")


def _accent_pixels(im) -> int:
    """Count pixels near the panel accent. numpy, not a Python loop — a 1920x1080
    frame is 2M pixels and three of them per test is a minute of CI time."""
    import numpy as np
    a = np.asarray(im, dtype=np.int16)
    return int((np.abs(a - np.array(ACCENT, dtype=np.int16)).max(axis=2) <= TOL).sum())


def _bright_pixels(im) -> int:
    import numpy as np
    a = np.asarray(im, dtype=np.int16)
    return int((a.min(axis=2) > 200).sum())


def test_props_off_leaves_no_lit_empty_panel():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        on = _accent_pixels(_frame(scenes.queue_scene, True, d))
        off = _accent_pixels(_frame(scenes.queue_scene, False, d))
    assert on > 2000, (
        f"the NOW SERVING panel should dominate with props ON; saw {on} px — "
        "if the scene was restyled, update ACCENT in this test")
    assert off < on * 0.02, (
        f"props=False still paints {off} accent pixels ({off / max(on, 1):.0%} "
        "of the lit panel). Removing a widget's TEXT does not remove the "
        "widget — an empty lit plate is the EMPTY_COMPOSITION / UI_WIDGET the "
        "propless mode exists to avoid.")
    print(f"ok  queue_scene: {on} accent px with props, {off} without")


def test_the_person_survives_the_prop_removal():
    """The whole point of propless mode: no claim, but still a human.

    Banning the scene library outright removed all 14 character shots from
    shared-air and cost a full point of score. `props=False` must never become
    a slower version of that.
    """
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for fn in (scenes.queue_scene, scenes.hold_scene, scenes.free_scene):
            bright = _bright_pixels(_frame(fn, False, d))
            assert bright > 3000, (
                f"{fn.__name__}(props=False) has only {bright} near-white "
                "pixels — the white pictogram figure is missing, which makes "
                "this a blank room rather than a person in one")
            print(f"ok  {fn.__name__}: figure present with props off ({bright} px)")


if __name__ == "__main__":
    test_props_off_leaves_no_lit_empty_panel()
    test_the_person_survives_the_prop_removal()
    print("all propless-staging checks pass")
