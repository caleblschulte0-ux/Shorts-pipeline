"""The four graph_races the showrunner blocked on 2026-09-10, held closed.

`state/production_runs/20260910/trending.json`:

    expected 6, uploaded 2, failed 8
    failed_by_stage:  {showrunner_block: 4, infra_error: 4}
    failed_by_format: {graph_race: 4, unknown: 4}

Every one of the four was a `graph_race`, and between them they named three
auto-fails. This file is one test per named defect, because the defects were
not subtle and not new — they were the SAME defects `data_learning/charts.py`
had been fixed for hours earlier, in a renderer nobody checked. `graph_race`
goes `make_graph_race.py` -> `engines/chart_race.py`, and that file imported
`shared.fit_title` and nothing else from the design system.
"""
from __future__ import annotations

import ast
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib                                            # noqa: E402
matplotlib.use("Agg")

from engines import chart_race as CR                         # noqa: E402
from funnel import series_icons                              # noqa: E402
from shared import look                                      # noqa: E402

C = "https://upload.wikimedia.org/wikipedia/commons/thumb/"


def _code(fn) -> str:
    """`fn`'s source with every string constant blanked — a comment or
    docstring quoting the code it replaced is not the code."""
    tree = ast.parse(inspect.getsource(fn).lstrip())
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            node.value = ""
    return ast.unparse(tree)


class AMarkMustBelongToTheThingItLabels(unittest.TestCase):
    """`junk_imagery` — the one FATAL check, which blocks at any score.

        "The 'Gold' series icon is the VTM GOLD television-channel logo
         (a Belgian broadcaster's brand mark), sitting in the legend and
         riding the line tip in EVERY frame."

    `_brand_logo_url("Gold")` full-text searched Commons for "Gold logo",
    Commons returned `VTM GOLD logo.svg`, and the only test applied was
    "does the filename read as a mark". It did. Whose mark was never asked.
    """

    def test_the_belgian_tv_channel_is_refused(self):
        self.assertFalse(
            series_icons._is_about(C + "VTM_GOLD_logo.svg.png", "Gold"))

    def test_containment_alone_would_not_have_caught_it(self):
        """The reason the fix is a LEFTOVER test and not a substring test."""
        self.assertIn("gold", "vtm gold logo.svg")

    def test_the_real_mark_still_resolves(self):
        for name, fname in (("Gold", "Gold_logo.svg.png"),
                            ("Boeing", "Boeing_logo.svg.png"),
                            ("Airbus", "Airbus_Logo_2017.png"),
                            ("Bitcoin", "Bitcoin.svg.png"),
                            ("Netflix", "Netflix_2015_logo.svg.png"),
                            ("Visa", "Visa_Inc._logo.svg.png"),
                            ("Germany", "Coat_of_arms_of_Germany.svg.png"),
                            ("Saudi Arabia", "Flag_of_Saudi_Arabia.svg.png")):
            self.assertTrue(series_icons._is_about(C + fname, name),
                            f"{name} <- {fname} should resolve")

    def test_a_neighbouring_brand_is_refused(self):
        for name, fname in (("Bitcoin", "Bitcoin_Cash_logo.svg.png"),
                            ("Apple", "Apple_Records_logo.png"),
                            ("Shell", "Royal_Dutch_Shell_logo.svg.png"),
                            ("Oil", "Oil_India_logo.png"),
                            ("United States", "Flag_of_Mexico.svg.png")):
            self.assertFalse(series_icons._is_about(C + fname, name),
                             f"{name} <- {fname} is somebody else's mark")

    def test_an_empty_name_never_matches_anything(self):
        self.assertFalse(series_icons._is_about(C + "Gold_logo.svg.png", ""))

    def test_both_lookup_paths_are_guarded(self):
        """Commons search AND the Wikipedia infobox — a fix on one of two
        callers is not a fix."""
        src = _code(series_icons._brand_logo_url)
        self.assertEqual(src.count("_is_about"), 2)


class TheFloorIsFramedNotNailedToZero(unittest.TestCase):
    """`empty_void`, three of the four blocks.

        "roughly the lower 40% of the picture is empty because the y-axis
         floors at 0 while all data lives 5.5M-12.9M; dark_fraction 1.0."
    """

    def test_a_high_band_is_framed(self):
        bot = look.frame_the_data(5.5e6, 12.9e6)
        self.assertGreater(bot, 0.0)
        self.assertLess(bot, 5.5e6)

    def test_a_growth_story_still_starts_at_zero(self):
        """417 -> 71,467 bald eagles is a comeback. Framing that band would
        flatter it, which is the opposite failure and just as dishonest."""
        self.assertEqual(look.frame_the_data(417, 71467), 0.0)

    def test_a_flat_series_does_not_explode(self):
        self.assertEqual(look.frame_the_data(5.0, 5.0), 0.0)

    def test_negatives_are_not_clipped_away(self):
        self.assertLessEqual(look.frame_the_data(-40.0, -10.0), -40.0)

    def test_the_renderer_no_longer_pins_the_axis_to_zero(self):
        src = _code(CR.render)
        self.assertNotIn("ax.set_ylim(0, cam_top)", src)
        self.assertIn("cam_bot", src)

    def test_the_floor_only_ever_opens_outward(self):
        """A breathing axis is not cosmetic: the cadence gate measures
        motion on a downscale of the frame and would read it as the story
        moving. `cam_bot` ratchets like `cam_top`."""
        src = _code(CR.render)
        self.assertIn("min(cam_bot", src)
        self.assertIn("max(cam_x", src)


