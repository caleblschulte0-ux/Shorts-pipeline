"""A full-frame picture is measured at the length it PLAYS, not the length it
was probed at.

`coldest-place-in-the-universe-is-human-made` was blocked by the temporal
gate 21 times (duplicate_ratio 0.51-0.53 against 0.45; six of them on
2026-09-28/29, after the gauge and the timeline were fixed). Rendered
offline, the worst held window is 36-48s: the brain's
`earth-orbit-vs-deep-space-flyout`, 0.83-0.92 held.

`mechanic_motion_ok` had passed it. The probe runs when the mechanic is
chosen, before the span is known, and compares ONE adjacent pair at each of
five points of a 7s beat with the reveal un-eased. The render then:

  * eased the reveal with a private `1 - (1 - r)**2`, whose end slope is
    zero (CLAUDE.md: "one easing curve — `viz_scene.settle()`");
  * laid it across a 13.8s span, so every reveal-paced move is half as far
    per frame as the probe saw.

Refusing the mechanic alone was tried and measured WORSE (0.459 -> 0.493):
it fell back to the diorama, which is just as reveal-paced and froze the
same window. So the measurement sits where the fallback chain does —
`charts.render_story_build` — and every full-frame renderer's span is held
to the gate's own ceiling at the length it will play.
"""
from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_learning import charts                             # noqa: E402
from data_learning import viz_scene as vs                    # noqa: E402
from data_learning.quality_milestones import active_phase    # noqa: E402

#: The span the flyout actually played on 2026-09-29 (13.8s at 30fps).
SPAN = 414

#: The brain's mechanic, verbatim from `niche.config.json`. Its two pictures
#: come from `_env` (in CI they were the deterministic Earth and satellite
#: icons — the cutout service was answering 402).
FLYOUT = """\
earth = subject_image('Earth planet photo from space')
iss = subject_image('International Space Station photo')
cx = (RX0 + RX1) // 2
cy = RTOP + 420
er = 140
if earth is not None:
    paste(earth, cx - er, cy - er, er * 2, er * 2)
ang = clamp(reveal) * 6.283
orbit_r = er + 60
ix = cx + orbit_r * math.cos(ang)
iy = cy + orbit_r * math.sin(ang) * 0.4
if iss is not None:
    paste(iss, ix - 40, iy - 30, 80, 60)
t = clamp(reveal)
fx = cx + (940 - cx) * t
fy = cy - 260 * t
d.line([(cx, cy - er - 10), (fx, fy)], fill=rgba(WARN, 200), width=4)
d.ellipse([fx - 8, fy - 8, fx + 8, fy + 8], fill=rgba(WARN, 230))
dist = values[0] * t
text(f'{dist / 1e15:.1f} quadrillion mi', fx, fy - 40, size=22, color=WARN, center=True)
text(labels[0], fx, fy - 68, size=18, color=WARN, center=True)
text(f'{labels[1]}: {int(values[1])} mi away', cx, cy + er + 50, size=26, color=HIGHLIGHT, center=True)
text('RIGHT OVER YOUR HEAD', cx, RTOP + 60, size=30, color=TEXT, center=True)
"""

#: A mark that sweeps the whole frame whatever the span — a chart's pace.
#: (Every mechanic must place a real subject, or `validate_mechanic` refuses
#: it before a frame is drawn.)
SWEEPS = """\
pic = subject_image('a thing')
d.rectangle([0, 0, W, int(20 + reveal * (H - 100))], fill=rgba(TEXT, 255))
if pic is not None:
    paste(pic, RX0, RTOP, 200, 200)
"""


class _Item:
    def __init__(self, label, value):
        self.label, self.value = label, value


class _Ins:
    slug = "t"
    topic = ""                       # no title card: measure the picture
    unit = "miles"

    def __init__(self, code, name, kind="mechanic"):
        self.kind = kind
        self.items = [_Item("Boomerang Nebula", 2.94e16),
                      _Item("NASA's Cold Atom Lab (ISS)", 250.0)]
        self.scene = {"mechanic": name, "concept": "c", "code": code}


def _env():
    from PIL import Image, ImageChops, ImageDraw, ImageOps
    pic = Image.new("RGBA", (96, 96), (90, 160, 230, 255))
    return {"values": [2.94e16, 250.0],
            "labels": ["Boomerang Nebula", "NASA's Cold Atom Lab (ISS)"],
            "vmax": 2.94e16, "n": 2, "images": {},
            "subject_image": lambda *_a, **_k: pic,
            "_Image": Image, "_ImageDraw": ImageDraw,
            "_ImageOps": ImageOps, "_ImageChops": ImageChops}


