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
       "beats": [{"source_id": URLS[0], "start": 0.0, "end": 10.0},
                 {"source_id": URLS[1], "start": 0.0, "end": 10.0}]}


def _report(url):
    return {"source_id": url, "channel": "soda", "duration_s": 30.0,
            "summary": "soda bets on the boss fight", "people": ["Soda"],
            "title": "bet", "words": [{"w": "bet", "s": 0.0, "e": 0.5}],
            "dialogue_beats": [], "visual_beats": []}


def _review(publish, score, fix="cut the dead air"):
    return {"publish": publish, "story_score": score,
            "stranger_summary": "Soda bets everything and loses it.",
            "payoff_at": 30.0 if publish else None,
            "problems": [] if (publish and score >= 80) else
            [{"type": "pacing", "at": 4.0, "fix": fix}]}


class _Harness(unittest.TestCase):
    def run_attempt(self, reviews, *, preflight=lambda p: [],
                    spec_extra=None, cluster=None, plan=None,
                    clusters=None, memory=None, qa=None):
        rt = _load_rt()
        self.rt = rt
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        rt.EVENTS_FILE = tmp / "events.json"
        rt._STORY_POOL = None
        rt._CLIP_MEMORY = memory or clip_memory.empty()
        rt._JUDGES.clear()
        self.revisions = 0
        self.revise_fixes = []

        def revise(edl, problems, reports, **_k):
            self.revisions += 1
            self.revise_fixes.append([p["fix"] for p in problems])
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
            (mock.patch.object(clip_qa, "review", side_effect=list(qa))
             if qa else
             mock.patch.object(clip_qa, "review", return_value={
                 "verdict": "pass", "problems": [], "vision": {}})),
            mock.patch.object(storyline, "find_vod_arcs",
                              return_value=json.loads(json.dumps(
                                  clusters or [cluster or CLUSTER]))),
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
        # the table read is its own test file; here every review is a
        # render's (test_a_plan_is_read_before_it_is_rendered)
        spec = {"kind": "twitch_clip", "sources": {"twitch": ["soda"]},
                "story_table_reads": 0}
        spec.update(spec_extra or {})
        return rt._story_attempt({"capture": spec}, {"posted": {}},
                                 tmp, tmp / "out.mp4", "clip-x-1")

    def verdicts(self):
        return self.rt._JUDGES.get("story_director", {}).get("clusters", [])


class RepairBeforeDrop(_Harness):
    def test_a_story_the_second_repair_fixes_is_posted(self):
        led = self.run_attempt([_review(False, 52), _review(False, 61),
                                _review(True, 84)])
        self.assertIsNotNone(led, "two repairs got it to a pass — post it")
        self.assertEqual(led["revision_count"], 2)
        self.assertEqual(led["narrative_score"], 84)
        self.assertEqual(led["narrative_summary"],
                         "Soda bets everything and loses it.")

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


class APassUnderTheFloorDoesNotShip(_Harness):
    """2026-10-05: the critic passed the Cinna story at 74 and it shipped
    with no payoff. It had passed every story it was ever shown (66-80); the
    one that held viewers was the 80. A story ships at `story_min_score`."""

    def test_a_critic_pass_at_74_is_repaired_not_shipped(self):
        led = self.run_attempt([_review(True, 74), _review(True, 76),
                                _review(True, 77)])
        self.assertIsNone(led)
        self.assertEqual(self.revisions, 2, "it was repaired toward the bar")
        v = [x for x in self.verdicts() if x["outcome"] == "narrative_failed"]
        self.assertIn("under the 80 floor", v[0]["why"])

    def test_repaired_up_to_the_floor_it_ships(self):
        led = self.run_attempt([_review(True, 74), _review(True, 82)])
        self.assertIsNotNone(led)
        self.assertEqual(led["narrative_score"], 82)

    def test_the_floor_is_configurable(self):
        led = self.run_attempt([_review(True, 74)],
                               spec_extra={"story_min_score": 70})
        self.assertIsNotNone(led)


