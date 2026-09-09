"""THE NEEDLE POINTED AT 74% OF THE SWEEP FOR EVERY NUMBER IN THE WORLD.

`draw_gauge` set its full-scale value to `abs(v) * 1.35`. That is not a
scale — it is the reading itself, scaled — so 51,863 and 3 and 0.02 all put
the needle in exactly the same place. The arc carried no information at all,
and the picture was a number with a ring behind it.

`bare_number_card` is an auto-fail and it took 41 of this channel's 228
recorded verdicts. The showrunner read the defect off the screen without ever
seeing the code:

    "a giant '51,863' on an empty dark field with a decorative unlabeled arc"
                                        melatonin-kids-er-surge, 2026-09-06
    "a giant numeral over a dark field with a decorative ring and nothing
     else — the number is the beat, not a demonstration of it"
    "seg1:mid and seg1:end are a giant '14.8%' / '21.7%' counter on an empty
     gradient — the gauge arc it should be filling is zoomed almost entirely
     off-frame"                        four-day-workweek-spreads, 2026-09-07

A dial is one of the few machines that CANNOT be improvised. A needle means
something only against a full scale that is really there, so:

  * an explicit baseline or limit IS the scale;
  * failing that, a percentage is out of 100;
  * failing that there is no scale, and the honest answer is to decline the
    beat. A raw count has no ceiling, and inventing one is the same class of
    lie as "2019 IS 9% OF THE WHOLE" — which this channel actually shipped.

Runs standalone:  python3 tests/test_a_dial_needs_a_scale.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from PIL import Image, ImageDraw                          # noqa: E402
from data_learning import charts, viz_scene as vs         # noqa: E402
from data_learning.insights import Insight                # noqa: E402
from data_learning.sources.base import DataPoint, Source  # noqa: E402

BOX = (vs.RX0, vs.RTOP, vs.RX1, vs.MACHINE_BOT)
SRC = Source(name="X", publisher="Y", url="https://x", access_date="2026-09-09")


def mk(pairs, unit, base=None):
    i = Insight(kind="scene", topic="t", main_insight="m",
                items=[DataPoint(label=a, value=float(b)) for a, b in pairs],
                source=SRC, unit=unit, highlight_label=pairs[0][0])
    if base:
        i.baseline = DataPoint(label=base[0], value=float(base[1]))
    return i


class AScaleThatIsREALLYThere(unittest.TestCase):
    def test_a_percentage_is_out_of_a_hundred(self):
        ins = mk([("Rate", 22.9)], "percent")
        self.assertEqual(vs.gauge_full_scale(ins, 22.9, "percent"), 100.0)

    def test_a_baseline_is_the_scale(self):
        ins = mk([("Now", 760)], "count", base=("Capacity", 1000))
        self.assertEqual(vs.gauge_full_scale(ins, 760.0, "count"), 1000.0)

    def test_a_raw_count_has_no_ceiling_so_it_is_REFUSED(self):
        ins = mk([("ER visits", 51863)], "count")
        self.assertIsNone(vs.gauge_full_scale(ins, 51863.0, "count"))

    def test_a_percentage_over_a_hundred_is_refused_not_clipped(self):
        """A "140%" is a ratio wearing a percent sign, and pinning it to a
        100 dial would draw it as full and stop."""
        ins = mk([("X", 140)], "percent")
        self.assertIsNone(vs.gauge_full_scale(ins, 140.0, "percent"))

    def test_a_baseline_BELOW_the_reading_is_not_a_scale(self):
        """The needle would run off the end of its own dial."""
        ins = mk([("Now", 1800)], "count", base=("Target", 1000))
        self.assertIsNone(vs.gauge_full_scale(ins, 1800.0, "count"))


class THENEEDLEMovesWithTheNumber(unittest.TestCase):
    """The regression oracle. Under the old rule these three renders were
    pixel-identical apart from the printed figure."""

    def _needle(self, value):
        ins = mk([("Rate", value)], "percent")
        img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
        got = vs.draw_gauge(ImageDraw.Draw(img), img, BOX, ins,
                            charts.HIGHLIGHT, 1.0, "percent")
        self.assertIsNotNone(got, value)
        return got[2], got[3]          # the needle tip

    def test_three_readings_put_the_needle_in_three_places(self):
        tips = [self._needle(v) for v in (8.0, 45.0, 92.0)]
        self.assertEqual(len(set(tips)), 3, f"needle did not move: {tips}")

    def test_a_bigger_number_reads_further_round_the_dial(self):
        xs = [self._needle(v)[0] for v in (8.0, 45.0, 92.0)]
        self.assertEqual(xs, sorted(xs), f"the dial is not monotonic: {xs}")


class TheARCIsLabelled(unittest.TestCase):
    """"a decorative unlabeled arc" was literally true: no ends, no ticks."""

    def test_both_ends_of_the_scale_are_printed(self):
        import inspect
        src = inspect.getsource(vs.draw_gauge)
        self.assertIn("_ulabel(_val, unit", src)
        self.assertIn("(0.0, 0.0,", src)
        self.assertIn("(1.0, vmax,", src)

    def test_there_are_tick_marks_at_the_quarters(self):
        import inspect
        src = inspect.getsource(vs.draw_gauge)
        self.assertIn("(0.0, 0.25, 0.5, 0.75, 1.0)", src)

    def test_the_full_scale_value_is_never_derived_from_the_reading(self):
        """The whole bug in one line. If the scale is computed FROM the reading
        again the arc goes straight back to being decoration.

        Asserted against the executable code with comments and docstrings
        stripped: both functions quote the old formula in their prose on
        purpose, and a test that cannot tell an explanation from a statement
        is a proximity check wearing a semantic one's clothes."""
        import ast
        import inspect
        for fn in (vs.draw_gauge, vs.gauge_full_scale):
            tree = ast.parse(inspect.getsource(fn).lstrip())
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(
                        node.value, str):
                    node.value = ""
            code = ast.unparse(tree)
            self.assertNotIn("1.35", code, fn.__name__)
        self.assertIn("vmax = gauge_full_scale(",
                      inspect.getsource(vs.draw_gauge))


class TheBuilderRefusesWhatTheDrawingRefuses(unittest.TestCase):
    """`docs/DATA_MACHINES.md`: a builder that accepts what its own draw
    function declines hands the beat a token, fails validation at render time
    and degrades to a chart — a slot spent, no variety, and nothing anywhere
    saying why."""

    def test_the_builder_declines_a_raw_count(self):
        self.assertEqual(vs.gauge_scene(mk([("ER visits", 51863)], "count")),
                         {})

    def test_the_builder_accepts_a_percentage(self):
        self.assertTrue(vs.gauge_scene(mk([("Rate", 22.9)], "percent")))

    def test_builder_and_drawing_agree_across_the_catalogue(self):
        cases = [
            mk([("Rate", 22.9)], "percent"),
            mk([("ER visits", 51863)], "count"),
            mk([("Now", 760)], "count", base=("Capacity", 1000)),
            mk([("X", 140)], "percent"),
            mk([("Share", 61.2)], "%"),
            mk([("Cost", 4200)], "usd"),
        ]
        for ins in cases:
            built = bool(vs.gauge_scene(ins))
            img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            drew = vs.draw_gauge(ImageDraw.Draw(img), img, BOX, ins,
                                 charts.HIGHLIGHT, 1.0,
                                 ins.unit) is not None
            self.assertEqual(built, drew,
                             f"builder {built} vs drawing {drew} for "
                             f"{ins.items[0].label} {ins.unit}")


if __name__ == "__main__":
    unittest.main()
