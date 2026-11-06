"""The Twitch channel picks what strangers already loved (operator,
2026-11-05, choosing "Switch it" after Baller Bro, built on the week's most
upvoted sports posts, reached a 446-view median while this channel sat at 9
with ~1% of its views from the Shorts feed).

r/LivestreamFail's most upvoted clips and Twitch's category charts join the
clip arm's pool from ANY streamer, an upvoted moment outranks a fan's clip
of the same velocity, and the ranker is told to favour what a stranger
feels with no idea who anyone is."""
import unittest
from pathlib import Path
from unittest import mock

import scripts.run_third as rt
from funnel import hot_clips
from third_capture import author

SRC = (Path(__file__).resolve().parents[1] / "scripts" / "run_third.py"
       ).read_text()


class TheInternetsPicksJoinThePool(unittest.TestCase):
    def setUp(self):
        rt._PROVEN_POOL = None
        hot_clips._LSF_CACHE.clear()

    tearDown = setUp

    def test_upvoted_clips_and_category_charts_from_anyone(self):
        hot = [{"slug": "A", "url": "https://clips.twitch.tv/A",
                "post_title": "Streamer breaks down crying", "upvotes": 4000,
                "permalink": "p"}]
        ce = mock.Mock()
        ce.helix_clips.return_value = [
            {"url": "https://clips.twitch.tv/A", "slug": "A", "views": 9000,
             "channel": "somebody_new", "title": "t"}]
        ce.top_by_category.return_value = [
            {"url": "https://clips.twitch.tv/B", "slug": "B", "views": 50000,
             "channel": "other", "title": "t2"}]
        with mock.patch.object(hot_clips, "livestreamfail",
                               return_value=hot):
            pool = rt._proven_pool(ce, {})
        self.assertEqual([c["proven_by"] for c in pool],
                         ["r/LivestreamFail", "Twitch category chart"])
        self.assertEqual(pool[0]["internet"]["post_title"],
                         "Streamer breaks down crying")

    def test_read_once_a_run(self):
        ce = mock.Mock()
        ce.helix_clips.return_value = []
        ce.top_by_category.return_value = []
        with mock.patch.object(hot_clips, "livestreamfail",
                               return_value=[]) as lsf:
            rt._proven_pool(ce, {})
            rt._proven_pool(ce, {})
        self.assertEqual(lsf.call_count, 2)     # week + month, once

    def test_it_never_raises(self):
        ce = mock.Mock()
        ce.helix_clips.side_effect = RuntimeError("down")
        with mock.patch.object(hot_clips, "livestreamfail",
                               return_value=[{"slug": "A"}]):
            self.assertEqual(rt._proven_pool(ce, {}), [])

    def test_the_clip_arm_takes_them_under_the_same_rules(self):
        i = SRC.index("for c in _proven_pool(clip_edit, spec):")
        block = SRC[i:i + 500]
        for rule in ("posted_keys", "per_streamer", "_same_event"):
            self.assertIn(rule, block)

    def test_an_upvoted_moment_outranks_a_fans_clip(self):
        self.assertIn('proven_boost = float(spec.get("proven_boost", 4.0))',
                      SRC)
        self.assertEqual(SRC.count('_fit(c["channel"], c)'), 2)


class TheRankerLooksForNoContextMoments(unittest.TestCase):
    def test_it_is_told(self):
        self.assertIn("NO CONTEXT NEEDED", author._RANK_SYSTEM)

    def test_it_sees_what_strangers_said(self):
        seen = {}

        def fake(user, system):
            seen["user"] = user
            return {"scores": []}
        with mock.patch.object(author, "_call_claude", side_effect=fake):
            author.rank_clips([{"url": "u", "channel": "x", "title": "t",
                                "internet": {"post_title": "he cries",
                                             "upvotes": 12}}])
        self.assertIn("internet_says='he cries' upvotes=12", seen["user"])


if __name__ == "__main__":
    unittest.main()