class NoPayoffNoStory(unittest.TestCase):
    """Code may only ADD blocks: a critic pass that cannot name the second
    the story pays off, or retell it in a sentence, is a fail."""

    def _review(self, out):
        with mock.patch.object(story_director, "_brain", return_value=out):
            edl = story_director.validate_edl(_with_narration(""),
                                              {"a": 60.0, "b": 60.0})
            return story_director.review_rough_cut(edl, "", None, 40.0)

    def test_publish_without_a_payoff_is_a_fail(self):
        r = self._review({"publish": True, "story_score": 85,
                          "stranger_summary": "She gets ditched.",
                          "payoff_at": None, "problems": []})
        self.assertFalse(r["publish"])
        self.assertEqual(r["problems"][-1]["type"], "weak_payoff")

    def test_publish_without_a_retelling_is_a_fail(self):
        r = self._review({"publish": True, "story_score": 85,
                          "stranger_summary": "", "payoff_at": 31.0,
                          "problems": []})
        self.assertFalse(r["publish"])

    def test_a_named_payoff_passes_through(self):
        r = self._review({"publish": True, "story_score": 85,
                          "stranger_summary": "She gets ditched and caught.",
                          "payoff_at": 31.0, "problems": []})
        self.assertTrue(r["publish"])
        self.assertEqual(r["payoff_at"], 31.0)

    def test_the_rubric_asks_for_both(self):
        p = story_director._REVIEW_SYSTEM
        self.assertIn("stranger_summary", p)
        self.assertIn("payoff_at", p)


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
         "beats": [{"source_id": "a", "start": 0, "end": 10, "link": "so", "role": "setup",
                    "purpose": "the claim"},
                   {"source_id": "b", "start": 0, "end": 10,
                    "link": "so", "role": "payoff", "purpose": "the proof"}]}
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


class SkippedCandidatesDoNotSpendTheBudget(_Harness):
    """2026-10-05 story backtest: attempts 3 and 4 examined almost nothing
    new — the six-candidate budget was spent on already-refused candidates
    that were skipped in a millisecond."""

    def test_a_fresh_candidate_behind_seven_refused_ones_is_examined(self):
        mem = clip_memory.empty()
        refused = []
        for i in range(7):
            urls = [f"https://www.twitch.tv/x/clip/Old{i}a",
                    f"https://www.twitch.tv/x/clip/Old{i}b"]
            clip_memory.note_story_tried(mem, urls, why="no change")
            refused.append({"who": ["x"], "kind": "vod_arc",
                            "video_id": f"v{i}",
                            "clips": [{"source_url": u, "title": "t",
                                       "channel": "x", "date": "2026-10-01"}
                                      for u in urls]})
        led = self.run_attempt([_review(True, 85)], memory=mem,
                               clusters=refused + [json.loads(
                                   json.dumps(CLUSTER))])
        self.assertIsNotNone(led, "the fresh candidate was never reached")


class NoSecondOfTheBroadcastPlaysTwice(unittest.TestCase):
    """The 2026-10-05 backtest's Kai Cenat cut ended one clip at 24.1-29.9s
    and opened the next at 0-9.8s — and the two clips overlap in the
    broadcast, so "You kept talking about proof, right?" played twice back
    to back. The critic named it on 10-04, 10-05 and in the backtest."""

    POS = {"A": ("vod1", 100.0), "B": ("vod1", 125.0),
           "C": ("vod2", 125.0)}

    def _beats(self, *spec):
        return [{"source_id": s, "start": a, "end": b, "link": "so", "role": "setup",
                 "purpose": "p"} for s, a, b in spec]

    def test_the_kai_overlap_is_trimmed(self):
        rs = []
        out = story_director._no_replayed_seconds(
            self._beats(("A", 24.1, 29.9), ("B", 0.0, 9.8)), self.POS, rs)
        self.assertEqual([(b["source_id"], b["start"], b["end"])
                          for b in out],
                         [("A", 24.1, 29.9), ("B", 4.9, 9.8)])
        self.assertIn("so no second of the broadcast plays twice", rs[0])

    def test_a_beat_entirely_inside_one_already_shown_is_dropped(self):
        rs = []
        out = story_director._no_replayed_seconds(
            self._beats(("A", 20.0, 40.0), ("B", 0.0, 10.0)), self.POS, rs)
        self.assertEqual([b["source_id"] for b in out], ["A"])
        self.assertIn("dropped", rs[0])

    def test_different_broadcasts_never_collide(self):
        rs = []
        out = story_director._no_replayed_seconds(
            self._beats(("A", 24.1, 29.9), ("C", 0.0, 9.8)), self.POS, rs)
        self.assertEqual(len(out), 2)
        self.assertEqual(rs, [])

    def test_two_beats_over_the_same_seconds_of_one_clip(self):
        rs = []
        out = story_director._no_replayed_seconds(
            self._beats(("Z", 0.0, 10.0), ("Z", 5.0, 20.0)), {}, rs)
        self.assertEqual([(b["start"], b["end"]) for b in out],
                         [(0.0, 10.0), (10.0, 20.0)])

    def test_positions_come_from_the_reports_incl_vod_windows(self):
        pos = story_director._positions([
            {"source_id": "A", "video_id": "v", "broadcast_t0": 940.0},
            {"source_id": "B", "video_id": None, "broadcast_t0": None}])
        self.assertEqual(pos["A"], ("v", 940.0))
        self.assertEqual(pos["B"], ("src:B", 0.0))

    def test_the_run_records_where_each_source_starts(self):
        src = (ROOT / "scripts" / "run_third.py").read_text()
        self.assertIn('rep["broadcast_t0"] = vod.get("vod_start_s")', src)
        self.assertIn('rep.setdefault("broadcast_t0", c.get("vod_offset"))',
                      src)


