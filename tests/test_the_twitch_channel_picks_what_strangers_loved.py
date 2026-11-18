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
        block = SRC[i:i + 800]
        for rule in ("posted_keys", "per_streamer", "_same_event"):
            self.assertIn(rule, block)

    def test_an_upvoted_moment_outranks_a_fans_clip(self):
        self.assertIn('proven_boost = float(spec.get("proven_boost", 4.0))',
                      SRC)
        self.assertEqual(SRC.count('_fit(c["channel"], c)'), 2)


class AnUpvotedClipIsNotPunishedForItsAge(unittest.TestCase):
    """11-06, the first run: 22 upvoted clips in the pool, none in the top
    five, because views per hour divided a month-old clip by its month."""

    def test_its_age_is_capped_at_a_day(self):
        i = SRC.index("for c in cands[:age_probe]:")
        block = SRC[i:i + 900]
        self.assertIn('c.get("proven_by") == "r/LivestreamFail"', block)
        self.assertIn("age = min(age or 24.0, 24.0)", block)
        self.assertLess(block.index("age = min("), block.index('c["vph"]'))

    def test_the_pick_line_says_where_it_came_from(self):
        i = SRC.index('print(f"[pick]')
        self.assertIn("proven_by", SRC[i:i + 500])


class ASearchChannelPostsNamesPeopleSearch(unittest.TestCase):
    """11-06..11-10: chart clips from unknown streamers got 0-3 views; the
    channel's hits were drama about names people search."""

    def test_a_chart_clip_needs_a_followed_streamer(self):
        i = SRC.index("for c in _proven_pool(clip_edit, spec):")
        block = SRC[i - 600:i + 400]
        self.assertIn("_followed", block)
        self.assertIn('("r/LivestreamFail", "favored game")', block)

    def test_a_chart_clip_gets_no_free_pass_on_the_core_penalty(self):
        i = SRC.index("def _fit(ch, c=None):")
        block = SRC[i:i + 400]
        self.assertNotIn("else 1.0)", block)

    def test_the_ranker_is_told_about_search(self):
        from third_capture import author
        self.assertIn("SEARCHED NAMES", author._RANK_SYSTEM)


class PostItBeforeTheOtherClippers(unittest.TestCase):
    """11-14: same retention as Baller Bro, ~1% of its feed views. A clip
    days old is already on dozens of clipper channels."""

    def test_a_stale_clip_ranks_far_down(self):
        i = SRC.index("for c in cands[:age_probe]:")
        block = SRC[i:i + 2400]
        self.assertIn('spec.get("fresh_h", 48)', block)
        self.assertIn('c["score"] *= float(spec.get("stale_factor", 0.3))',
                      block)

    def test_it_uses_the_true_age_not_the_capped_one(self):
        i = SRC.index("for c in cands[:age_probe]:")
        block = SRC[i:i + 2400]
        self.assertLess(block.index('c["age_true_h"] = age'),
                        block.index("age = min(age or 24.0, 24.0)"))


class GTASixIsFavored(unittest.TestCase):
    """Operator, 2026-11-18: "Favor GTA 6 clips"."""

    def test_a_gta_six_clip_is_recognised(self):
        self.assertIn("Grand Theft Auto VI", rt.FAVOR_GAMES)
        for t in ("xQc's first GTA 6 heist", "GTA VI police chase",
                  "Grand Theft Auto VI is insane"):
            self.assertTrue(rt._favored({"title": t}, set()), t)
        self.assertFalse(rt._favored({"title": "GTA 5 RP moment"}, set()))
        self.assertTrue(rt._favored({"title": "x", "game_id": "99"},
                                    {"99"}))

    def test_its_chart_joins_from_any_streamer(self):
        class CE:
            def helix_clips(self, ids):
                return []

            def top_by_category(self, ids, days=2, top=20):
                if ids == ["777"]:
                    return [{"url": "u/gta", "channel": "nobody",
                             "title": "first heist", "views": 9}]
                return []

            def game_id(self, name):
                return "777"
        rt._PROVEN_POOL = None
        from funnel import hot_clips
        hot_clips._LSF_CACHE.clear()
        with mock.patch.object(hot_clips, "livestreamfail",
                               return_value=[]):
            pool = rt._proven_pool(CE(), {})
        rt._PROVEN_POOL = None
        self.assertEqual([c["proven_by"] for c in pool], ["favored game"])
        i = SRC.index("for c in _proven_pool(clip_edit, spec):")
        self.assertIn('"favored game"', SRC[i:i + 500])

    def test_it_is_boosted_and_the_ranker_is_told(self):
        i = SRC.index("def _fit(ch, c=None):")
        self.assertIn("_favored(c, _fav_ids)", SRC[i:i + 300])
        from third_capture import author
        self.assertIn("GTA 6 IS WHAT PEOPLE SEARCH NOW",
                      author._RANK_SYSTEM)


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
