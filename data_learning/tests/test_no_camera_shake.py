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
# 0: the whole-frame camera float (the big one)
# --------------------------------------------------------------------------- #
def test_data_channel_never_applies_the_camera_float():
    """shared/camera_float.py describes itself as "a slow Lissajous drift of
    the visual layer — a hand-held/breathing camera", implemented as a moving
    crop window over an oversized frame. It was added to feed the showrunner's
    per-frame motion detector and it moved EVERY pixel of EVERY frame.

    Other channels may keep it. The data channel may not touch it.
    """
    live = [ln.strip() for ln in _STUDIO.splitlines()
            if ("camera_float" in ln or "crop_vf" in ln or "_cf." in ln)
            and not ln.lstrip().startswith("#")]
    assert not live, f"the camera float is back in the data render: {live[:3]}"


def test_no_moving_crop_window_anywhere_in_the_data_render():
    """The float's shape, independent of which module it comes from: a crop
    whose x or y is a function of time."""
    bad = []
    for src, name in ((_STUDIO, "studio_render"), (_VIZ_SCENE, "viz_scene")):
        for ln in src.splitlines():
            code = ln.split("#", 1)[0]
            if "crop=" in code and re.search(r"(sin|cos)\(", code):
                bad.append(f"{name}: {ln.strip()[:70]}")
    assert not bad, f"a moving crop window is back: {bad[:3]}"


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


# --------------------------------------------------------------------------- #
# 6: the chokepoint — the whole body never translates or rotates
# --------------------------------------------------------------------------- #
def test_no_periodic_whole_body_term_in_any_animator():
    """The rule is not "the body never moves" — a crouch, a drive and a
    progressive lean are the performance, and the acting gate needs them.
    The rule is that whole-body motion may never be PERIODIC:

      * no `bob` driven by _s(t), which is sin(2*pi*t) — a continuous breath
        that runs for the entire video;
      * no `tilt` driven by sin(x * pi * N) with N >= 2 — a rattle of several
        cycles inside a single phase.

    Both read as a vibrating character, which is what a viewer calls camera
    shake. One-shot arcs (sin(s*pi), or anything linear in phase) are fine.
    """
    bad = []
    for i, ln in enumerate(_DIRECTOR.splitlines(), 1):
        code = ln.split("#", 1)[0]
        if re.search(r"\bbob\s*=.*_s\(", code):
            bad.append(f"{i}: continuous breath -> {ln.strip()[:70]}")
        m = re.search(r"\btilt\s*=\s*math\.sin\([a-z_]+ \* math\.pi \* ([\d.]+)\)",
                      code)
        if m and float(m.group(1)) >= 2:
            bad.append(f"{i}: {m.group(1)}-cycle rattle -> {ln.strip()[:70]}")
    assert not bad, "periodic whole-body motion is back:\n  " + "\n  ".join(bad[:5])


def test_no_breath_returned_inline_by_a_legacy_animator():
    """The legacy actions return their bob as the last element of the tuple —
    `..., R.mouth_o(), _s(t) * 3)` — never assigning it to a name, so the scan
    above cannot see it. This caught a real escape during mutation testing."""
    bad = [f"{i}: {ln.strip()[:74]}"
           for i, ln in enumerate(_DIRECTOR.splitlines(), 1)
           if re.search(r",\s*(abs\()?_s\(t\)\)?\s*\*\s*[\d.]+\)\s*$",
                        ln.split("#", 1)[0])]
    assert not bad, "a breathing bob is back in a return tuple:\n  " + "\n  ".join(bad[:5])


def test_no_animator_bob_is_antisymmetric_over_the_cycle():
    """Behavioural periodicity detector, independent of how the code is spelled.

    A continuous breath is bob(t) = A*sin(2*pi*t), so bob(t + 0.5) == -bob(t)
    for every t. Real acting (a crouch that descends, a hop that lands) does
    not have that symmetry. Any animator whose bob is antisymmetric across the
    half-cycle AND not flat is vibrating.
    """
    from data_learning import mascot_director as md
    offenders = []
    for name, fn in sorted(md.ANIMATORS.items()):
        try:
            bobs = [(fn(i / 16.0, md.price_tag)[6],
                     fn((i / 16.0 + 0.5) % 1.0, md.price_tag)[6])
                    for i in range(16)]
        except Exception:                     # animator needs a different prop
            continue
        if any(abs(a) > 1e-9 for a, _ in bobs) and \
                all(abs(a + b) < 1e-6 for a, b in bobs):
            offenders.append(name)
    assert not offenders, f"antisymmetric (sine) bob in animators: {offenders}"