def _w(text, t0, step=0.4):
    return [{"w": w, "s": round(t0 + i * step, 2),
             "e": round(t0 + i * step + 0.3, 2)}
            for i, w in enumerate(text.split())]


class NoLineIsSaidTwiceAcrossASeam(unittest.TestCase):
    """Backtest #2 (2026-10-05): the scout's Kai cut came from the month of
    posts, which carry no broadcast positions, and still said "You kept
    talking about proof, right?" twice across the seam."""

    WORDS = {
        "A": _w("you are so disrespectful you kept talking about proof right",
                0.0),
        "B": _w("you kept talking about proof right so let's bring the proof",
                0.0),
    }

    def _beats(self, *spec):
        return [{"source_id": s, "start": a, "end": b, "link": "so", "role": "setup",
                 "purpose": "p"} for s, a, b in spec]

    def test_the_repeated_opening_is_trimmed(self):
        rs = []
        out = story_director._no_repeated_lines(
            self._beats(("A", 0.0, 4.5), ("B", 0.0, 5.0)), self.WORDS, rs)
        # "you kept talking about proof right" = 6 words; B now starts after
        self.assertEqual(out[1]["start"], round(self.WORDS["B"][5]["e"] + 0.05, 2))
        self.assertIn("opened on the 6 words", rs[0])

    def test_three_shared_words_are_not_a_repeat(self):
        rs = []
        words = {"A": _w("we went to the shop", 0.0),
                 "B": _w("to the shop and then home", 0.0)}
        out = story_director._no_repeated_lines(
            self._beats(("A", 0.0, 2.5), ("B", 0.0, 3.0)), words, rs)
        self.assertEqual(out[1]["start"], 0.0)
        self.assertEqual(rs, [])

    def test_validate_edl_applies_it(self):
        edl = _with_narration("")
        edl.pop("narration")
        edl["beats"] = [dict(edl["beats"][0], source_id="A", start=0, end=4.5),
                        dict(edl["beats"][1], source_id="B", start=0, end=5.0)]
        rs = []
        out = story_director.validate_edl(edl, {"A": 10.0, "B": 10.0},
                                          reasons=rs, words=self.WORDS)
        self.assertGreater(out["beats"][1]["start"], 2.0)


class TheOpeningSaysWhoAndWhat(unittest.TestCase):
    """Backtest #2: 'missing_context' was the critic's first complaint on
    13 of 21 cuts — Pokimane's 'my baby' never named as her cat, CaseOh's
    challenge never named, Reggie never introduced."""

    def test_the_director_is_told_the_first_three_seconds_rule(self):
        p = story_director._PLAN_SYSTEM
        self.assertIn("THE FIRST THREE SECONDS TELL A STRANGER WHO AND WHAT",
                      p)
        self.assertIn("SITUATION in plain words", p)

    def test_narration_is_no_longer_discouraged_for_who_and_what(self):
        p = story_director._PLAN_SYSTEM
        self.assertNotIn("Usually omit.", p.split("narration:")[1][:600])
        self.assertIn("never says WHO or WHAT", p)


