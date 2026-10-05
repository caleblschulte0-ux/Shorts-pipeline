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
                    spec_extra=None, cluster=None, plan=None):
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
                              return_value=[json.loads(json.dumps(
                                  cluster or CLUSTER))]),
            mock.patch.object(storyline, "find_clusters", return_value=[]),
            mock.patch.object(story_director, "scout_stories",
                              return_value=[]),
            mock.patch.object(scene_analysis, "analyze_source",
                              side_effect=lambda src, meta, *a, **k:
                              _report(meta["source_url"])),
            mock.patch.object(story_director, "plan_story",
                              return_value=(dict(EDL) if plan is None
                                            else plan)),
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


class ARefusalCoversTheWholeCandidate(_Harness):
    """2026-10-03: a broadcast arc with one clip that could not be read was
    refused in story slot 1 and downloaded, analysed and refused AGAIN in
    slot 2 — the refusal had remembered only the clips that were read, so
    the unreadable one made the same arc look new."""

    def test_an_unreadable_member_does_not_make_the_arc_new(self):
        dead = "https://www.twitch.tv/soda/clip/Dead"
        cl = json.loads(json.dumps(CLUSTER))
        cl["clips"].append({"source_url": dead, "title": "x",
                            "channel": "soda", "date": "2026-10-02",
                            "video_id": "v1", "vod_offset": 300.0})
        calls = {"n": 0}

        def pf(path):
            calls["n"] += 1
            return ["source only 3.0s"] if calls["n"] == 3 else []
        with mock.patch.object(story_director, "last_rejection",
                               return_value={"why": "director judged: not a "
                                             "story — unrelated moments",
                                             "editorial": True}):
            self.run_attempt([], cluster=cl, preflight=pf, plan=False)
        self.assertIsNotNone(
            clip_memory.already_tried(self.rt._CLIP_MEMORY, URLS + [dead]),
            "the same arc, dead clip included, is the same refused arc")


class TheReviserSeesWhatTheDirectorSaw(unittest.TestCase):
    def test_every_source_transcript_reaches_the_revision(self):
        seen = {}

        def brain(user, system, **kw):
            seen["user"] = user
            return None
        reps = [{"source_id": f"s{i}", "channel": "kai", "duration_s": 60,
                 "summary": "x", "transcript_lines":
                 ("filler " * 900) + f"LINE-FROM-SOURCE-{i}"}
                for i in range(3)]
        with mock.patch.object(story_director, "_brain", side_effect=brain):
            story_director.revise_edl(
                dict(EDL), [{"type": "missing_context", "at": 0.0,
                             "fix": "open on the accusation"}], reps)
        for i in range(3):
            self.assertIn(f"LINE-FROM-SOURCE-{i}", seen["user"])


REGGIE = [{"source_id": "a", "channel": "kaicenat", "duration_s": 60,
           "summary": "Kai reads Reggie's text claiming Kai ignored his call",
           "people": ["Kai Cenat", "Reggie"],
           "transcript_lines": "[0.0-6.0] Reggie said I ignored his call at "
                               "2:32 and that I left him on read"},
          {"source_id": "b", "channel": "kaicenat", "duration_s": 60,
           "summary": "Kai shows the call history screenshot",
           "people": ["Kai Cenat"],
           "transcript_lines": "[0.0-5.0] look at the call history, he's "
                               "lying"}]


def _with_narration(text):
    e = {"is_story": True, "premise": "p", "central_question": "q?",
         "structure": "chronological", "title": "t",
         "hook_overlay": "he says kai ignored him",
         "beats": [{"source_id": "a", "start": 0, "end": 10, "role": "setup",
                    "purpose": "the claim"},
                   {"source_id": "b", "start": 0, "end": 10,
                    "role": "payoff", "purpose": "the proof"}]}
    e["narration"] = {"text": text, "over_beat": 0,
                      "essential_because": "source a, 0-6s"}
    return e


class TheRepairMaySayWhatTheFootageSays(unittest.TestCase):
    """2026-10-03 and 10-04: the critic refused the Kai Cenat / Reggie story
    on three runs because "the opening never says what Reggie is accused
    of" — and the reviser was not allowed to say it. It may now add ONE
    narration line, and code drops a line the sources do not support."""

    def test_the_prompt_allows_narration_for_missing_context(self):
        p = story_director._REVISE_SYSTEM
        self.assertIn("missing_context", p)
        self.assertIn("narration", p)
        self.assertIn("ONLY what a source's transcript", p)

    def test_a_line_from_the_footage_is_grounded(self):
        self.assertTrue(story_director.narration_grounded(
            "Reggie claimed Kai ignored his call and left him on read.",
            REGGIE))

    def test_an_invented_line_is_not(self):
        self.assertFalse(story_director.narration_grounded(
            "Reggie stole Kai's championship ring during the tournament.",
            REGGIE))
        self.assertFalse(story_director.narration_grounded("", REGGIE))

    def _revise(self, text):
        with mock.patch.object(story_director, "_brain",
                               return_value=_with_narration(text)):
            return story_director.revise_edl(
                _with_narration(""), [{"type": "missing_context", "at": 0.0,
                                       "fix": "say what Reggie claims"}],
                REGGIE)

    def test_the_reviser_keeps_a_grounded_line(self):
        out = self._revise("Reggie claimed Kai ignored his call.")
        self.assertIsNotNone(out)
        self.assertEqual(out["narration"]["text"],
                         "Reggie claimed Kai ignored his call.")

    def test_the_reviser_loses_an_invented_line_but_keeps_the_cut(self):
        out = self._revise("Reggie stole Kai's championship ring yesterday.")
        self.assertIsNotNone(out, "the cut survives")
        self.assertFalse(out.get("narration"))

    def test_the_directors_own_narration_meets_the_same_floor(self):
        with mock.patch.object(story_director, "_brain",
                               return_value=_with_narration(
                                   "Reggie stole Kai's championship ring.")):
            out = story_director.plan_story(REGGIE, None)
        self.assertIsNotNone(out)
        self.assertFalse(out.get("narration"))

    def test_narration_over_the_OPENING_beat_survives_validation(self):
        """`int(over_beat) or -1` made beat 0 into -1: every setup line was
        silently dropped before any of this existed."""
        out = story_director.validate_edl(
            _with_narration("Reggie claimed Kai ignored his call."),
            {"a": 60.0, "b": 60.0})
        self.assertEqual(out["narration"]["over_beat"], 0)


class TwoStoryAttemptsADay(unittest.TestCase):
    def test_the_template_asks_for_two_story_slots(self):
        tpl = json.loads((ROOT / "state" / "third_packages" /
                          "default_clip.json").read_text())
        self.assertEqual(tpl["story_count"], 2)


if __name__ == "__main__":
    unittest.main()
