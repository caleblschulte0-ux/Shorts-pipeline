"""Long-form builds an EPISODE of several stories and holds when there is
not enough for one. Before: one story per video — a 47s all-still cut on
2026-09-06 (doctor 38fd2900770d) and a 53s one on 2026-10-07, neither of
them a watch-page video."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))

import build_longform as BL  # noqa: E402

# Every fixture beat cites one OFFICIAL dataset: readiness() refuses a story
# built on invented ("illustrative") numbers, and these tests are about
# depth and selection, not sourcing (tests/test_longform_sourced.py).
OFFICIAL = {"params": {"file": "lf_fixture_official.json"}}
_DATA_PATCH = None


def setUpModule():
    global _DATA_PATCH
    import json as _json
    import tempfile as _tf
    d = Path(_tf.mkdtemp(prefix="lf-data-"))
    (d / "lf_fixture_official.json").write_text(
        _json.dumps({"source": {"officiality": "official"}}))
    _DATA_PATCH = mock.patch.object(BL, "DATA_DIR", d)
    _DATA_PATCH.start()


def tearDownModule():
    _DATA_PATCH.stop()


def _story(slug: str, words_per_say: int = 20, beats: int = 3,
           title: str | None = None) -> dict:
    say = " ".join(["word"] * words_per_say)
    return {"slug": slug, "title": title or slug.upper(), "hook": say,
            "closing": say,
            "segments": [{"say": say, **OFFICIAL} for _ in range(beats)]}


class EpisodeSelection(unittest.TestCase):
    def _pick(self, stories, posted, done=(), views=None, explicit=None):
        with mock.patch.object(BL, "_posted_slugs", return_value=posted), \
                mock.patch.object(BL, "_already_longformed",
                                  return_value=set(done)), \
                mock.patch.object(BL, "_views", return_value=views or {}):
            return BL.pick_episode({"stories": stories}, explicit)

    def test_a_two_beat_story_is_not_a_chapter(self):
        self.assertFalse(BL.readiness(_story("a", beats=2))[0])
        self.assertTrue(BL.readiness(_story("a"))[0])

    def test_one_shorts_story_is_never_a_long_form(self):
        """~45s of narration — the 2026-10-07 case — holds the slot."""
        self.assertIsNone(self._pick([_story("a", 30)], ["a"]))

    def test_it_fills_to_the_target_and_stops(self):
        stories = [_story(f"s{i}") for i in range(20)]
        picks = self._pick(stories, [s["slug"] for s in stories])
        total = sum(BL.estimate_seconds(s) for s in stories
                    if s["slug"] in picks)
        self.assertGreaterEqual(total, BL.EPISODE_MIN_S)
        self.assertLessEqual(len(picks), BL.EPISODE_MAX_STORIES)
        last = BL.estimate_seconds(stories[0])
        self.assertLess(total - last, BL.EPISODE_TARGET_S)

    def test_best_watched_leads_then_newest(self):
        stories = [_story(f"s{i}") for i in range(10)]
        posted = [s["slug"] for s in stories]          # newest first
        picks = self._pick(stories, posted, views={"s7": 900, "s3": 50})
        self.assertEqual(picks[:3], ["s7", "s3", "s0"])

    def test_already_longformed_is_skipped(self):
        stories = [_story(f"s{i}") for i in range(10)]
        picks = self._pick(stories, [s["slug"] for s in stories],
                           done=["s0", "s1"])
        self.assertNotIn("s0", picks)
        self.assertNotIn("s1", picks)

    def test_explicit_slugs_are_held_to_the_same_bar(self):
        stories = [_story(f"s{i}", 70) for i in range(4)]
        stories.append(_story("thin", beats=2))
        self.assertIsNone(self._pick(stories, [], explicit=["s0", "thin"]))
        self.assertEqual(self._pick(stories, [], explicit=["s1", "s0"]),
                         ["s1", "s0"])

    def test_the_title_leads_with_the_best_story(self):
        t = BL.episode_title([_story("a", title="Lake Chad Vanished (3 Charts)"),
                              _story("b"), _story("c")])
        self.assertEqual(t, "Lake Chad Vanished (+2 More Stories In Charts)")
        self.assertLessEqual(len(BL.episode_title(
            [_story("a", title="x" * 200), _story("b")])), 100)


if __name__ == "__main__":
    unittest.main()