class RepairsStartFromTheBestCut(_Harness):
    """Third backtest (2026-10-06): repair chains got WORSE as they went —
    CaseOh 70 -> 66 -> 58 — because each repair rewrote the last repair."""

    def test_a_worse_repair_is_not_the_base_for_the_next(self):
        self.run_attempt([_review(False, 70, "fix A"),
                          _review(False, 66, "fix B"),
                          _review(False, 58, "fix C")])
        self.assertEqual(self.revise_fixes, [["fix A"], ["fix A"]],
                         "the second repair works from the 70, not the 66")

    def test_a_better_repair_becomes_the_base(self):
        self.run_attempt([_review(False, 60, "fix A"),
                          _review(False, 72, "fix B"),
                          _review(False, 74, "fix C")])
        self.assertEqual(self.revise_fixes, [["fix A"], ["fix B"]])


class TheStoryEndsWhereTheSentenceEnds(unittest.TestCase):
    """Third backtest: the one cut over the bar still ended on 'I have
    them' — "the final line is cut mid-phrase"."""

    W = {"E": _w("this is better than my bed I have them", 10.0)}

    def _last(self, end, dur=60.0):
        beats = [{"source_id": "E", "start": 9.0, "end": end,
                  "link": "so", "role": "payoff", "purpose": "p"}]
        rs = []
        out = story_director._finish_the_sentence(beats, self.W,
                                                  {"E": dur}, rs)
        return out[-1]["end"], rs

    def test_mid_word_runs_to_the_end_of_the_breath(self):
        # words every 0.4s, 0.3s long: one breath; last word ends 13.5
        end, rs = self._last(11.1)
        self.assertEqual(end, 13.6)
        self.assertIn("mid-sentence", rs[0])

    def test_never_more_than_three_seconds(self):
        words = {"E": _w(" ".join(["word"] * 30), 10.0)}
        beats = [{"source_id": "E", "start": 9.0, "end": 10.1,
                  "link": "so", "role": "payoff", "purpose": "p"}]
        out = story_director._finish_the_sentence(beats, words,
                                                  {"E": 60.0}, [])
        self.assertLessEqual(out[-1]["end"], 10.1 + 3.0 + 0.1)

    def test_never_past_the_source(self):
        end, _ = self._last(11.1, dur=12.0)
        self.assertLessEqual(end, 12.0)

    def test_an_end_in_a_pause_is_left_alone(self):
        words = {"E": _w("done", 10.0) + _w("later", 14.0)}
        beats = [{"source_id": "E", "start": 9.0, "end": 11.0,
                  "link": "so", "role": "payoff", "purpose": "p"}]
        rs = []
        out = story_director._finish_the_sentence(beats, words,
                                                  {"E": 60.0}, rs)
        self.assertEqual(out[-1]["end"], 11.0)
        self.assertEqual(rs, [])

    def test_a_source_that_ends_mid_sentence_is_cut_back(self):
        # backtest #4: "this is really better than my bed. I have them" and
        # the clip ends — nothing to run on to, so end after "bed."
        words = {"E": _w("this is really better than my bed. I have them",
                         10.0)}
        beats = [{"source_id": "E", "start": 9.0, "end": 13.6,
                  "link": "so", "role": "payoff", "purpose": "p"}]
        rs = []
        out = story_director._finish_the_sentence(beats, words,
                                                  {"E": 13.6}, rs)
        self.assertEqual(out[-1]["end"], 12.8)       # "bed." ends 12.7
        self.assertIn("cut back", rs[0])

    def test_a_source_that_stops_on_its_last_word_is_not_a_pause(self):
        # backtest #6: the clip's own last word "them" counted as an ending
        # and the cut ended on "I have them" again
        words = {"E": _w("this is really better than my bed. I have them",
                         10.0)}                       # "them" ends 13.9
        beats = [{"source_id": "E", "start": 9.0, "end": 14.0,
                  "link": "so", "role": "payoff", "purpose": "p"}]
        rs = []
        out = story_director._finish_the_sentence(beats, words,
                                                  {"E": 14.0}, rs)
        self.assertEqual(out[-1]["end"], 12.8)
        self.assertIn("cut back", rs[0])

    def test_a_last_word_followed_by_silence_is_an_ending(self):
        words = {"E": _w("this is really better than my bed I love it",
                         10.0)}                       # "it" ends 13.9
        beats = [{"source_id": "E", "start": 9.0, "end": 14.0,
                  "link": "so", "role": "payoff", "purpose": "p"}]
        out = story_director._finish_the_sentence(beats, words,
                                                  {"E": 16.0}, [])
        self.assertEqual(out[-1]["end"], 14.0)

    def test_punctuation_ends_a_sentence_inside_one_breath(self):
        words = {"E": _w("this is really better than my bed. I have them "
                         "all over the house and the cats love them", 10.0)}
        beats = [{"source_id": "E", "start": 9.0, "end": 11.5,
                  "link": "so", "role": "payoff", "purpose": "p"}]
        out = story_director._finish_the_sentence(beats, words,
                                                  {"E": 60.0}, [])
        self.assertEqual(out[-1]["end"], 12.8)

    def test_never_cut_below_a_beat(self):
        words = {"E": _w("ok. and then I have them all", 10.0)}
        beats = [{"source_id": "E", "start": 9.5, "end": 12.2,
                  "link": "so", "role": "payoff", "purpose": "p"}]
        out = story_director._finish_the_sentence(beats, words,
                                                  {"E": 12.2}, [])
        self.assertEqual(out[-1]["end"], 12.2, "'ok.' is under 1.5s in")


