"""THE COMEBACK WAS DRAWN AS A COLLAPSE.

`bald-eagle-population-rebound`, 2026-09-09, on the closing beat — the
punchline of the video:

    "the closing chart runs 2020 -> 1963 left-to-right, so the line falls
     steeply as the narration says 'one of the biggest wildlife comebacks' —
     the picture contradicts the words at the punchline"

417 nesting pairs in 1963, 71,467 in 2020. It is the biggest recovery story
the channel has, and `insights._comparison` sorted the pair by MAGNITUDE
before handing it to `_story_versus`, which draws `items[0]` on the left. Two
PLACES may be ordered by size. Two DATES may not — that is a before-and-after,
and reversing it inverts the claim.

The same render carried two more of the reviewer's standing complaints, and
both turned out to be one unaccounted-for number.

**The bar's round cap overshoots the value.** `solid_capstyle="round"` on a
165pt line puts half a linewidth of ink ABOVE the datum — a tenth of the axes
height — so the tallest column was drawn across the subtitle band:

    "MASSACH[        ] VS MISSISSIPPI"

which reads as the mascot occluding text and is not the mascot at all.
`_clamp_host` has kept HIM below `SUB_Y` since 2026-08-22; the bar had no such
rule.

**And the chart path had no text fitting at all.** Every long label was drawn
at its nominal size and simply overlapped whatever was beside it:

    "'1969-1972 (Apollo era)' and '1973-2024 (since)' print over each other
     AND on top of the subtitle; all three are unreadable"
    "axis labels truncated mid-word ('1963 (all', '2006 (yea')"

`viz_scene` got `fit_text` on 2026-09-09; `charts` is the other half of the
same render and got nothing.

Runs standalone:  python3 tests/test_the_chart_reads_left_to_right.py
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

from data_learning import charts                          # noqa: E402
from data_learning.insights import _comparison, _leading_year  # noqa: E402
from data_learning.sources.base import DataPoint, Source   # noqa: E402


class _DS:
    title = "Bald eagle nesting pairs"
    unit = "pairs"
    source = Source(name="n", publisher="USFWS", url="https://x",
                    access_date="2026-09-09")


def _ins(pairs):
    return _comparison(_DS(), [DataPoint(label=a, value=float(b))
                               for a, b in pairs], None)


class TimeRunsLeftToRight(unittest.TestCase):
    def test_the_eagle_comeback_rises(self):
        ins = _ins([("1963", 417), ("2020", 71467)])
        self.assertEqual([p.label for p in ins.items], ["1963", "2020"])

    def test_a_fall_still_falls(self):
        """Chronological, not 'always rising' — the order is TIME."""
        ins = _ins([("1990 (pre-vaccine)", 4000), ("2019 (two-dose era)", 100)])
        self.assertEqual([p.label for p in ins.items],
                         ["1990 (pre-vaccine)", "2019 (two-dose era)"])

    def test_two_PLACES_are_still_ordered_by_size(self):
        ins = _ins([("Mississippi", 52.7), ("Massachusetts", 96.5)])
        self.assertEqual([p.label for p in ins.items],
                         ["Massachusetts", "Mississippi"])

    def test_a_year_is_read_through_whatever_follows_it(self):
        self.assertEqual(_leading_year("1963 (all-time low)"), 1963)
        self.assertEqual(_leading_year("2006 (year before delisting)"), 2006)
        self.assertEqual(_leading_year("2020"), 2020)

    def test_a_number_that_is_not_a_year_is_not_a_year(self):
        for lab in ("417 pairs", "12", "", None, "Massachusetts", "3000000"):
            self.assertIsNone(_leading_year(lab), lab)

    def test_the_highlight_stays_on_the_bigger_number(self):
        """Reordering must not move the claim onto the smaller bar."""
        ins = _ins([("1963", 417), ("2020", 71467)])
        self.assertEqual(ins.highlight_label, "2020")


class TheWinningColumnCarriesTheHOST(unittest.TestCase):
    """Draw order and 'which one won' were the same thing while items arrived
    sorted by magnitude. They are not any more, and pinning the host to
    `items[0]` would hang him off the smaller bar."""

    def test_the_host_is_baked_on_the_taller_column(self):
        import inspect
        src = inspect.getsource(charts._story_versus)
        self.assertIn("win = 0 if left.value >= right.value else 1", src)
        self.assertIn("_bake_host(ax, xs[win]", src)
        self.assertIn("if j == win:", src)


class TheFitterShrinksBeforeItCollides(unittest.TestCase):
    def test_a_long_label_gets_a_smaller_size(self):
        big = charts._fit_fontsize("1963", 300.0, 28)
        small = charts._fit_fontsize("1969-1972 (Apollo era)", 300.0, 28)
        self.assertEqual(big, 28)
        self.assertLess(small, 28)

    def test_it_is_monotonic_in_length(self):
        prev = 99
        for n in (2, 6, 12, 24, 48):
            size = charts._fit_fontsize("x" * n, 300.0, 28)
            self.assertLessEqual(size, prev)
            prev = size

    def test_it_never_goes_below_a_readable_floor(self):
        self.assertGreaterEqual(charts._fit_fontsize("x" * 400, 100.0, 28), 14)


class MEASUREDOnTheRenderedCard(unittest.TestCase):
    """The arithmetic above is only as good as what comes out of matplotlib."""

    #: A run this long can only be a COLUMN. The bars are 165pt wide and a
    #: glyph stroke is a few pixels, so matching on the bar's own colour and
    #: then on run length separates them cleanly — matching bare alpha finds
    #: the rounded card behind everything and measures nothing.
    RUN = 60

    def _card(self, pairs):
        import numpy as np
        from PIL import Image
        ins = _ins(pairs)
        with tempfile.TemporaryDirectory() as td:
            p, _ = charts.render_story_chart(ins, Path(td) / "c.png")
            self.assertIsNotNone(p)
            return np.asarray(Image.open(p).convert("RGBA"), dtype="int16")

    def _bar_mask(self, arr):
        """Pixels drawn in either series colour, at full opacity."""
        import numpy as np
        out = np.zeros(arr.shape[:2], dtype=bool)
        for hexcol in (charts.HIGHLIGHT, charts.ACCENT):
            c = [int(hexcol[i:i + 2], 16) for i in (1, 3, 5)]
            near = (np.abs(arr[:, :, 0] - c[0]) < 18) & \
                   (np.abs(arr[:, :, 1] - c[1]) < 18) & \
                   (np.abs(arr[:, :, 2] - c[2]) < 18) & (arr[:, :, 3] > 200)
            out |= near
        return out

    def _top_bar_row(self, arr):
        lit = self._bar_mask(arr)
        for r in range(lit.shape[0]):
            best = run = 0
            for v in lit[r]:
                run = run + 1 if v else 0
                best = max(best, run)
            if best >= self.RUN:
                return r
        return lit.shape[0]

    def test_no_bar_reaches_the_subtitle_band(self):
        arr = self._card([("Mississippi", 52.7), ("Massachusetts", 96.5)])
        h = arr.shape[0]
        top = self._top_bar_row(arr)
        sub_row = int((1.0 - charts.SUB_Y) * h)
        self.assertGreater(
            top, sub_row,
            f"a bar's cap reaches row {top}, above the subtitle at {sub_row}")

    #: The card is inset from the frame; ink outside this is off the card.
    CARD = (0.03, 0.97)

    def _label_ink(self, arr):
        """First and last column of series-coloured ink in the x-label band,
        and the widest gutter between the two blocks."""
        import numpy as np
        h = arr.shape[0]
        lit = self._bar_mask(arr)
        cols = lit[int(0.845 * h):int(0.885 * h), :].any(axis=0)
        xs = np.nonzero(cols)[0]
        if not len(xs):
            return None
        d = np.diff(xs)
        return int(xs[0]), int(xs[-1]), int(d.max() - 1) if len(d) else 0

    def test_a_long_axis_label_stays_ON_the_card(self):
        """The real eagle labels, which is what the reviewer was reading:

            "axis labels truncated mid-word ('1963 (all', '2006 (yea')"

        Drawn at their nominal 28pt these two run from x=121 to x=1090 of a
        1100px card — ten pixels from the edge of the FRAME, straight through
        the card's own margin. Fitted they land at 180..916.
        """
        arr = self._card([("1963 (all-time low)", 417.0),
                          ("2006 (year before delisting)", 9789.0)])
        w = arr.shape[1]
        ink = self._label_ink(arr)
        self.assertIsNotNone(ink, "no x labels were drawn at all")
        lo, hi, _ = ink
        self.assertGreaterEqual(lo, self.CARD[0] * w, "label off the left")
        self.assertLessEqual(hi, self.CARD[1] * w, "label off the right")

    def test_the_two_axis_labels_do_not_touch(self):
        arr = self._card([("1963 (all-time low)", 417.0),
                          ("2006 (year before delisting)", 9789.0)])
        w = arr.shape[1]
        ink = self._label_ink(arr)
        self.assertIsNotNone(ink)
        self.assertGreater(ink[2], w * 0.02,
                           "the two axis labels run into each other")


if __name__ == "__main__":
    unittest.main()
