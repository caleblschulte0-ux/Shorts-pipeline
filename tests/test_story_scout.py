"""The story arm uses its brain to find stories — across a month, across streams.

Operator, 2026-09-22: "Twitch isn't gonna hand them to you on a silver
platter ... these are gonna have to be from over extended periods of time,
more than one stream sometimes. Sometimes they'll be from one stream. The
thing needs to use its brain."

Every mechanical grouping the arm had matched WORDS. Measured on three
stories in the channel's own log that week (titles only):

    Wolverine suit   built -> revealed -> the controversy
                     old matcher kept [2, 1]: dropped the payoff
    Brickbois        Lang's audition (Buddha) -> Kevin (Soda) -> the record
                     old matcher kept [1, 1, 1]: no story
    Rug pull         promised the coin will pump -> loses $800
                     old matcher kept [1, 1]: they share only "buddha"

So a scout brain reads the whole lookback window as a catalogue and
PROPOSES stories; the director still DECIDES, with transcripts and frames,
§8 unchanged. The scout never sees a clip — it is never trusted on its own.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from third_capture import storyline as sl               # noqa: E402
from third_capture import story_director as sd          # noqa: E402


def _log_clip(slug, title, ch, date, posted=True):
    return {"source_url": f"https://www.twitch.tv/{ch}/clip/{slug}",
            "title": title, "channel": ch, "date": date, "posted": posted}


def _pool_clip(slug, title, ch, date, views, vid=None, off=None):
    return {"source_url": f"https://www.twitch.tv/{ch}/clip/{slug}",
            "title": title, "channel": ch, "date": date, "views": views,
            "posted": False, "video_id": vid, "vod_offset": off}


class TheCatalogueCoversTheWholeWindow(unittest.TestCase):
    def test_posted_history_reaches_back_past_a_flood_of_rejections(self):
        """'Most recent N' reached back four days: ~17 rejected clips a day
        crowded out every earlier chapter."""
        corpus = [_log_clip(f"old{i}", f"Old chapter number {i}", "kai",
                            "2026-08-25") for i in range(3)]
        corpus += [_log_clip(f"rej{i}", f"Rejected clip about thing {i}",
                             "kai", "2026-09-22", posted=False)
                   for i in range(300)]
        lines, ids = sl.build_catalogue(corpus, max_fresh=10, max_history=40)
        dates = {c["date"] for c in ids.values()}
        self.assertIn("2026-08-25", dates,
                      "the month-old chapters fell out of the catalogue")

    def test_titles_that_say_nothing_are_left_out(self):
        corpus = [_log_clip("a", "?", "kai", "2026-09-22", posted=False),
                  _log_clip("b", "truth bomb", "kai", "2026-09-22",
                            posted=False),
                  _log_clip("c", "Kai Reveals His Custom Suit", "kai",
                            "2026-09-21", posted=False)]
        lines, _ = sl.build_catalogue(corpus)
        text = "\n".join(lines)
        self.assertIn("Kai Reveals His Custom Suit", text)
        self.assertNotIn("| ? ", text)
        self.assertNotIn("truth bomb", text)

    def test_a_clip_in_both_keeps_the_authored_title_and_the_vod_position(self):
        corpus = [_log_clip("x", "Kai Reveals His Custom Suit", "kai",
                            "2026-09-21"),
                  _pool_clip("x", "LMAOOO", "kai", "2026-09-21", 5000,
                             vid="v7", off=3600)]
        lines, ids = sl.build_catalogue(corpus)
        self.assertEqual(len(lines), 1)
        self.assertIn("Kai Reveals His Custom Suit", lines[0])
        self.assertIn("vod=v7@1:00", lines[0])
        self.assertIn("5.0k", lines[0])

    def test_lines_run_in_time_order_with_short_ids(self):
        corpus = [_log_clip("b", "Second thing happens", "kai", "2026-09-21"),
                  _log_clip("a", "First thing happens", "kai", "2026-09-18")]
        lines, ids = sl.build_catalogue(corpus)
        self.assertTrue(lines[0].startswith("C1 | 2026-09-18"))
        self.assertEqual(set(ids), {"C1", "C2"})


class TheScoutProposesAndIsCheckedStructurally(unittest.TestCase):
    IDS = {f"C{i}" for i in range(1, 20)}
    LINES = [f"C{i} | 2026-09-{i:02d} | kai | - | clip {i}" for i in range(1, 20)]

    def _scout(self, answer):
        with mock.patch.object(sd, "_brain", return_value=answer):
            return sd.scout_stories(self.LINES, self.IDS)

    def test_a_good_proposal_survives(self):
        got = self._scout({"stories": [{"members": ["C3", "C9", "C14"],
                                        "premise": "p", "why_connected": "w",
                                        "shape": "multi_stream"}]})
        self.assertEqual(got[0]["members"], ["C3", "C9", "C14"])

    def test_an_invented_clip_is_refused(self):
        self.assertEqual(self._scout({"stories": [
            {"members": ["C3", "C999"], "premise": "p"}]}), [])

    def test_one_clip_is_not_a_story(self):
        self.assertEqual(self._scout({"stories": [
            {"members": ["C3", "C3"], "premise": "p"}]}), [])

    def test_a_pile_is_not_a_story(self):
        self.assertEqual(self._scout({"stories": [
            {"members": [f"C{i}" for i in range(1, 9)], "premise": "p"}]}), [])

    def test_at_most_three_are_kept(self):
        many = {"stories": [{"members": [f"C{i}", f"C{i + 1}"], "premise": "p"}
                            for i in range(1, 12, 2)]}
        self.assertEqual(len(self._scout(many)), 3)

    def test_no_brain_or_garbage_means_no_proposals_not_a_crash(self):
        for bad in (None, "text", {"stories": "no"}, {"stories": [None, 7]},
                    {}):
            with self.subTest(answer=bad):
                self.assertEqual(self._scout(bad), [])


class TheDirectorKeepsTheVeto(unittest.TestCase):
    def test_the_hypothesis_is_labelled_as_one(self):
        seen = {}

        def brain(user, system, **kw):
            seen["user"] = user
            return {"is_story": False, "why_not": "footage does not show it"}

        reps = [{"source_id": s, "channel": "kai", "duration_s": 30,
                 "date": "2026-09-18", "summary": "x"} for s in ("a", "b")]
        with mock.patch.object(sd, "_brain", side_effect=brain):
            self.assertIsNone(sd.plan_story(reps, None,
                                            hypothesis="Kai builds a suit"))
        self.assertIn("Treat it as a HYPOTHESIS", seen["user"])
        self.assertIn("the scout never saw the clips", seen["user"])

    def test_multi_stream_sources_are_not_called_one_broadcast(self):
        """The one-broadcast note used to fire whenever every source had a
        position. Scouted multi-stream stories have positions too — in
        DIFFERENT broadcasts."""
        seen = {}

        def brain(user, system, **kw):
            seen["user"] = user
            return None

        reps = [{"source_id": s, "channel": "kai", "duration_s": 30,
                 "date": "2026-09-18", "summary": "x", "vod_offset": 100,
                 "video_id": v} for s, v in (("a", "v1"), ("b", "v2"))]
        with mock.patch.object(sd, "_brain", side_effect=brain):
            sd.plan_story(reps, None)
        self.assertNotIn("ONE BROADCAST", seen["user"])

    def test_one_shared_broadcast_is_still_called_one(self):
        seen = {}

        def brain(user, system, **kw):
            seen["user"] = user
            return None

        reps = [{"source_id": s, "channel": "kai", "duration_s": 30,
                 "date": "2026-09-18", "summary": "x", "vod_offset": o,
                 "video_id": "v1"} for s, o in (("a", 100), ("b", 400))]
        with mock.patch.object(sd, "_brain", side_effect=brain):
            sd.plan_story(reps, None)
        self.assertIn("ONE BROADCAST", seen["user"])


class TheDirectorsReasonIsKept(unittest.TestCase):
    """2026-09-23: the director turned down all three scouted stories and the
    record said only "director judged: not a story" — the `why_not` it is
    asked for was thrown away."""

    def _plan(self, answer):
        reps = [{"source_id": s, "channel": "kai", "duration_s": 30,
                 "date": "2026-09-18", "summary": "x"} for s in ("a", "b")]
        with mock.patch.object(sd, "_brain", return_value=answer):
            sd.plan_story(reps, None)
        return sd.last_rejection()

    def test_the_why_not_reaches_the_record(self):
        rej = self._plan({"is_story": False,
                          "why_not": "the second clip is a different game"})
        self.assertIn("the second clip is a different game", rej["why"])

    def test_it_is_still_classified_editorial(self):
        rej = self._plan({"is_story": False, "why_not": "no payoff shown"})
        self.assertTrue(rej["editorial"])

    def test_a_missing_why_not_still_records_the_verdict(self):
        rej = self._plan({"is_story": False})
        self.assertIn("not a story", rej["why"])


class TheSlotUsesTheScoutFirst(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src = (ROOT / "scripts" / "run_third.py").read_text()
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "_story_attempt")
        cls.body = ast.get_source_segment(src, fn)

    def test_scouted_stories_are_offered_first(self):
        """The scout's best proposal is the first candidate; after that the
        scout and the VOD arcs take turns (2026-09-23: the scout's three
        took every slot and 174 arcs went unexamined)."""
        i_first = self.body.index("_mixed.append(scouted[i])")
        i_vod = self.body.index("_mixed.append(vod_arcs[i])")
        self.assertLess(i_first, i_vod)
        self.assertIn("clusters = _mixed + storyline.find_clusters(", self.body)

    def test_the_candidate_budget_is_six(self):
        self.assertIn('spec.get("story_max_clusters", 6)', self.body)

    def test_the_catalogue_is_built_from_the_whole_corpus(self):
        self.assertIn("storyline.build_catalogue(corpus)", self.body)

    def test_a_scouted_story_is_not_resplit_by_the_week_window(self):
        i_scouted = self.body.index("elif is_scouted:\n                # The scout's grouping")
        i_split = self.body.index("_subs = _semantic_subclusters(reports)")
        self.assertLess(i_scouted, i_split)

    def test_the_scouts_premise_reaches_the_director(self):
        self.assertIn("hypothesis=(", self.body)

    def test_the_same_story_is_not_analysed_twice(self):
        self.assertIn("storyline.near_dup(urls_, _members_seen)", self.body)

    def test_what_the_scout_proposed_is_recorded(self):
        self.assertIn('"scouted": [{"premise"', self.body)



class ARetryDoesNotRepeatTheStory(unittest.TestCase):
    """`main` retries a failed slot up to MAX_SLOT_ATTEMPTS times and every
    retry re-entered the story branch — paying for the whole story search
    again (16 minutes for three candidates on 2026-09-23)."""

    def test_the_story_branch_requires_the_first_attempt(self):
        src = (ROOT / "scripts" / "run_third.py").read_text()
        fn = next(n for n in ast.walk(ast.parse(src))
                  if isinstance(n, ast.FunctionDef) and n.name == "process")
        body = ast.get_source_segment(src, fn)
        i_guard = body.index("and attempt == 1")
        i_call = body.index("_story_attempt(pkg, log, work, out_mp4,")
        self.assertLess(i_guard, i_call)


if __name__ == "__main__":
    unittest.main()
