"""What the explainer's pictures SAY must be true, and must be about the thing.

Every one of these was named by the showrunner on 2026-09-26's explainer:

- "the gauge shows fractional city counts (1.5, 4.9) for an integer claim",
  title "cut off at both edges ('TIES WAYMO'S...')"  -> fill_vessel
- "the payoff grid reads '15 times over' while the title and narration say
  16 sunrises", the grey '15' "nearly invisible"      -> nest
- "'With beaver dams fits in Without beaver dams' (garbled)"  -> nest title
- "the grid that stands for beavers is 20 generic HUMAN-silhouette icons"
  (FATAL junk_imagery)                                -> icons
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_learning import charts as C      # noqa: E402
from data_learning import icons as I       # noqa: E402
from data_learning import viz_scene as vs  # noqa: E402


class ACountCountsInWholeSteps(unittest.TestCase):
    def test_whole_numbers_stay_whole(self):
        for t in (0.1, 0.3, 0.5, 0.77, 0.99, 1.0):
            v = C.count_up(5, t)
            self.assertEqual(v, round(v), t)
        self.assertEqual(C.count_up(5, 1.0), 5)
        self.assertEqual(C.count_up(200000, 1.0), 200000)

    def test_a_decimal_keeps_its_own_precision(self):
        self.assertEqual(C.count_up(4.41, 1.0), 4.41)
        self.assertAlmostEqual(C.count_up(4.41, 0.5), 2.205, delta=0.006)

    def test_the_vessel_uses_it_and_fits_its_title(self):
        src = (ROOT / "data_learning" / "charts.py").read_text()
        self.assertIn("fmt(count_up(star.value, eased))", src)
        self.assertNotIn("fmt(star.value * eased)", src)


class AMultipleIsSaidHonestly(unittest.TestCase):
    def test_below_twenty_it_keeps_a_decimal(self):
        self.assertEqual(vs.times_text(1440 / 93), "15.5")
        self.assertEqual(vs.times_text(3.0), "3")
        self.assertEqual(vs.times_text(76.4), "76")

    def test_the_nest_says_the_multiple_not_fits_in(self):
        src = (ROOT / "data_learning" / "viz_scene.py").read_text()
        self.assertNotIn('fits in {_label_of(big_p)}"', src)
        self.assertIn("times_text(ratio)} times over", src)


class AnAnimalIsNotAPerson(unittest.TestCase):
    def test_an_animal_population_is_the_animal(self):
        self.assertEqual(I.emoji_codepoint("north american beaver population"),
                         "1f9ab")
        self.assertEqual(I.emoji_codepoint("whale population"), "1f40b")
        self.assertEqual(I.emoji_codepoint("bee population"), "1f41d")

    def test_a_species_with_no_icon_is_no_icon_not_a_crowd(self):
        self.assertIsNone(I.emoji_codepoint("axolotl population"))

    def test_people_are_still_people(self):
        for t in ("world population", "us population", "prison population",
                  "population"):
            self.assertEqual(I.emoji_codepoint(t), "1f465", t)

    def test_a_sea_star_is_not_a_wave(self):
        self.assertIsNone(I.emoji_codepoint("sea star wasting disease"))
        self.assertEqual(I.emoji_codepoint("sea level rise"), "1f30a")


if __name__ == "__main__":
    unittest.main()
