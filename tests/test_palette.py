"""THE HOUSE PALETTE, and the lie the modulo was telling.

Operator, 2026-09-09: *"just do a whole pass on how we're conveying data ...
just the colors and style of graphics we use."*

The audit that day, over `data_learning/`, `shared/` and `engines/`:

* 100 distinct colours in the render code, 8 of them from the house palette
* twelve near-identical darks for what is one card background
* the series palette CYCLED — `palette[i % len(palette)]` — and 7.3% of the
  catalogue's datasets have more than six points, up to thirteen. On 82
  datasets two different categories were painted the same colour.
* the series colours failed the colour-blindness check: `#34D399` against
  `#F472B6` at ΔE 6.6 for a deuteranope

Reordering the six fixed the ADJACENT-pair check and was not enough, because
adjacency is not what a viewer sees — a donut shows every wedge at once.
All-pairs, the reordered palette had the violet and the blue at ΔE 0.3 for a
deuteranope (identical) and the two ambers at 8.0 in NORMAL vision, under the
hard floor of 15. So the colours moved, each by the smallest nudge from its
original that clears every floor.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import palette as pal        # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class ColourIsComputedNotEyeballed(unittest.TestCase):
    """The one habit the house method insists on: run the checks."""

    def test_the_shipped_palette_passes_every_check(self):
        v = pal.audit()
        self.assertTrue(v["ok"], "; ".join(v["problems"]))

    def test_every_series_colour_is_readable_on_the_card(self):
        for c in pal.SERIES + (pal.OVERFLOW,):
            k = pal.contrast(c, pal.CARD)
            self.assertGreaterEqual(k, pal.CONTRAST_FLOOR, f"{c} at {k:.2f}")

    def test_adjacent_slots_survive_red_green_colourblindness(self):
        """~8% of men. The pair that failed before this landed was the green
        against the pink, at ΔE 6.6."""
        for a, b in zip(pal.SERIES, pal.SERIES[1:]):
            for kind in ("deuteranopia", "protanopia"):
                d = pal.delta_e(a, b, kind)
                self.assertGreaterEqual(d, pal.CVD_FLOOR,
                                        f"{a} vs {b} {kind} ΔE {d:.1f}")

    def test_adjacent_slots_survive_ORDINARY_vision_too(self):
        """Below 15 is the hard fail — a full-colour reader cannot tell the
        pair apart, and no amount of secondary encoding excuses that one."""
        for a, b in zip(pal.SERIES, pal.SERIES[1:]):
            d = pal.delta_e(a, b)
            self.assertGreaterEqual(d, pal.NORMAL_FLOOR, f"{a} vs {b}")

    def test_the_palette_this_replaced_still_FAILS(self):
        """A regression guard with teeth. If the shipped palette passes and
        the one it replaced also passes, the floors were loosened rather than
        the colours fixed — which is the failure mode this whole file exists
        to prevent."""
        broken = ("#60A5FA", "#F59E0B", "#A78BFA", "#F472B6",
                  "#34D399", "#FBBF24")
        self.assertFalse(pal.audit(broken)["ok"])

    def test_the_check_reproduces_the_reference_validator(self):
        """`validate_palette.js` reported ΔE 6.6 for the worst colourblind
        pair of the old palette. A first version of this module answered 14.7
        for the same pair — CIE76 Lab with OKLab floors, two rulers and one
        set of numbers — and so PASSED the palette the validator had just
        failed. These are the validator's own figures."""
        self.assertAlmostEqual(
            min(pal.delta_e("#F472B6", "#34D399", k)
                for k in ("deuteranopia", "protanopia")), 6.6, delta=0.15)
        self.assertAlmostEqual(
            min(pal.delta_e("#A78BFA", "#F472B6", k)
                for k in ("deuteranopia", "protanopia")), 10.3, delta=0.15)

    def test_ALL_pairs_separate_not_just_adjacent_ones(self):
        """Adjacency is not what a viewer sees: a donut shows every wedge at
        once. Checked all-pairs, merely REORDERING the old colours left the
        violet and the blue at ΔE 0.3 for a deuteranope — identical."""
        import itertools
        for a, b in itertools.combinations(pal.SERIES, 2):
            self.assertGreaterEqual(pal.delta_e(a, b), pal.NORMAL_FLOOR,
                                    f"{a} vs {b} in normal vision")
            d = min(pal.delta_e(a, b, k)
                    for k in ("deuteranopia", "protanopia"))
            self.assertGreaterEqual(d, pal.CVD_FLOOR, f"{a} vs {b} colourblind")


