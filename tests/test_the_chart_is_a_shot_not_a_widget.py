"""The frame has to look like a channel made it, not like a dashboard.

Operator note, 2026-09-10: *"the whole look of the thing is cheap and
shit ... it can look much better"*, and then, after the first pass,
*"closer but it can be even more sharp and clean and more professional
YouTuber looking"*. Everything here is a defect that was visible in a
rendered frame and is now held closed, because each one is the kind that
comes back the moment somebody edits the layout for another reason.
"""
from __future__ import annotations

import ast
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib                                            # noqa: E402
matplotlib.use("Agg")

from data_learning import charts as C                        # noqa: E402
from data_learning.insights import Insight                   # noqa: E402
from data_learning.sources.base import DataPoint, Source     # noqa: E402

SRC = Source(name="S", publisher="P", url="https://x",
             access_date="2026-09-04")


def _insight(kind, items, **kw):
    return Insight(kind=kind, topic="T", main_insight="m",
                   items=[DataPoint(label=a, value=b) for a, b in items],
                   source=SRC, **kw)


def _body(fn):
    """The function's CODE, with every string constant blanked.

    Source-reading tests in this repo have asserted on prose more than once:
    a comment or docstring quoting the code it replaced is not the code.
    """
    tree = ast.parse(inspect.getsource(fn).lstrip())
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            node.value = ""
    return ast.unparse(tree)


class ThereIsNoCard(unittest.TestCase):
    """A bordered panel floating on a gradient is a UI widget, not a shot —
    `repair_planner` has a defect code for it (`UI_WIDGET`)."""

    def test_the_card_patch_is_gone(self):
        src = _body(C._card_base)
        self.assertNotIn("FancyBboxPatch", src)
        self.assertNotIn("CARD_EDGE", src)

    def test_the_figure_is_transparent_so_the_ground_shows_through(self):
        fig, plt = C._card_base()
        try:
            self.assertEqual(fig.patch.get_alpha(), 0.0)
        finally:
            plt.close(fig)


class TheHeadingIsAHierarchy(unittest.TestCase):
    def test_the_kicker_is_above_the_headline(self):
        self.assertGreater(C.KICK_Y, C.HEAD_Y)

    def test_the_chart_ceiling_did_not_move(self):
        """`SUB_Y` is what thirteen composers lay out under. Moving the
        subtitle must not move it, or every chart walks up into the type."""
        self.assertAlmostEqual(C.SUB_Y, 0.845, 3)

    def test_the_headline_is_set_in_the_display_cut(self):
        face = C._display_face()
        self.assertIsNotNone(face, "InterDisplay-Bold is not committed")
        self.assertTrue(Path(face).exists())

    def test_straight_quotes_never_reach_the_frame(self):
        out = C._typeset("NASA's share - the 1990s...")
        self.assertNotIn("'", out)
        self.assertIn("’", out)
        self.assertIn("—", out)
        self.assertIn("…", out)

    def test_the_source_line_hangs_off_the_page_margin(self):
        """Everything else starts at HEAD_X; a centred footer under a
        left-aligned block is the tell that the layout was assembled."""
        src = _body(C._footer)
        self.assertIn("HEAD_X", src)
        self.assertNotIn("0.5", src)


class MarksAreCappedEverywhere(unittest.TestCase):
    """`look.bar_thickness` exists so no composer picks its own number."""

    def test_no_composer_hardcodes_a_bar_thickness(self):
        for name in ("_story_bars", "_story_versus"):
            src = _body(getattr(C, name))
            self.assertNotIn("lw = 165", src, name)

    def test_the_comparison_column_is_a_mark_not_a_wall(self):
        ins = _insight("comparison", [("Then", 588.0), ("Now", 942.0)],
                       unit="usd_billions", highlight_label="Now")
        fig, plt = C._card_base()
        try:
            ax, _ = C._story_versus(fig, plt, ins, "")
            widths = [ln.get_linewidth() for ln in ax.lines]
            self.assertTrue(widths)
            # points -> pixels on the real card
            px = max(widths) * C.SERIES_DPI / 72.0
            self.assertLess(px, 0.20 * C.SERIES_W * C.SERIES_DPI,
                            "a column wider than a fifth of the frame")
        finally:
            plt.close(fig)


