"""A size comparison in a hook is looked up and checked, never invented.

Operator, 2026-09-25: *"why a forest the size of France disappeared"*. A
comparison brings a name and a number the dataset does not contain, so the
brain is only ever handed the ones `shared/scale_refs` has checked.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import hook_doctrine as H  # noqa: E402
from shared import scale_refs as S     # noqa: E402

CFG = json.loads((ROOT / "data_learning" / "niche.config.json").read_text())
# pinned soft: production persists a sharpened hook into the config
AMAZON = dict(next(s for s in CFG["stories"]
                   if s["slug"] == "amazon-still-shrinking"),
              hook="The clearing is dropping. The damage isn't.")


class TheArithmeticIsTrue(unittest.TestCase):
    def test_units_convert(self):
        self.assertAlmostEqual(S.to_km2(100, "hectares"), 1.0)
        self.assertAlmostEqual(S.to_km2(1, "million hectares"), 10_000.0)
        self.assertAlmostEqual(S.to_km2(1, "square miles"), 2.589988, 5)
        self.assertIsNone(S.to_km2(5, "percent"))

    def test_bigger_means_bigger(self):
        self.assertEqual(S.phrase_for(750_000, 695_662, "Texas"),
                         "bigger than Texas")
        self.assertIsNone(S.phrase_for(600_000, 695_662 * 1.2, "Texas"))

    def test_times_is_floored_so_more_than_stays_true(self):
        self.assertEqual(S.phrase_for(3.9 * 4_001, 4_001, "Rhode Island"),
                         "more than 3 times the size of Rhode Island")

    def test_a_place_is_never_compared_with_itself(self):
        got = S.comparisons([(551_695, "square kilometers",
                              "Entire Country Of France")])
        self.assertNotIn("France", [c["name"] for c in got])


class OnlyCheckedComparisonsReachAHook(unittest.TestCase):
    def test_the_amazon_story_gets_a_true_comparison(self):
        facts = H.scale_facts(AMAZON)
        self.assertIn("bigger than Texas", [f["phrase"] for f in facts])

    def test_a_checked_name_is_allowed_and_an_unchecked_one_is_not(self):
        brain_calls = []

        def brain(prompt):
            brain_calls.append(prompt)
            if "fact-checker" in prompt:
                return json.dumps({"supported": [1, 2]})
            return json.dumps({"hooks": [
                "A forest bigger than Texas vanished — and you ate it.",
                "A forest bigger than Mongolia vanished — and you ate it."]})
        got = H.sharpen(dict(AMAZON), brain=brain, log=lambda m: None)
        self.assertEqual(got, "A forest bigger than Texas vanished — and you ate it.")
        self.assertIn("bigger than Texas", brain_calls[0])


if __name__ == "__main__":
    unittest.main()
