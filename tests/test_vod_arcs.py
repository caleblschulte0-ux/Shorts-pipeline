"""Stories come from ONE broadcast, and Twitch tells us which clips those are.

Between 2026-09-16 and 09-22 the Third story arm ran 7 times, considered 21
clusters, and rendered nothing:

    11  no_shared_event   no two clips in the pile shared any event
     9  not_a_story       the director declined
     1  starved

The clusters were people piles — a streamer's top clips from a 10-day
window, i.e. their greatest hits. STORY_DIRECTOR_PLAYBOOK §5 says a story
cluster must be "based on an event … not merely repeated appearances by the
same streamer", and lists "the original incident, the immediate reaction" as
the evidence to look for — both of which happen inside one stream.

Twitch attaches `video_id` and `vod_offset` to every clip. Clips from the
same VOD, minutes apart, are one incident by construction. `from_discovery`
threw both fields away, so the arm could never see it.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from third_capture import storyline as sl               # noqa: E402


def _clip(cid, views, off, *, vid="v1", ch="jynxzi", dur=30.0, title=None):
    return {"url": f"https://www.twitch.tv/{ch}/clip/{cid}", "views": views,
            "duration": dur, "title": title or cid, "channel": ch,
            "age_h": 20.0, "video_id": vid, "vod_offset": off}


class OneBroadcastIsOneStory(unittest.TestCase):
    def test_setup_escalation_reaction_in_broadcast_order(self):
        arcs = sl.find_vod_arcs([
            _clip("reaction", 2000, 1400),
            _clip("setup", 900, 1000),
            _clip("blowup", 5000, 1180),
        ])
        self.assertEqual(len(arcs), 1)
        self.assertEqual([c["title"] for c in arcs[0]["clips"]],
                         ["setup", "blowup", "reaction"])
        self.assertEqual(arcs[0]["kind"], "vod_arc")
        self.assertEqual(arcs[0]["video_id"], "v1")

    def test_the_arc_is_in_the_shape_the_story_arm_consumes(self):
        arc = sl.find_vod_arcs([_clip("a", 900, 1000),
                                _clip("b", 800, 1200)])[0]
        self.assertEqual(arc["who"], ["jynxzi"])
        for c in arc["clips"]:
            for field in ("source_url", "title", "channel", "date",
                          "vod_offset", "video_id"):
                with self.subTest(field=field):
                    self.assertIn(field, c)
            self.assertTrue(c["date"], "a clip with no date reads as undated")

    def test_the_hottest_broadcasts_come_first(self):
        arcs = sl.find_vod_arcs([
            _clip("a", 100, 1000, vid="cold"), _clip("b", 100, 1200, vid="cold"),
            _clip("c", 9000, 1000, vid="hot"), _clip("d", 9000, 1200, vid="hot"),
        ])
        self.assertEqual([a["video_id"] for a in arcs], ["hot", "cold"])


class WhatIsNotAStory(unittest.TestCase):
    def test_one_moment_clipped_twice_is_not_an_arc(self):
        """The one viral second everybody clipped. Without the same-moment
        collapse it looks like a two-beat story."""
        self.assertEqual(sl.find_vod_arcs([_clip("a", 900, 500),
                                           _clip("b", 700, 505)]), [])

    def test_the_duplicate_moment_keeps_its_most_viewed_copy(self):
        arcs = sl.find_vod_arcs([_clip("setup", 900, 1000),
                                 _clip("blowup-small", 1200, 1188),
                                 _clip("blowup-big", 5000, 1180)])
        titles = [c["title"] for c in arcs[0]["clips"]]
        self.assertIn("blowup-big", titles)
        self.assertNotIn("blowup-small", titles)

    def test_moments_hours_apart_are_different_stories(self):
        self.assertEqual(sl.find_vod_arcs([_clip("a", 900, 1000),
                                           _clip("b", 900, 12000)]), [])

    def test_clips_from_different_broadcasts_never_join(self):
        self.assertEqual(sl.find_vod_arcs([_clip("a", 900, 1000, vid="x"),
                                           _clip("b", 900, 1100, vid="y")]), [])

    def test_a_clip_without_vod_coordinates_is_skipped_not_guessed(self):
        bare = _clip("b", 900, 1100)
        bare["video_id"] = None
        self.assertEqual(sl.find_vod_arcs([_clip("a", 900, 1000), bare]), [])

    def test_the_same_clip_twice_in_the_pool_counts_once(self):
        """The sweep runs 7d and 30d windows, so a clip can arrive twice."""
        self.assertEqual(sl.find_vod_arcs([_clip("a", 900, 1000),
                                           _clip("a", 900, 1000)]), [])

    def test_member_cap_keeps_the_hottest_in_broadcast_order(self):
        pool = [_clip(f"c{i}", 100 * (i + 1), 1000 + i * 60) for i in range(9)]
        arc = sl.find_vod_arcs(pool, max_members=4)[0]
        offs = [c["vod_offset"] for c in arc["clips"]]
        self.assertEqual(len(offs), 4)
        self.assertEqual(offs, sorted(offs))
        self.assertEqual(min(c["views"] for c in arc["clips"]), 600)


class TheCoordinatesAreNoLongerThrownAway(unittest.TestCase):
    def test_from_discovery_keeps_vod_id_and_offset(self):
        out = sl.from_discovery([_clip("a", 900, 1234.0)])[0]
        self.assertEqual(out["video_id"], "v1")
        self.assertEqual(out["vod_offset"], 1234.0)


class TheStoryArmUsesThem(unittest.TestCase):
    """Wiring, read from the source: an arc finder nothing calls is the
    thing CLAUDE.md's rule zero exists to prevent."""

    @classmethod
    def setUpClass(cls):
        src = (ROOT / "scripts" / "run_third.py").read_text()
        tree = ast.parse(src)
        cls.fn = next(n for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef)
                      and n.name == "_story_attempt")
        cls.body = ast.get_source_segment(src, cls.fn)

    def test_vod_arcs_are_offered_before_people_clusters(self):
        self.assertIn("vod_arcs + storyline.find_clusters(", self.body)

    def test_a_vod_arc_is_not_resplit_by_token_overlap(self):
        """Token subclustering splits people piles into events. Run over an
        arc it would split the accusation from its own reply."""
        i_bypass = self.body.index("if is_vod_arc:\n                _subs = [sorted(")
        i_split = self.body.index("_subs = _semantic_subclusters(reports)")
        self.assertLess(i_bypass, i_split)

    def test_the_broadcast_position_reaches_the_reports(self):
        self.assertIn('rep["vod_offset"] = c.get("vod_offset")', self.body)

    def test_the_seven_day_sweep_is_deep_enough_to_find_them(self):
        self.assertIn('"7d": int(spec.get("story_top_vod", 20))', self.body)


class TheDirectorIsToldTheOrder(unittest.TestCase):
    def test_a_one_broadcast_set_is_labelled_and_timestamped(self):
        from third_capture import story_director as sd
        reps = [{"source_id": "a", "channel": "jynxzi", "duration_s": 30,
                 "date": "2026-09-22", "summary": "s", "vod_offset": 3725}]
        self.assertIn("broadcast_at=1h02m05s", sd._fmt_reports(reps))

    def test_the_director_keeps_its_veto(self):
        """Being one broadcast is not being a story. §8 still decides."""
        src = (ROOT / "third_capture" / "story_director.py").read_text()
        self.assertIn("do not assume they do", src)


if __name__ == "__main__":
    unittest.main()