class TheAccentFollowsTheStory(unittest.TestCase):
    """It followed the DRAW ORDER, so every comparison whose bigger side is
    drawn second put the channel's one accent on the side the video is not
    about — and then wrote the winner's number in the ink chosen to sit on
    the accent. `$942B` shipped in near-black on a slate column."""

    def _colours(self, items, highlight):
        ins = _insight("comparison", items, unit="usd_billions",
                       highlight_label=highlight)
        fig, plt = C._card_base()
        try:
            ax, _ = C._story_versus(fig, plt, ins, "")
            return [ln.get_color() for ln in ax.lines]
        finally:
            plt.close(fig)

    def test_the_bigger_side_gets_the_accent_whichever_is_drawn_first(self):
        for items in ([("Then", 588.0), ("Now", 942.0)],
                      [("Now", 942.0), ("Then", 588.0)]):
            cols = self._colours(items, "Now")
            self.assertIn(C.HIGHLIGHT, cols, items)

    def test_every_value_is_legible_against_the_ground(self):
        """Both numbers are ink on ground now — no label's legibility may
        depend on which colour its column happened to get."""
        src = _body(C._story_versus)
        self.assertNotIn("CARD", src)


class TheScaleReadsLikeAPersonWroteIt(unittest.TestCase):
    def test_ticks_are_round_numbers(self):
        ticks = C._nice_ticks(221.0, 3924.0)
        self.assertGreaterEqual(len(ticks), 2)
        for t in ticks:
            self.assertEqual(t, round(t), t)
            self.assertAlmostEqual(t % 100, 0, 6, t)

    def test_it_never_falls_back_to_the_raw_endpoints(self):
        for lo, hi in ((221, 3924), (16.1, 18.7), (0.4, 4.4), (3, 7),
                       (1_000_000, 9_400_000)):
            ticks = C._nice_ticks(float(lo), float(hi))
            self.assertGreaterEqual(len(ticks), 2, (lo, hi))
            self.assertNotEqual(ticks, [float(lo), float(hi)], (lo, hi))

    def test_a_flat_series_does_not_explode(self):
        self.assertEqual(len(C._nice_ticks(5.0, 5.0)), 2)


class RoundedBoxesDoNotSmearAcrossTheFrame(unittest.TestCase):
    """`FancyBboxPatch`'s `rounding_size` is in DATA units. On an axes that
    is 0..1 across and 0..100 up, `1.4` is more than the entire axis width —
    every stacked segment threw a pair of faint full-width streaks across the
    card, which is what the banding in the rendered frames actually was."""

    def test_the_stack_uses_plain_rectangles(self):
        src = _body(C._story_stack)
        self.assertNotIn("FancyBboxPatch", src)
        self.assertNotIn("rounding_size", src)

    def test_no_segment_is_drawn_wider_than_its_column(self):
        ins = _insight("share", [("Coal", 35.0), ("Gas", 22.0),
                                 ("Hydro", 14.0), ("Wind", 8.0)],
                       unit="percent", highlight_label="Coal")
        fig, plt = C._card_base()
        try:
            ax, _ = C._story_stack(fig, plt, ins, "")
            for patch in ax.patches:
                x0, x1 = patch.get_extents().x0, patch.get_extents().x1
                ax0, ax1 = ax.get_window_extent().x0, ax.get_window_extent().x1
                self.assertGreaterEqual(x0, ax0 - 1, patch)
                self.assertLessEqual(x1, ax1 + 1, patch)
        finally:
            plt.close(fig)