def _write(out: Path, slug: str, frames: int, y_of):
    """A full-frame renderer's contract: 1080x1920 PNGs + (pattern, [])."""
    from PIL import Image, ImageDraw
    out.mkdir(parents=True, exist_ok=True)
    for f in range(1, frames + 1):
        im = Image.new("RGB", (1080, 1920), (10, 14, 30))
        y = int(y_of(f / frames))
        ImageDraw.Draw(im).rectangle([0, 0, 1080, y], fill=(240, 240, 240))
        im.save(out / f"{slug}_build{f:02d}.png", compress_level=1)
    return str(out / f"{slug}_build%02d.png"), []


def _still(_ins, out, slug, frames):
    return _write(out, slug, frames, lambda r: 600)


def _still_other(_ins, out, slug, frames):
    return _write(out, slug, frames, lambda r: 1200)


def _moving(_ins, out, slug, frames):
    return _write(out, slug, frames, lambda r: 100 + r * 1700)


def _thumb(path):
    """A frame as the reviewer's cadence detector sees it: grey, 192px."""
    from PIL import Image
    im = Image.open(path).convert("L")
    im = im.resize((192, int(im.height * 192 / im.width)))
    return list(getattr(im, "get_flattened_data", im.getdata)())


def _held(paths) -> float:
    """Held share of build frames laid at 30fps, sampled at the reviewer's
    24fps and compared with the reviewer's OWN detector — measured here,
    independently of anything the renderer reports about itself."""
    from scripts.showrunner_review import BLOCK_MOTION_THRESH, _max_block_diff
    n = len(paths)
    idx = [min(n - 1, int(i * 30 / 24)) for i in range(int(n * 24 / 30))]
    th = {i: _thumb(paths[i]) for i in set(idx)}
    held = sum(1 for a, b in zip(idx, idx[1:])
               if _max_block_diff(th[a], th[b], 192) < BLOCK_MOTION_THRESH)
    return held / (len(idx) - 1)


def _build(ins, frames=SPAN, renderers=None, fallback=None):
    out = Path(tempfile.mkdtemp())
    with mock.patch.object(vs, "_mechanic_env", return_value=_env()), \
            mock.patch.dict(charts.FULLFRAME_RENDERERS, renderers or {}), \
            mock.patch.dict(charts.FALLBACK, fallback or {}):
        pattern, _anc = charts.render_story_build(ins, out, "m",
                                                  frames=frames)
    paths = [Path(pattern % f) for f in range(1, frames + 1)]
    return ins.kind, paths


class AFrozenSpanStepsDownTheChain(unittest.TestCase):
    def test_a_still_full_frame_picture_is_not_what_plays(self):
        kind, paths = _build(_Ins("", "x", kind="_t_still"), frames=120,
                             renderers={"_t_still": _still,
                                        "_t_moving": _moving},
                             fallback={"_t_still": "_t_moving"})
        self.assertLessEqual(_held(paths), active_phase().max_duplicate_ratio,
                             "a span that holds still end to end played")
        self.assertEqual(kind, "_t_moving")

    def test_a_moving_full_frame_picture_is_kept(self):
        kind, _paths = _build(_Ins("", "x", kind="_t_moving"), frames=120,
                              renderers={"_t_moving": _moving},
                              fallback={"_t_moving": "_t_still"})
        self.assertEqual(kind, "_t_moving")


def _real_insight(kind):
    """A real `Insight`, so the terminal matplotlib chart really renders."""
    from data_learning.insights import Insight
    from data_learning.sources.base import DataPoint, Source
    src = Source(name="X", publisher="Y", url="https://x",
                 access_date="2026-09-29")
    return Insight(kind=kind, topic="t", main_insight="m",
                   items=[DataPoint(label="Boomerang Nebula", value=2.94e16),
                          DataPoint(label="Cold Atom Lab", value=250.0)],
                   source=src, unit="miles", highlight_label="Cold Atom Lab")


