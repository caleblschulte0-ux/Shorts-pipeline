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

    #: `_story_versus` draws its two columns at these axes x positions.
    COLS = (0.28, 0.72)

    def _grip(self, pairs):
        """Where the host was actually attached, in axes x."""
        ins = _ins(pairs)
        fig, plt = charts._card_base()
        try:
            charts._ATTACH_FRAME.clear()
            charts._story_versus(fig, plt, ins, "")
            self.assertTrue(charts._ATTACH_FRAME, "the host was never baked")
            return charts._ATTACH_FRAME[-1]["x"]
        finally:
            plt.close(fig)

    def test_the_host_is_baked_on_the_taller_column(self):
        """MEASURED, not read out of the source.

        This asserted three substrings of `_story_versus`, one of which
        (`if j == win:`) was a branch that only existed because the winner's
        number used to be drawn INSIDE its column. Deleting that branch —
        a fix, not a regression — failed a test whose name is about where
        the host stands. Assert where the host stands.
        """
        # A dated pair is normalised CHRONOLOGICALLY (the winner is drawn
        # second); two PLACES are normalised BY SIZE (the winner is drawn
        # first). Both orders are real, and the host has to find the taller
        # column in each — which is the whole reason `win` exists.
        for pairs, winner in (([("1963", 417.0), ("2020", 71467.0)], 1),
                              ([("Mississippi", 52.7),
                                ("Massachusetts", 96.5)], 0)):
            x = self._grip(pairs)
            near = min(range(2), key=lambda i: abs(x - self.COLS[i]))
            self.assertEqual(near, winner,
                             f"host at {x:.3f}, expected the {winner} column")

    def test_the_accent_is_on_the_taller_column_too(self):
        """It followed the DRAW ORDER, so any comparison whose bigger side is
        drawn second put the channel's one accent on the wrong side."""
        for pairs in ([("1963", 417.0), ("2020", 71467.0)],
                      [("Mississippi", 52.7), ("Massachusetts", 96.5)]):
            ins = _ins(pairs)
            fig, plt = charts._card_base()
            try:
                ax, _ = charts._story_versus(fig, plt, ins, "")
                lines = [ln for ln in ax.lines
                         if ln.get_linewidth() > 20]
                self.assertTrue(lines)
                tallest = max(lines, key=lambda ln: max(ln.get_ydata()))
                self.assertEqual(tallest.get_color(), charts.HIGHLIGHT, pairs)
            finally:
                plt.close(fig)


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

    #: The two long labels the reviewer was reading when they reported
    #: "axis labels truncated mid-word ('1963 (all', '2006 (yea')". Drawn at
    #: their nominal 28pt these run from x=121 to x=1090 of a 1100px card —
    #: ten pixels from the edge of the FRAME, through the card's own margin.
    LONG = [("1963 (all-time low)", 417.0),
            ("2006 (year before delisting)", 9789.0)]

    def _label_boxes(self, pairs):
        """The two column names, MEASURED as rendered, as (x0, x1) fractions.

        This used to scan the pixels of a horizontal band for ink in one of
        the two SERIES colours. Both halves of that stopped being true in the
        same change: the labels wear INK now (`shared/palette` has always
        said they must), and the band moved when the y limits did. It failed
        as "no x labels were drawn at all" — a passing chart reported as a
        missing one, which is the worst way for a test to be wrong. The Text
        artists are right there and they measure exactly.
        """
        ins = _ins(pairs)
        fig, plt = charts._card_base()
        try:
            ax, _ = charts._story_versus(fig, plt, ins, "")
            fig.canvas.draw()
            r = fig.canvas.get_renderer()
            W = fig.get_size_inches()[0] * fig.dpi
            names = {p.label for p in ins.items}
            out = []
            for t in ax.texts:
                if t.get_text() in names:
                    bb = t.get_window_extent(r)
                    out.append((bb.x0 / W, bb.x1 / W))
            return sorted(out)
        finally:
            plt.close(fig)

    def test_a_long_axis_label_stays_ON_the_card(self):
        boxes = self._label_boxes(self.LONG)
        self.assertEqual(len(boxes), 2, "no x labels were drawn at all")
        self.assertGreaterEqual(boxes[0][0], self.CARD[0], "label off the left")
        self.assertLessEqual(boxes[-1][1], self.CARD[1], "label off the right")

    def test_the_two_axis_labels_do_not_touch(self):
        boxes = self._label_boxes(self.LONG)
        self.assertEqual(len(boxes), 2)
        self.assertGreater(boxes[1][0] - boxes[0][1], 0.02,
                           "the two axis labels run into each other")


if __name__ == "__main__":
    unittest.main()
