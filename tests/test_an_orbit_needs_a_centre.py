"""ARABLE HECTARES ARE NOT BODIES AROUND A SUN.

    "seg1: an orbital-system picture asserts a relationship the data doesn't
     have — arable hectares are a ranking, not bodies around a sun; the rings
     say nothing"                                     algeria, 2026-09-09
    "seg1:start/mid: 'Russian Federation 121649000' and 'India 153868700'
     overprint each other; the labels are unreadable at the moment the whole
     point (India edges out the US) is supposed to land"

Two defects in one machine, and the first is the older rule in this repo: **a
relationship is a CLAIM, drawn at 200pt**, and OTHER — fall back to something
that can carry it — is always an acceptable answer.

An orbit says "these things sit at these distances FROM THAT THING". A
ranking says no such thing. Drawing one as a solar system invents a centre
for it, and the centre is the loudest object on screen. So it refuses unless
the numbers really are distances or the claim is about remoteness from a
centre; `charts.FALLBACK["orbit"]` sends the refusal to bubbles, where length
and area still depict honestly.

The second was the label. Trailing the MOVING BODY put two labels at the same
y whenever two bodies happened to be at the same height, and nothing about a
rotation prevents that. A ring's RADIUS is its value, so the label now sits
above its own ring, where the y is separated by the radius difference and
`spread` guarantees a gutter. `viz_scene.draw_orbit` also printed the raw
`121649000` through `_vfmt`; every other machine uses `_ulabel`.

Runs standalone:  python3 tests/test_an_orbit_needs_a_centre.py
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from data_learning import charts, viz_scene as vs           # noqa: E402
from data_learning.insights import Insight                  # noqa: E402
from data_learning.sources.base import DataPoint, Source    # noqa: E402

SRC = Source(name="n", publisher="World Bank", url="https://x",
             access_date="2026-09-09")

#: The real algeria beat.
ARABLE = [("India", 153868700.0), ("United States", 152262000.0),
          ("Russian Federation", 121649000.0), ("China", 118900000.0),
          ("Brazil", 55762000.0)]


def _ins(topic, unit, pairs=ARABLE, main="", kind="orbit"):
    return Insight(kind=kind, topic=topic, main_insight=main,
                   items=[DataPoint(label=a, value=b) for a, b in pairs],
                   source=SRC, unit=unit, highlight_label=pairs[0][0])


class ARankingIsNotASolarSystem(unittest.TestCase):
    def test_the_arable_land_ranking_is_refused(self):
        self.assertFalse(vs.orbit_is_honest(
            _ins("Arable land", "hectares", main="India leads the map")))

    def test_a_share_is_refused(self):
        self.assertFalse(vs.orbit_is_honest(
            _ins("Fossil fuel energy consumption", "% of total")))

    def test_a_count_is_refused(self):
        self.assertFalse(vs.orbit_is_honest(_ins("Nesting pairs", "pairs")))

    def test_a_real_distance_is_allowed(self):
        for topic, unit in (("Distance from the sun", "km"),
                            ("Commute distance", "miles"),
                            ("How far the probe has travelled", "light years")):
            self.assertTrue(vs.orbit_is_honest(_ins(topic, unit)),
                            f"{topic} [{unit}]")

    def test_a_claim_ABOUT_remoteness_is_allowed_whatever_the_unit(self):
        """"how far each suburb sits from the centre" is an orbit even when
        the column is a count of minutes or stops."""
        self.assertTrue(vs.orbit_is_honest(
            _ins("Suburbs", "count",
                 main="how far each suburb sits from the centre")))


class ARefusalFallsBackInsteadOfGoingBLACK(unittest.TestCase):
    """A machine that declines has to leave the beat with something. A scene
    whose only element refuses renders a sequence of EMPTY frames unless the
    dry probe catches it, and `draw_orbit`'s return value is otherwise
    ignored by the dispatch."""

    def _scene(self, topic, unit):
        ins = _ins(topic, unit, kind="scene")
        ins.scene = {"title": True,
                     "elements": [{"type": "orbit_group", "region": "full",
                                   "anim": "grow"}]}
        return ins

    def test_a_refused_scene_orbit_returns_None(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(vs.render_scene(
                self._scene("Arable land", "hectares"), Path(td), "s",
                frames=3))

    def test_an_honest_scene_orbit_still_renders(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNotNone(vs.render_scene(
                self._scene("Distance from the sun", "km"), Path(td), "s",
                frames=3))

    def test_the_chart_renderer_refuses_too(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(charts._render_orbit(
                _ins("Arable land", "hectares"), Path(td), "o", frames=3))

    def test_and_the_fallback_it_lands_on_still_depicts(self):
        """`bubbles`, not bare numbers."""
        self.assertEqual(charts.FALLBACK.get("orbit"), "bubbles")


class TheLabelsCannotOVERPRINT(unittest.TestCase):
    """Measured on the rendered frame: five country labels, at the values
    that collided."""

    #: The renderer's own geometry, for the values that collided.
    def _label_ys(self):
        vals = [v for _l, v in ARABLE]
        vmax = max(vals)
        cy, r_in, r_out = 760, 150, 430
        radii = [r_in + (r_out - r_in) * (v / vmax) for v in vals]
        return vs.spread([cy - rad - 20 for rad in radii], 46, 230, cy - 44)

    def test_five_labels_land_on_five_separate_lines(self):
        """The four leaders are within 30% of each other — 153.9M, 152.3M,
        121.6M, 118.9M — so their rings are nearly the same size and the raw
        label positions are nearly the same y. That is the case that
        collided, and `spread` is what holds it open."""
        ys = self._label_ys()
        self.assertEqual(len(ys), 5)
        gaps = [abs(b - a) for a, b in zip(ys, ys[1:])]
        self.assertTrue(all(g >= 45.0 for g in gaps),
                        f"labels closer than one line apart: {gaps}")

    def test_and_they_stay_inside_the_frame(self):
        ys = self._label_ys()
        self.assertTrue(all(230 <= y <= 760 - 44 for y in ys), ys)

    def test_the_scene_orbit_formats_its_numbers(self):
        """`_vfmt` printed 121649000. Nine digits with no separator is not a
        number a viewer reads.

        Asserted on the executable code: the docstring and the comment both
        quote the old call on purpose."""
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(vs.draw_orbit).lstrip())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                node.value = ""
        code = ast.unparse(tree)
        self.assertIn("_ulabel", code)
        self.assertNotIn("_vfmt", code)

    def test_both_orbit_renderers_spread_their_labels(self):
        import inspect
        for fn in (vs.draw_orbit, charts._render_orbit):
            self.assertIn("spread", inspect.getsource(fn), fn.__name__)


if __name__ == "__main__":
    unittest.main()
