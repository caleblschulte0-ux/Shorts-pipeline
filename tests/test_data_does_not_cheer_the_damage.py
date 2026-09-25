"""Data never celebrates bad news.

The showrunner on amazon-still-shrinking (2026-09-24): "Data cheers with both
arms up while the clearing grows, which celebrates the damage". Every host in
both looks is posed through `viz_scene.scene_host`, and it now asks
`data_learning/tone.py` first.
"""
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_learning import tone  # noqa: E402
from data_learning import viz_scene as vs  # noqa: E402


class TheToneIsReadFromTheWords(unittest.TestCase):
    def test_harm_is_bad_news(self):
        for t in ("The Amazon has lost 750,000 square kilometers",
                  "The bill still grows",
                  "Coffee prices hit a record after the drought",
                  "Bat deaths from the fungus"):
            self.assertTrue(tone.is_bad_news(t), t)

    def test_a_recovery_is_not(self):
        for t in ("Bald eagle population rebound",
                  "Wolves return to Colorado",
                  "Life expectancy climbs to 73",
                  "Solar power output doubled"):
            self.assertFalse(tone.is_bad_news(t), t)


class ACheerOverDamageBecomesAReaction(unittest.TestCase):
    def test_the_role_is_changed_only_for_bad_news(self):
        self.assertEqual(tone.honest_role("cheer", "The Amazon has lost land"),
                         "shock")
        self.assertEqual(tone.honest_role("cheer", "Eagles rebound"), "cheer")
        self.assertEqual(tone.honest_role("climb", "The Amazon has lost land"),
                         "climb")

    def test_every_host_goes_through_it(self):
        src = inspect.getsource(vs.scene_host)
        self.assertIn("honest_role(", src)


if __name__ == "__main__":
    unittest.main()