class AStillIsNeverTradedForAnotherStill(unittest.TestCase):
    """Stepping down blindly was measured WORSE on coldest-place: the flyout
    (0.88) fell to a diorama (0.97) and then to one teal bubble clipped into
    a slab. The first picture that froze plays unless something further
    down the chain actually moves."""

    def test_the_story_keeps_its_own_picture_when_nothing_moves(self):
        kind, paths = _build(_real_insight("_t_still"), frames=120,
                             renderers={"_t_still": _still,
                                        "_t_other": _still_other},
                             fallback={"_t_still": "_t_other",
                                       "_t_other": "bubbles"})
        self.assertNotEqual(kind, "_t_other",
                            "one still was traded for a different still")
        if kind == "_t_still":
            self.assertNotIn("step", str(paths[0].parent),
                             "the kept picture's frames were not its own")
            self.assertTrue(all(p.exists() for p in paths))
        else:            # the terminal chart moved: that is what plays
            self.assertLessEqual(_held(paths),
                                 active_phase().max_duplicate_ratio)


class TheFlyoutOverItsRealSpan(unittest.TestCase):
    def test_the_probe_would_have_passed_it(self):
        """The bug's precondition: the choose-time probe says it moves."""
        with mock.patch.object(vs, "_mechanic_env", return_value=_env()):
            self.assertTrue(vs.mechanic_motion_ok(
                {"mechanic": "flyout", "concept": "c", "code": FLYOUT},
                _Ins(FLYOUT, "flyout")))

    def test_what_plays_is_under_the_gates_ceiling(self):
        # the chain's next step is a picture known to move, so what this
        # measures is whether the frozen flyout is the one that PLAYS
        kind, paths = _build(_Ins(FLYOUT, "flyout"),
                             renderers={"_t_moving": _moving},
                             fallback={"mechanic": "_t_moving"})
        held = _held(paths)
        self.assertLessEqual(
            held, active_phase().max_duplicate_ratio,
            f"{kind} played {held:.2f} held over its {SPAN}-frame span — "
            f"over the temporal gate's ceiling on its own")


class AMechanicThatMovesIsKept(unittest.TestCase):
    """Refusing everything would be a channel of charts."""

    @classmethod
    def setUpClass(cls):
        cls.kind, cls.paths = _build(_Ins(SWEEPS, "sweep"),
                                     renderers={"_t_still": _still},
                                     fallback={"mechanic": "_t_still"})

    def test_a_sweep_is_kept_over_a_long_span(self):
        self.assertEqual(self.kind, "mechanic", "a frame-wide sweep refused")

    def test_the_end_of_the_span_still_moves(self):
        """The private ease-out's end slope is zero. The house curve
        (`settle`) keeps 0.72 of it, so the LAST fifth is not a still."""
        self.assertLessEqual(_held(self.paths[-len(self.paths) // 5:]),
                             active_phase().max_duplicate_ratio)


class TheMeasureIsTheReviewers(unittest.TestCase):
    def test_the_ceiling_is_read_not_restated(self):
        self.assertEqual(charts._held_ceiling(),
                         active_phase().max_duplicate_ratio)

    def test_the_build_measures_what_the_reviewer_measures(self):
        """`span_held_ratio` must agree with the reviewer's detector, or the
        refusal is a second opinion about a different question."""
        _kind, paths = _build(_Ins("", "x", kind="_t_moving"), frames=90,
                              renderers={"_t_moving": _moving})
        self.assertAlmostEqual(
            charts.span_held_ratio([_thumb(p) for p in paths]),
            _held(paths), places=6)
        self.assertEqual(
            charts.span_held_ratio([[0] * 1200 for _ in range(60)]), 1.0)


def _names(node):
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


class ARefusedMechanicIsNotTaughtAsOne(unittest.TestCase):
    """The library records a persisted mechanic `moves: True`. One the build
    stepped past as frozen must not be persisted as having drawn — the
    persist call is conditioned on what was BUILT, not what was asked for."""

    def test_persisting_asks_what_was_built(self):
        tree = ast.parse(
            (ROOT / "data_learning" / "studio_render.py").read_text())
        guards = [n.test for n in ast.walk(tree) if isinstance(n, ast.If)
                  and any(isinstance(c, ast.Call)
                          and getattr(c.func, "id", "")
                          == "_persist_rendered_mechanic"
                          for b in n.body for c in ast.walk(b))]
        self.assertTrue(guards, "no guarded persist call found")
        for g in guards:
            self.assertIn("_built", _names(g),
                          "a mechanic is persisted on what was asked for")


if __name__ == "__main__":
    unittest.main()