class ItNeverWrapsAround(unittest.TestCase):
    """`palette[i % len(palette)]` says slot 6 IS slot 0. On a thirteen-wedge
    donut that is two wedges the same colour with different names on them."""

    def test_slot_six_is_not_slot_zero(self):
        self.assertNotEqual(pal.series_color(0), pal.series_color(6))

    def test_everything_past_the_palette_is_the_neutral(self):
        for i in range(len(pal.SERIES), len(pal.SERIES) + 8):
            self.assertEqual(pal.series_color(i), pal.OVERFLOW)

    def test_the_neutral_is_not_one_of_the_series(self):
        self.assertNotIn(pal.OVERFLOW, pal.SERIES)

    def test_a_negative_slot_is_not_the_last_colour(self):
        self.assertEqual(pal.series_color(-1), pal.OVERFLOW)

    def test_colour_stops_where_the_LABELS_stop(self):
        """The waffle names five entries and its palette handed out six, so
        the sixth slice had a colour and nothing saying what it was."""
        self.assertEqual(pal.series_color(5, labelled=5), pal.OVERFLOW)
        self.assertEqual(pal.series_color(4, labelled=5), pal.SERIES[4])

    def test_the_highlight_always_wins(self):
        self.assertEqual(pal.series_color(3, highlight="#4FD1C5"), "#4FD1C5")


class TheRenderersUseIt(unittest.TestCase):
    """Rule zero. A palette module nothing imports is a colour swatch."""

    CHARTS = ROOT / "data_learning" / "charts.py"

    def test_no_cycled_palette_survives_in_the_chart_code(self):
        src = self.CHARTS.read_text()
        self.assertNotIn("% len(palette)", src)
        self.assertNotRegex(src, r"palette\s*=\s*\[")

    def test_the_chart_code_imports_the_shared_palette(self):
        self.assertIn("from shared.palette import series_color",
                      self.CHARTS.read_text())

    def test_the_waffle_ties_its_colours_to_its_legend(self):
        src = self.CHARTS.read_text()
        self.assertIn("WAFFLE_LEGEND", src)
        self.assertIn("labelled=WAFFLE_LEGEND", src)
        self.assertNotIn("labels[:5]", src)


class OneCardColourNotTwelve(unittest.TestCase):
    """Twelve near-identical darks were in the render code for one card
    background. A viewer cannot tell them apart, which is exactly why they
    drifted — nothing ever looked wrong enough to fix."""

    def test_the_card_has_one_definition(self):
        self.assertEqual(pal.CARD, "#0B1020")

    def test_the_darks_that_were_confused_are_genuinely_indistinguishable(self):
        """Recorded so the next person does not 'fix' one of them back in:
        these differ by less than the eye resolves, so a mismatch between two
        machines is invisible in review and wrong in the file."""
        for other in ("#0A0E20", "#0C1220", "#0B0F17", "#0A0E1A"):
            # OKLab x100. The closest SERIES pair is 8.4 apart and that is
            # the threshold of "tell these two marks apart"; these darks are
            # all under 2, an order of magnitude closer.
            self.assertLess(pal.delta_e(pal.CARD, other), 2.5,
                            f"{other} is far enough from the card to be "
                            f"a deliberate second colour")


if __name__ == "__main__":
    unittest.main()


class EveryThemeIsChecked(unittest.TestCase):
    """The palette work landed on `charts.py` first — and the charts are the
    FALLBACK. The 42 machines, which lead most beats, take their colour from
    `studio_render.THEMES`, so for a while the validated palette applied to
    the pictures we draw least.

    Two of the six themes failed the moment they were measured: theme 2 had
    a rose and a green ΔE 4.6 apart for a colourblind viewer (below even the
    hard floor), theme 3 a green and a cyan 12.1 apart in ORDINARY vision.
    One story in three shipped colours a viewer could not separate.
    """

    def _themes(self):
        from data_learning import studio_render as sr
        return sr.THEMES

    def test_every_theme_separates_all_three_of_its_colours(self):
        bad = {}
        for i, t in enumerate(self._themes()):
            v = pal.audit_trio([t["highlight"], t["accent"], t["warn"]])
            if not v["ok"]:
                bad[i] = v["problems"]
        self.assertEqual(bad, {}, f"themes a viewer cannot read: {bad}")

    def test_the_two_themes_that_failed_are_actually_different_now(self):
        """A guard against a revert that keeps the comment and drops the fix."""
        themes = self._themes()
        self.assertNotEqual(themes[2]["accent"], "#FB7185")
        self.assertNotEqual(themes[3]["highlight"], "#34D399")

    def test_the_pairs_that_failed_still_FAIL_the_check(self):
        """If these ever pass, the floors were loosened rather than the
        colours fixed."""
        self.assertFalse(pal.audit_trio(["#FBBF24", "#FB7185", "#34D399"])["ok"])
        self.assertFalse(pal.audit_trio(["#34D399", "#22D3EE", "#FBBF24"])["ok"])

    def test_the_themes_are_judged_on_ALL_pairs(self):
        """Three colours drawn at once: adjacency is meaningless here, and
        `audit` (adjacent-only) would have cleared theme 3."""
        import inspect
        self.assertIn("combinations", inspect.getsource(pal.audit_trio))
