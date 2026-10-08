"""A near-miss keeps its edit.

Lacy's Fortnite story scored 82 in story backtest 5 and died at clip QA.
In backtest 8 the director, asked again from scratch, called the same two
clips "not a story". Every judge here is a brain and none answers the same
way twice, so an edit the critic rated near the bar is kept, and the next
attempt repairs it instead of re-rolling the plan. It still has to pass
the same critic at the same 80.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_a_story_has_a_narrator_per_beat import _edl, _line  # noqa
from tests.test_a_story_is_repaired_before_it_is_dropped import (  # noqa
    EDL, URLS, _Harness, _review)
from third_capture import clip_memory as cm                     # noqa: E402
from third_capture import story_director                        # noqa: E402


def _reports():
    return [{"source_id": s, "channel": "rakai", "duration_s": d,
             "transcript_lines": "rakai lost the bag in the sewer"}
            for s, d in (("a", 30.0), ("b", 40.0), ("c", 25.0))]


class TheMemoryKeepsNearMisses(unittest.TestCase):
    def test_a_near_miss_is_kept_and_found_by_its_sources(self):
        mem = cm.empty()
        cm.keep_edit(mem, _edl(None), 76)
        self.assertEqual(cm.kept_edit(mem, ["a", "b", "c", "x"])["score"], 76)
        self.assertIsNone(cm.kept_edit(mem, ["a", "b"]),
                          "a source it needs is missing today")

    def test_a_weak_cut_is_not_kept(self):
        mem = cm.empty()
        cm.keep_edit(mem, _edl(None), cm.KEEP_MIN - 1)
        self.assertEqual(mem.get("kept_edits", []), [])

    def test_a_lower_score_never_replaces_a_higher_one(self):
        mem = cm.empty()
        cm.keep_edit(mem, _edl(None), 82)
        cm.keep_edit(mem, _edl(None), 72)
        self.assertEqual([k["score"] for k in mem["kept_edits"]], [82])

    def test_the_shelf_is_bounded_best_first(self):
        mem = cm.empty()
        for i in range(cm.KEEP_MAX + 5):
            e = _edl(None)
            e["beats"][0]["source_id"] = f"s{i}"
            cm.keep_edit(mem, e, 70 + i % 10)
        self.assertEqual(len(mem["kept_edits"]), cm.KEEP_MAX)
        scores = [k["score"] for k in mem["kept_edits"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_every_narrator_line_is_kept(self):
        mem = cm.empty()
        v = story_director.validate_edl(
            _edl([_line("Rakai lost the bag in the sewer.", 0),
                  _line("Rakai lost the bag in the sewer.", 2)]),
            {"a": 30.0, "b": 40.0, "c": 25.0})
        cm.keep_edit(mem, v, 80)
        back = story_director.revalidate(mem["kept_edits"][0]["edl"],
                                         _reports())
        self.assertEqual([n["over_beat"] for n in back["narration_lines"]],
                         [0, 2])


class ANearMissIsTriedAgain(unittest.TestCase):
    URLS = ["https://www.twitch.tv/lacy/clip/A", "https://www.twitch.tv/lacy/clip/B"]

    def test_a_near_miss_is_retried_then_skipped_like_any_refusal(self):
        mem = cm.empty()
        for _ in range(cm.KEEP_RETRIES):
            cm.note_story_tried(mem, self.URLS, why="76", rendered=True,
                                near=True)
            self.assertIsNone(cm.already_tried(mem, self.URLS))
        cm.note_story_tried(mem, self.URLS, why="76", rendered=True,
                            near=True)
        self.assertIsNotNone(cm.already_tried(mem, self.URLS),
                             "retries spent: skipped until a better edit")

    def test_a_far_miss_is_skipped_at_once(self):
        mem = cm.empty()
        cm.note_story_tried(mem, self.URLS, why="58", rendered=True)
        self.assertIsNotNone(cm.already_tried(mem, self.URLS))


class AKeptEditMeetsTodaysLaws(unittest.TestCase):
    def test_a_valid_kept_edit_comes_back(self):
        self.assertIsNotNone(story_director.revalidate(_edl(None),
                                                       _reports()))

    def test_a_kept_edit_is_held_to_todays_sources(self):
        r = _reports()
        r[2]["duration_s"] = 5.0          # the payoff beat ran 3-15s
        back = story_director.revalidate(_edl(None), r)
        self.assertLessEqual(back["beats"][2]["end"], 5.0)

    def test_a_kept_edit_whose_source_is_gone_is_refused(self):
        self.assertIsNone(story_director.revalidate(_edl(None),
                                                    _reports()[:1]))


class TheNextAttemptRepairsTheKeptEdit(_Harness):
    def test_the_director_is_not_asked_again(self):
        mem = cm.empty()
        cm.keep_edit(mem, dict(EDL), 82)
        with mock.patch.object(story_director, "revalidate",
                               side_effect=lambda e, r: dict(EDL)):
            led = self.run_attempt([_review(True, 85)], plan=None,
                                   memory=mem)
        self.assertIsNotNone(led, "the kept edit was rendered and passed")

    def test_a_refused_render_keeps_its_best_edit(self):
        mem = cm.empty()
        self.run_attempt([_review(False, 72), _review(False, 76),
                          _review(False, 74)], memory=mem)
        self.assertEqual(mem["kept_edits"][0]["score"], 76)
        self.assertEqual(sorted(mem["kept_edits"][0]["sources"]),
                         sorted(URLS))

    def test_the_bar_does_not_move(self):
        mem = cm.empty()
        cm.keep_edit(mem, dict(EDL), 82)
        with mock.patch.object(story_director, "revalidate",
                               side_effect=lambda e, r: dict(EDL)):
            led = self.run_attempt([_review(True, 78), _review(False, 70),
                                    _review(False, 71)], memory=mem)
        self.assertIsNone(led)


if __name__ == "__main__":
    unittest.main()
