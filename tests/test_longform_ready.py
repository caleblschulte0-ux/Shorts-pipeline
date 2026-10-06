"""Long-form picks the deepest unused story and holds when none is ready
(doctor 38fd2900770d). Before: newest unused slug, rendered blind — a 47s
all-still cut that only the showrunner stopped."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))

import build_longform as BL  # noqa: E402


def _story(slug: str, words_per_say: int, beats: int = 4) -> dict:
    say = " ".join(["word"] * words_per_say)
    return {"slug": slug, "hook": say, "closing": say,
            "segments": [{"say": say} for _ in range(beats)]}


class LongformReadiness(unittest.TestCase):
    def _pick(self, stories, posted, done=(), explicit=None):
        cfg = {"stories": stories}
        with mock.patch.object(BL, "_posted_slugs", return_value=posted), \
                mock.patch.object(BL, "_already_longformed",
                                  return_value=set(done)):
            return BL.pick_slug(cfg, explicit)

    def test_thin_story_is_not_ready(self):
        self.assertFalse(BL.readiness(_story("a", 16))[0])      # ~47s case
        self.assertFalse(BL.readiness(_story("a", 60, beats=2))[0])
        self.assertTrue(BL.readiness(_story("a", 40))[0])

    def test_newest_thin_story_loses_to_older_deep_one(self):
        stories = [_story("new", 16), _story("deep", 40)]
        self.assertEqual(self._pick(stories, ["new", "deep"]), "deep")

    def test_deepest_wins_then_newest_breaks_ties(self):
        stories = [_story("a", 40), _story("b", 50), _story("c", 50)]
        self.assertEqual(self._pick(stories, ["a", "c", "b"]), "c")

    def test_slot_is_held_when_nothing_is_ready(self):
        self.assertIsNone(self._pick([_story("t", 16)], ["t"]))

    def test_already_longformed_is_skipped(self):
        stories = [_story("a", 40), _story("b", 40)]
        self.assertEqual(self._pick(stories, ["a", "b"], done=["a"]), "b")

    def test_explicit_slug_is_held_to_the_same_bar(self):
        stories = [_story("t", 16), _story("deep", 40)]
        self.assertIsNone(self._pick(stories, [], explicit="t"))
        self.assertEqual(self._pick(stories, [], explicit="deep"), "deep")


if __name__ == "__main__":
    unittest.main()
