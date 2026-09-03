"""GUARD: the data-explainer channel must never ship camera shake again.

Every video this channel posted for a month carried a handheld wobble. It was
not one bug — it was five independent oscillators, each added for a defensible
local reason (keep the host alive, keep the hook moving, keep frames from being
identical), which summed to a frame that never sat still:

  1. studio_render — the host overlay rode +6*sin(1.3*t) in x and +9*sin(2.1*t)
     in y, evaluated per frame, for the whole video.
  2. studio_render — the hook photo was pushed in with zoompan (1.12 -> 1.6).
     zoompan truncates its pan expressions to whole pixels each frame, so the
     full-frame image juddered.
  3. viz_scene — object sizes were multiplied by a sine of the build phase.
  4. mascot — the idle sprite loop raised and lowered the whole character on a
     cosine ("breathing").
  5. mascot_director — every posed frame added _s(t) * bob to the whole rig.

These tests fail the build if any of them return. They are deliberately a mix
of source assertions (for the ffmpeg filtergraph, which cannot be unit-rendered
cheaply) and behavioural assertions (which measure the drawing code directly).

Runs with pytest OR standalone:
    python3 data_learning/tests/test_no_camera_shake.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_STUDIO = (_REPO / "data_learning" / "studio_render.py").read_text()
_VIZ_SCENE = (_REPO / "data_learning" / "viz_scene.py").read_text()
_MASCOT = (_REPO / "data_learning" / "mascot.py").read_text()
_DIRECTOR = (_REPO / "data_learning" / "mascot_director.py").read_text()


# --------------------------------------------------------------------------- #
# 1 + 2: the ffmpeg filtergraph
# --------------------------------------------------------------------------- #
def test_no_zoompan_anywhere_in_the_studio_render():
    """zoompan pans in whole pixels — on a full-frame image that IS the shake."""
    offenders = [ln.strip() for ln in _STUDIO.splitlines() if "zoompan" in ln
                 and not ln.lstrip().startswith("#")]
    assert not offenders, f"zoompan is back in studio_render: {offenders[:3]}"


def test_no_periodic_term_in_any_overlay_position():
    """No sin/cos may drive an overlay's x/y — that is a moving camera."""
    bad = []
    for ln in _STUDIO.splitlines():
        code = ln.split("#", 1)[0]
        if not re.search(r"overlay=|^\s*(xe|ye)\s*=", code):
            continue
        if re.search(r"\b(sin|cos)\(", code):
            bad.append(ln.strip())
    assert not bad, f"periodic term driving frame position: {bad[:3]}"


# --------------------------------------------------------------------------- #
# 3: scene drawing must not pulse
# --------------------------------------------------------------------------- #
def test_scene_object_size_does_not_depend_on_build_phase():
    """Same reveal, different phase -> byte-identical drawing. A size that
    breathes with the build phase is a shake with a friendlier name."""
    from PIL import Image, ImageChops, ImageDraw
    from data_learning import viz_scene

    def _render(phase: float):
        canvas = Image.new("RGBA", (600, 900), (0, 0, 0, 0))
        d = ImageDraw.Draw(canvas)
        viz_scene.draw_object(d, canvas, (20, 20, 580, 880), None, 42.0,
                              "Kenya", "#4FD1C5", 1.0, 100.0,
                              side=True, phase=phase)
        return canvas

    a, b = _render(0.10), _render(0.85)
    assert ImageChops.difference(a, b).getbbox() is None, \
        "object drawing changes with build phase — the pulse is back"


def test_breathe_multiplier_is_gone_from_source():
    assert "_breathe" not in _VIZ_SCENE, "the _breathe oscillator is back"


# --------------------------------------------------------------------------- #
# 4: the sprite loop must not translate
# --------------------------------------------------------------------------- #
def test_idle_sprite_loop_does_not_move_the_character():
    """The loop composites at a fixed origin. A cosine offset here vibrated the
    host for the entire runtime of every video."""
    body = _MASCOT[_MASCOT.index("def _bob_loop"):]
    body = body[:body.index("\ndef ", 1)]
    moved = re.findall(r"alpha_composite\([^)]*\(0,\s*([^)]+)\)", body)
    assert moved, "could not find the composite call — test needs updating"
    for expr in moved:
        assert expr.strip() == "0", \
            f"idle loop translates the sprite by {expr!r} — the bob is back"


# --------------------------------------------------------------------------- #
# 5: the posed rig must not ride a sine
# --------------------------------------------------------------------------- #
def test_posed_rig_has_zero_idle_bob_at_every_phase():
    from data_learning import mascot_director as md
    spec = {"pose": {"lh": [150, 252, -8], "rh": [190, 252, 8],
                     "motion": {"limb": "both", "amp": 6}, "bob": 8}}
    for i in range(21):
        t = i / 20.0
        bob = md._a_pose(t, spec)[-1]
        assert bob == 0.0, f"_a_pose returns bob={bob} at t={t} — rig oscillates"


def _main() -> int:
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {fn.__name__}: {e}")
    print("PASS — no camera shake in the data channel" if not failed
          else f"{failed} FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_main())
