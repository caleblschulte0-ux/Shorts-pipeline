"""The bubble scene has to USE the frame, and the numbers have to be there.

2026-08-11. Three of the five explainer stories were blocked by the
showrunner with notes about the same scene:

    "seg0 is a near-empty card with a flat bubble row"
    "tiny bubbles in a mostly empty frame"
    "equal-size blobs that only reveal numbers at the very end"

All three are literally true and all three are measurable. `_story_bubbles`
packed every item into ONE row scaled to fit the WIDTH, inside a card 1.15x
TALLER than it is wide. With five items the row is already 92% of the width,
so the bubbles cannot grow and the rest of the frame stays empty:

    items   ink coverage   frame height used
      5         8.7%            18.5%
      3        16.9%            31.4%
      2        27.7%            46.8%

And `_lblalpha` holds every label at alpha 0 until 80% of the build — right
for a BAR, whose label lands as the bar reaches it, but a bubble's number
sits at the centre of a circle drawn from frame one. On the hook beat, whose
reveal curve does not pass 0.8 until ~71% of a 20-second window, the values
were invisible for fourteen seconds.

    python -m unittest tests.test_bubbles_use_the_frame -v
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
from matplotlib.patches import Circle  # noqa: E402

from data_learning import charts as C  # noqa: E402
from data_learning.insights import Insight  # noqa: E402
from data_learning.sources.base import DataPoint, Source  # noqa: E402

SRC = Source(name="WDI", publisher="World Bank", url="https://example",
             access_date="2026-08-11")

# The actual seg0 data of the 2026-08-11 macao story.
MACAO = [("Macao", 20570), ("Monaco", 18500), ("Singapore", 8400),
         ("Hong Kong", 6800), ("Gibraltar", 3400)]


class BubbleCase(unittest.TestCase):
    def scene(self, vals, reveal=1.0):
        items = [DataPoint(label=l, value=v) for l, v in vals]
        ins = Insight(kind="bubbles", topic="People per sq km",
                      main_insight="Macao is the densest place on Earth",
                      items=items, source=SRC, unit="count",
                      highlight_label=vals[0][0])
        fig, plt = C._card_base()
        ax, _specs = C._story_bubbles(fig, plt, ins, "tops the list", reveal)
        fig.canvas.draw()
        self.fig, self.plt, self.ax = fig, plt, ax
        return ax

    def tearDown(self):
        if getattr(self, "fig", None) is not None:
            self.plt.close(self.fig)
            self.fig = None

    def circles(self):
        return [p for p in self.ax.patches if isinstance(p, Circle)]

    def geometry(self):
        cs = self.circles()
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        rs = [c.get_radius() for c in cs]
        ys = [c.center[1] for c in cs]
        top = max(y + r for y, r in zip(ys, rs))
        bot = min(y - r for y, r in zip(ys, rs))
        return {
            "ink": sum(math.pi * r * r for r in rs) / ((x1 - x0) * (y1 - y0)),
            "vfill": (top - bot) / (y1 - y0),
            "r_max": max(rs),
            "inside": (all(c.center[0] - r >= x0 - 0.5
                           and c.center[0] + r <= x1 + 0.5
                           for c, r in zip(cs, rs))
                       and bot >= y0 - 0.5 and top <= y1 + 0.5),
        }


class TestItFillsTheFrame(BubbleCase):

    def test_the_macao_scene_is_no_longer_a_thin_strip(self):
        """8.7% ink over 18.5% of the height was the shipped state."""
        self.scene(MACAO)
        g = self.geometry()
        self.assertGreater(g["ink"], 0.15,
                           f"ink {g['ink']:.3f} — still a near-empty card")
        self.assertGreater(g["vfill"], 0.40,
                           f"height used {g['vfill']:.3f} — still a flat row")

    def test_five_near_identical_values_still_fill_it(self):
        """Equal values are the worst case for a width-scaled row: every
        bubble is the same small size and nothing grows."""
        self.scene([("A", 100), ("B", 98), ("C", 96), ("D", 95), ("E", 94)])
        self.assertGreater(self.geometry()["ink"], 0.15)

    def test_four_items_too(self):
        self.scene([("A", 100), ("B", 70), ("C", 50), ("D", 20)])
        g = self.geometry()
        self.assertGreater(g["ink"], 0.25)
        self.assertGreater(g["vfill"], 0.60)

    def test_nothing_leaves_the_axes(self):
        for vals in (MACAO, [("A", 100), ("B", 70), ("C", 50), ("D", 20)],
                     [("A", 100), ("B", 40)], [("Only", 5)]):
            self.scene(vals)
            self.assertTrue(self.geometry()["inside"],
                            f"a bubble escapes the axes for n={len(vals)}")
            self.tearDown()


class TestSmallCountsAreUntouched(BubbleCase):
    """The complaint was about 4+ items in one row. Two and three items
    already used a reasonable share of the frame and their layout is
    unchanged — a fix that quietly re-cuts the scenes that were FINE is the
    thing CLAUDE.md warns about. These are the pre-change numbers."""

    def test_two_items_keep_their_exact_geometry(self):
        self.scene([("A", 100), ("B", 40)])
        g = self.geometry()
        self.assertAlmostEqual(g["ink"], 0.277, places=2)
        self.assertAlmostEqual(g["r_max"], 27.0, places=0)

    def test_three_items_keep_their_exact_geometry(self):
        self.scene([("A", 100), ("B", 60), ("C", 30)])
        g = self.geometry()
        self.assertAlmostEqual(g["ink"], 0.169, places=2)
        self.assertAlmostEqual(g["r_max"], 18.1, places=0)

    def test_three_items_stay_on_one_row(self):
        self.scene([("A", 100), ("B", 60), ("C", 30)])
        ys = {round(c.center[1], 3) for c in self.circles()}
        self.assertEqual(len(ys), 1)

    def test_five_items_use_two(self):
        self.scene(MACAO)
        ys = {round(c.center[1], 3) for c in self.circles()}
        self.assertEqual(len(ys), 2)


class TestLabelsStayClear(BubbleCase):
    """A second row puts the top row's labels where the bottom row's circles
    are. Trading an empty frame for a collided one is not an improvement."""

    def overlaps(self):
        r = self.fig.canvas.get_renderer()
        inv = self.ax.transData.inverted()
        worst = 0.0
        for t in [x for x in self.ax.texts if x.get_va() == "top"]:
            bb = t.get_window_extent(r).transformed(inv)
            for c in self.circles():
                cx, cy = c.center
                nx = max(bb.x0, min(cx, bb.x1))
                ny = max(bb.y0, min(cy, bb.y1))
                worst = max(worst, c.get_radius() - math.hypot(cx - nx,
                                                              cy - ny))
        return worst

    def test_no_label_lands_on_a_bubble(self):
        for vals in (MACAO,
                     [("Alpha", 100), ("Bravo", 70), ("Charlie", 50),
                      ("Delta", 20)],
                     [("A", 100), ("B", 98), ("C", 96), ("D", 95),
                      ("E", 94)]):
            self.scene(vals)
            self.assertLessEqual(self.overlaps(), 0.0,
                                 f"label collides with a bubble, n={len(vals)}")
            self.tearDown()


class TestTheNumbersAreVisibleEarly(BubbleCase):
    """`_lblalpha` is right for a bar and wrong for a bubble."""

    def alphas(self, reveal):
        self.scene(MACAO, reveal=reveal)
        a = [t.get_alpha() for t in self.ax.texts]
        self.tearDown()
        return a

    def test_a_third_of_the_way_in_the_numbers_are_fully_there(self):
        self.assertTrue(all(a == 1.0 for a in self.alphas(0.33)))

    def test_the_global_ladder_would_still_be_hiding_them(self):
        """Pin the defect so the fix is measured against the real thing."""
        self.assertEqual(C._lblalpha(0.33), 0.0)
        self.assertEqual(C._lblalpha(0.7), 0.0)

    def test_they_are_not_simply_on_from_frame_zero(self):
        """They should ride the inflation, not ignore it."""
        self.assertTrue(all(a < 1.0 for a in self.alphas(0.05)))

    def test_bars_keep_the_landing_behaviour(self):
        """The global ramp exists for a reason and is not what changed."""
        src = (ROOT / "data_learning" / "charts.py").read_text()
        bars = src.split("def _story_bars(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("_lblalpha(", bars)


if __name__ == "__main__":
    unittest.main()
