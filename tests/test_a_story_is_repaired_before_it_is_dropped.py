"""A rendered story is REPAIRED until the critic passes it — never shipped
without that pass — and every way a story dies is recorded.

2026-10-01 and 10-02: the only two stories the director accepted were
rendered, revised ONCE, scored 54 and 52 by the narrative critic and thrown
away; the problems the critic named were never written anywhere. 48 of the
59 story verdicts on record were "starved" with no reason. Operator,
2026-10-03: "Post a story." The answer is the explainer's — keep repairing
what the critic names, same critic, same `publish` bar — plus a second
story slot a day, and a record that says why each candidate died.

Driven through the REAL `_story_attempt`; only the downloads, the brains and
the renderer are stubbed.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from third_capture import (clip_edit, clip_memory, clip_qa,     # noqa: E402
                           scene_analysis, story_director, storyline)
from third_capture import story as story_mod                    # noqa: E402


def _load_rt():
    spec = importlib.util.spec_from_file_location(
        "run_third_repair", ROOT / "scripts" / "run_third.py")
    rt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rt)
    return rt


URLS = [f"https://www.twitch.tv/soda/clip/Part{i}" for i in (1, 2)]
CLUSTER = {"who": ["soda"], "kind": "vod_arc", "video_id": "v1",
           "clips": [{"source_url": u, "title": f"part {i}",
                      "channel": "soda", "date": "2026-10-02",
                      "video_id": "v1", "vod_offset": 100.0 * i}
                     for i, u in enumerate(URLS)]}
EDL = {"title": "Soda Loses The Bet", "hook_overlay": "he bet everything",
       "premise": "Soda bets and loses", "structure": "chronological",
       "beats": [{"source_id": URLS[0]}, {"source_id": URLS[1]}]}


def _report(url):
    return {"source_id": url, "channel": "soda", "duration_s": 30.0,
            "summary": "soda bets on the boss fight", "people": ["Soda"],
            "title": "bet", "words": [{"w": "bet", "s": 0.0, "e": 0.5}],
            "dialogue_beats": [], "visual_beats": []}


def _review(publish, score, fix="cut the dead air"):
    return {"publish": publish, "story_score": score,
            "problems": [] if publish else
            [{"type": "pacing", "at": 4.0, "fix": fix}]}


class _Harness(unittest.TestCase):
    def run_attempt(self, reviews, *, preflight=lambda p: [],
                    spec_extra=None):
        rt = _load_rt()
        self.rt = rt
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        rt.EVENTS_FILE = tmp / "events.json"
        rt._STORY_POOL = None
        rt._CLIP_MEMORY = clip_memory.empty()
        rt._JUDGES.clear()
        self.revisions = 0

        def revise(edl, problems, reports):
            self.revisions += 1
            return dict(EDL)

        clip = tmp / "c.mp4"
        clip.write_bytes(b"x")
        led = {"final_words": [], "duration_s": 40.0, "member_keys": URLS,
               "beats": [{"streamer": "soda"}], "n_beats": 2}
        patches = [
            mock.patch.object(clip_memory, "PATH", tmp / "mem.json"),
            mock.patch.object(clip_edit, "discover", return_value=[]),
            mock.patch.object(clip_edit, "download",
                              return_value={"path": str(clip)}),
            mock.patch.object(clip_qa, "preflight", side_effect=preflight),
            mock.patch.object(clip_qa, "contact_sheet", return_value=None),
            mock.patch.object(clip_qa, "review", return_value={
                "verdict": "pass", "problems": [], "vision": {}}),
            mock.patch.object(storyline, "find_vod_arcs",
                              return_value=[json.loads(json.dumps(CLUSTER))]),
            mock.patch.object(storyline, "find_clusters", return_value=[]),
            mock.patch.object(story_director, "scout_stories",
                              return_value=[]),
            mock.patch.object(scene_analysis, "analyze_source",
                              side_effect=lambda src, meta, *a, **k:
                              _report(meta["source_url"])),
            mock.patch.object(story_director, "plan_story",
                              return_value=dict(EDL)),
            mock.patch.object(story_director, "review_rough_cut",
                              side_effect=list(reviews)),
            mock.patch.object(story_director, "revise_edl",
                              side_effect=revise),
            mock.patch.object(story_mod, "render_story",
                              return_value=dict(led)),
        ]
        for p in patches:
            self.enterContext(p)
        spec = {"kind": "twitch_clip", "sources": {"twitch": ["soda"]}}
        spec.update(spec_extra or {})
        return rt._story_attempt({"capture": spec}, {"posted": {}},
                                 tmp, tmp / "out.mp4", "clip-x-1")

    def verdicts(self):
        return self.rt._JUDGES.get("story_director", {}).get("clusters", [])


class RepairBeforeDrop(_Harness):
    def test_a_story_the_second_repair_fixes_is_posted(self):
        led = self.run_attempt([_review(False, 52), _review(False, 61),
                                _review(True, 78)])
        self.assertIsNotNone(led, "two repairs got it to a pass — post it")
        self.assertEqual(led["revision_count"], 2)
        self.assertEqual(led["narrative_score"], 78)

    def test_the_critic_still_decides(self):
        """A high score without `publish` is still a no — the loop only
        repairs; it never lowers the bar."""
        led = self.run_attempt([_review(False, 52), _review(False, 88),
                                _review(False, 89)])
        self.assertIsNone(led)
        self.assertEqual(self.revisions, 2, "stops at story_revisions")

    def test_the_revision_budget_is_configurable(self):
        led = self.run_attempt([_review(False, 52), _review(False, 60)],
                               spec_extra={"story_revisions": 1})
        self.assertIsNone(led)
        self.assertEqual(self.revisions, 1)

    def test_a_dropped_story_says_what_the_critic_said(self):
        self.run_attempt([_review(False, 52, "the payoff is cut off"),
                          _review(False, 55, "the payoff is cut off"),
                          _review(False, 54, "the payoff is cut off")])
        v = [x for x in self.verdicts() if x["outcome"] == "narrative_failed"]
        self.assertEqual(len(v), 1)
        self.assertIn("[52, 55, 54]", v[0]["why"])
        self.assertIn("the payoff is cut off", v[0]["why"])

    def test_a_dropped_story_is_not_rerendered_by_the_next_slot(self):
        self.run_attempt([_review(False, 52), _review(False, 55),
                          _review(False, 54)])
        self.assertIsNotNone(
            clip_memory.already_tried(self.rt._CLIP_MEMORY, URLS))


class StarvationSaysWhy(_Harness):
    def test_preflight_failures_are_named_and_remembered(self):
        led = self.run_attempt([], preflight=lambda p: ["source only 4.0s"])
        self.assertIsNone(led)
        v = [x for x in self.verdicts() if x["outcome"] == "starved"]
        self.assertEqual(len(v), 1)
        self.assertIn("preflight:source only 4.0s", v[0]["why"])
        self.assertIsNotNone(
            clip_memory.already_tried(self.rt._CLIP_MEMORY, URLS),
            "clips too short today are too short tomorrow")


class TwoStoryAttemptsADay(unittest.TestCase):
    def test_the_template_asks_for_two_story_slots(self):
        tpl = json.loads((ROOT / "state" / "third_packages" /
                          "default_clip.json").read_text())
        self.assertEqual(tpl["story_count"], 2)


if __name__ == "__main__":
    unittest.main()