class HisFeetAreHisFeet(unittest.TestCase):
    """`_bake_host(..., align=(0.5, 0.0))` says "his feet are at this point",
    and that is only true if the bottom of the array is the bottom of the
    character. The SVG canvas is a fixed box he does not fill, so on a rank
    chart he stood a visible 35px ABOVE the bar he is supposed to stand on."""

    def test_the_empty_rows_under_him_are_cropped(self):
        import numpy as np
        img = np.zeros((40, 10, 4))
        img[5:20, 2:8, 3] = 1.0
        out = C._trim_floor(img)
        self.assertEqual(out.shape[0], 20)
        self.assertEqual(out.shape[1], 10, "only the BOTTOM may be trimmed")

    def test_a_fully_transparent_frame_is_returned_untouched(self):
        import numpy as np
        img = np.zeros((12, 4, 4))
        self.assertEqual(C._trim_floor(img).shape, img.shape)

    def test_the_width_is_never_trimmed(self):
        """Cropping to the alpha bounding box would re-centre him every
        frame, and his arms move — a raised arm would shift the whole
        character sideways for one frame and read as jitter."""
        import numpy as np
        img = np.zeros((30, 20, 4))
        img[0:10, 9:11, 3] = 1.0
        self.assertEqual(C._trim_floor(img).shape[1], 20)


class TheRankingFillsItsFrame(unittest.TestCase):
    def _render(self, n):
        ins = _insight("rank", [(f"Row {i}", float(n - i)) for i in range(n)],
                       unit="percent", highlight_label="Row 0")
        fig, plt = C._card_base()
        ax, arts = C._story_bars(fig, plt, ins, "")
        fig.canvas.draw()
        return fig, plt, ax, arts

    def test_the_value_never_overlaps_its_own_bar(self):
        for n in (2, 3, 5):
            fig, plt, ax, arts = self._render(n)
            try:
                r = fig.canvas.get_renderer()
                bar = max(ln.get_window_extent(r).x1 for ln in ax.lines)
                left = min(a[2].get_window_extent(r).x0 for a in arts)
                self.assertGreater(left, bar - 1,
                                   f"n={n}: the number sits on the bar cap")
            finally:
                plt.close(fig)

    def test_every_value_stays_inside_the_card(self):
        for n in (2, 3, 5):
            fig, plt, ax, arts = self._render(n)
            try:
                r = fig.canvas.get_renderer()
                W = fig.get_size_inches()[0] * fig.dpi
                for _v, _k, t, _ in arts:
                    self.assertLessEqual(t.get_window_extent(r).x1 / W,
                                         C.HEAD_RIGHT + 0.005, n)
            finally:
                plt.close(fig)

    def test_the_row_pitch_is_a_constant_until_the_rows_stop_fitting(self):
        """It was `fig.add_axes([..., 0.60])` at ANY row count, so three rows
        sat 300px apart around 110px of content and the bottom third of the
        frame was empty. Pitch is capped by the look, then by the band."""
        seen = []
        for n in (2, 3, 4, 6, 9):
            fig, plt, ax, _ = self._render(n)
            try:
                seen.append(round(float(ax.get_position().height / n), 6))
            finally:
                plt.close(fig)
        self.assertLess(max(seen[:2]) - min(seen[:2]), 1e-6, seen)
        for pitch in seen:
            self.assertLessEqual(pitch, 0.19 + 1e-6, seen)
        # ...and it only ever shrinks as rows are added, never jumps around.
        self.assertEqual(seen, sorted(seen, reverse=True), seen)

    def test_a_long_row_name_starts_at_the_page_margin(self):
        """The gutter that clipped "1966 (Apollo buildup)" to
        "5 (Apollo buildup)" is gone: there are no y-ticks to overflow."""
        fig, plt, ax, _ = self._render(3)
        try:
            self.assertEqual(list(ax.get_yticks()), [])
            self.assertAlmostEqual(ax.get_position().x0, C.HEAD_X, 3)
        finally:
            plt.close(fig)


if __name__ == "__main__":
    unittest.main()