class TheLineFillsTheFrame(unittest.TestCase):
    def test_the_fill_lives_in_the_design_system(self):
        """Both renderers need it, so neither may own it."""
        self.assertTrue(callable(look.gradient_fill))
        self.assertIn("gradient_fill", _code(CR.render))

    def test_it_draws_something(self):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        try:
            before = len(ax.images)
            look.gradient_fill(ax, [0, 1, 2], [1.0, 3.0, 2.0], 0.0, "#FFD37A")
            self.assertGreater(len(ax.images), before)
        finally:
            plt.close(fig)

    def test_a_degenerate_area_is_skipped_not_warned_about(self):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        try:
            for xs, ys, base in (([0, 1], [2.0, 2.0], 2.0),   # zero height
                                 ([1, 1], [1.0, 3.0], 0.0),   # zero width
                                 ([0], [1.0], 0.0)):          # one point
                look.gradient_fill(ax, xs, ys, base, "#FFD37A")
            self.assertEqual(len(ax.images), 0)
        finally:
            plt.close(fig)


class NothingIsMeasuredByCountingCharacters(unittest.TestCase):
    """`unreadable`, three of the four blocks. Every one of them is a width
    that was guessed from a length:

        "the tip label is clipped by the right frame edge, reading
         'United States  11.6' with the M cut off"
        "the y-axis title is also clipped by the frame edge, reading
         'Commercial aircraft delivered (count' with no closing paren"
        "'China 6.1B' and 'North America 5.8B' are printed on top of each
         other and over both marker icons"
    """

    def test_the_tip_flip_is_measured(self):
        src = _code(CR.render)
        self.assertNotIn("len(label) * TIP_LABEL_PX_PER_CHAR", src)
        self.assertIn("_text_px(fig, label", src)

    def test_the_label_separation_comes_from_the_label(self):
        """It was `cam_top * 0.058` — a fraction of the axis TOP, which is
        not the axis HEIGHT once the floor is framed, and was never the
        height of the thing being separated."""
        src = _code(CR.render)
        self.assertNotIn("cam_top * 0.058", src)

    def test_the_axis_name_is_fitted(self):
        self.assertIn("_fit_axis_name", _code(CR.render))

    def _fit(self, text, band):
        import matplotlib.pyplot as plt
        fig = plt.figure(figsize=(10, 19.2), dpi=100)
        try:
            fig.canvas.draw()
            return CR._fit_axis_name(fig, text, band)
        finally:
            plt.close(fig)

    def test_a_long_axis_name_loses_its_parenthetical_first(self):
        out = self._fit("Commercial aircraft delivered (count)", 260)
        self.assertNotIn("(count", out)
        self.assertIn("Commercial", out)

    def test_and_is_ellipsised_rather_than_cut_mid_word(self):
        out = self._fit("Commercial aircraft delivered worldwide "
                        "by every manufacturer (count)", 120)
        self.assertTrue(out.endswith("…"), out)

    def test_a_name_that_fits_is_left_alone(self):
        self.assertEqual(self._fit("Barrels per day", 4000),
                         "Barrels per day")

    def test_an_empty_name_survives(self):
        for t in ("", None):
            self.assertEqual(self._fit(t, 300), "" if t is None else t)


class TheHookGoesWhereTheDataIsNot(unittest.TestCase):
    """`unreadable`:

        "the 'Nobody saw this coming.' card is printed on top of the chart
         and covers the 'Saudi Arabia 8.5M' series label, which shows only
         as a smear behind it"

    `cam_top` is the top tip times 1.22, so the top ~18% of the plot is
    empty by construction on every frame. The card is anchored there rather
    than at a fixed 0.63 that happened to land on the data.
    """

    def test_the_card_is_anchored_to_the_axes_not_a_constant(self):
        src = _code(CR.render)
        self.assertNotIn("fig.text(0.5, 0.63, hook", src)
        self.assertIn("_hy", src)


if __name__ == "__main__":
    unittest.main()