class EverySlotTriesAStory(unittest.TestCase):
    """Operator, 2026-10-07: "this channel needs to be stories and edits
    not just raw clips". Every slot tries the story arm first; the clip arm
    is the fallback, and story_budget_min keeps the searches from eating
    the time the day's clips need."""

    def test_the_template_makes_every_slot_a_story_slot(self):
        from shared import channel_registry
        tpl = json.loads((ROOT / "state" / "third_packages" /
                          "default_clip.json").read_text())
        self.assertGreaterEqual(tpl["story_count"],
                                channel_registry.target_count("third"))

    def test_the_story_budget_leaves_the_clips_time(self):
        rt = _load_rt()
        tpl = json.loads((ROOT / "state" / "third_packages" /
                          "default_clip.json").read_text())
        cap = float(tpl["capture"]["story_budget_min"])
        self.assertLess(cap, rt._BUDGET_MIN - 20)

    def test_it_reaches_back_ninety_days(self):
        tpl = json.loads((ROOT / "state" / "third_packages" /
                          "default_clip.json").read_text())
        self.assertGreaterEqual(tpl["capture"]["story_lookback_days"], 90)
        self.assertGreater(tpl["capture"]["story_top_90d"], 0)


if __name__ == "__main__":
    unittest.main()


class ARejectedRevisionIsToldWhy(unittest.TestCase):
    """2026-10-07: a 66 and a 70 ended "after 0 revision(s)" because the
    reviser's EDL broke an edit law and came back None, silently."""

    def test_the_reviser_hears_what_it_broke_and_tries_once_more(self):
        calls = []
        bad = _with_narration("Reggie claimed Kai ignored his call.")
        bad["beats"] = [dict(bad["beats"][0], source_id="nope")]
        good = _with_narration("Reggie claimed Kai ignored his call.")

        def brain(user, system, **kw):
            calls.append(user)
            return bad if len(calls) == 1 else good
        with mock.patch.object(story_director, "_brain", side_effect=brain):
            out = story_director.revise_edl(
                _with_narration(""), [{"type": "pacing", "at": 0.0,
                                       "fix": "trim the opening"}], REGGIE)
        self.assertIsNotNone(out)
        self.assertEqual(len(calls), 2)
        self.assertIn("REJECTED", calls[1])

    def test_it_does_not_loop(self):
        calls = []

        def brain(user, system, **kw):
            calls.append(user)
            return {"is_story": True, "beats": []}
        with mock.patch.object(story_director, "_brain", side_effect=brain):
            out = story_director.revise_edl(
                _with_narration(""), [{"type": "pacing", "at": 0.0,
                                       "fix": "x"}], REGGIE)
        self.assertIsNone(out)
        self.assertEqual(len(calls), 2)