def test_body_pixels_do_not_move_between_phases():
    """Pixel proof: the legs/feet band is byte-identical across a full phase
    cycle. Arms may (and should) move; the body may not."""
    import io
    from PIL import Image, ImageChops
    from data_learning import mascot_director as md
    spec = {"action": "present", "prop": "price_tag", "text": "9"}
    frames = []
    for i in range(9):
        png = md._rasterise(md.compose_anim(spec, i / 8.0), 300)
        frames.append(Image.open(io.BytesIO(png)).convert("RGBA"))
    w, h = frames[0].size
    band = (0, int(h * 0.80), w, h)          # legs + feet: body, never arms
    ref = frames[0].crop(band)
    moved = [i for i, f in enumerate(frames[1:], 1)
             if ImageChops.difference(ref, f.crop(band)).getbbox() is not None]
    assert not moved, f"body band shifts at phases {moved} — the rig still moves"


# --------------------------------------------------------------------------- #
# 7: EVERY CHANNEL, not just this one (2026-09-03: the operator found the same
#    wobble on trending — it was a different oscillator in a different file)
# --------------------------------------------------------------------------- #
_RENDER_PATHS = [
    "make_reddit_story.py",            # trending: reddit_story
    "make_explainer_stacked.py",       # stacked explainer
    "make_text_card.py",               # retired format, still importable
    "engines/chart_race.py",           # trending: graph_race
    "shared/themed_bottom.py",         # trending: bottom strip
    "data_learning/footage_hybrid.py", # stock-footage compositor
    "data_learning/studio_render.py",  # data channel master
]


def _sources():
    for rel in _RENDER_PATHS:
        f = _REPO / rel
        if f.exists():
            yield rel, f.read_text()


def test_no_zoompan_in_any_channel():
    """zoompan is a moving crop window. No channel ships one."""
    bad = [f"{rel}:{i}" for rel, src in _sources()
           for i, ln in enumerate(src.splitlines(), 1)
           if "zoompan" in ln.split("#", 1)[0]]
    assert not bad, f"zoompan is back: {bad[:5]}"


def test_no_whole_frame_roll_in_any_channel():
    """np.roll of a finished frame is a shaken camera. Subjects may move; the
    frame may not. (The quake and chase renderers each had one.)"""
    bad = [f"{rel}:{i}" for rel, src in _sources()
           for i, ln in enumerate(src.splitlines(), 1)
           if "np.roll(out" in ln.split("#", 1)[0]]
    assert not bad, f"whole-frame roll is back: {bad[:5]}"


def test_no_periodic_pan_in_any_channel():
    """A crop/overlay/zoompan coordinate driven by sin/cos of time — the shape
    every one of these bugs has had, whichever file it lived in."""
    bad = []
    for rel, src in _sources():
        for i, ln in enumerate(src.splitlines(), 1):
            code = ln.split("#", 1)[0]
            if re.search(r"[xy]\s*=\s*'[^']*\b(sin|cos)\(", code) or \
               re.search(r"(crop|overlay)=[^\n]*\b(sin|cos)\(", code):
                bad.append(f"{rel}:{i}: {ln.strip()[:60]}")
    assert not bad, f"a periodic pan is back: {bad[:5]}"


def test_kenburns_engine_is_retired():
    """engines/still_motion is the canonical Ken Burns. It must refuse, and
    maybe_kenburns must keep the engine contract by returning None."""
    from engines.still_motion import kenburns, maybe_kenburns
    try:
        kenburns("x.png", "o.mp4", 2.0)
        raise AssertionError("kenburns() still renders a camera move")
    except RuntimeError:
        pass
    assert maybe_kenburns("x.png", "o.mp4", 2.0) is None, \
        "maybe_kenburns must return None, not a moving clip"


def test_camera_float_module_stays_retired():
    """main retired shared/camera_float on 2026-08-25. It stays retired."""
    from shared import camera_float as cf
    for name in ("crop_vf", "overlay_xy", "px_per_frame"):
        fn = getattr(cf, name, None)
        if fn is None:
            continue
        try:
            fn(1080, 1920)
            raise AssertionError(f"camera_float.{name} works again")
        except AssertionError:
            raise
        except Exception:
            pass


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
