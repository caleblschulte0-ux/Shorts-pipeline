"""THE REWRITE MAILBOX ASKS TODAY'S QUESTION — and only questions a rewrite can answer.

Doctor aaeb12de3ebd (restore explainer delivery), triage 2026-11-23. The
explainer posted 2 on 11-22 and 0 by 01:17Z on 11-23; the last run held 72
stories and the rewrite index listed 144 open requests. Read against the
queue that morning:

  * 48 requests carried hold reasons the run no longer gave — 14 still
    said "premise: no consequential number in the title or hook", a rule
    retired on 2026-11-17 — because `file_request` was idempotent on the
    story's WORDS and the same words held again for a NEW reason returned
    the old id and left the file alone.
  * 37 requests were for stories held `data:` (an illustrative source) that
    no rewrite can post, a quarter of ChatGPT's 10-per-firing cap.
  * 0 requests asked for the narration, while explainer_health named ten
    stories held `not_current` as readouts in six-plus runs each.

Held here, each failing on the old code:
  1. the same words held again REFRESH the open request with today's
     reasons (`refiled`), id unchanged, index `why` updated;
  2. a story held for its data files nothing and RETIRES its open asks
     (`unpostable`) — from a run result and from the backlog sweep;
  3. a `not_current` narration readout (or a hook under the floor) is
     filed as a `narration:` / `hook:` reason with the gate's word holds;
     a render-standard `not_current` is not;
  4. ChatGPT's answer must clear the narration doctrine (one number a beat)
     at the claim; the brain's retell/tighten path (`validate` default) is
     unchanged.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import rewrite_mailbox as RW                     # noqa: E402
from scripts import editorial_gate as EG                     # noqa: E402
from shared import pacing                                    # noqa: E402

# the proven fixture: a story the gate holds for WORD reasons on real data
from tests.test_a_held_story_is_reauthored_not_parked import (  # noqa: E402
    _story, GOOD_ANSWER)


class _Box(unittest.TestCase):
    def setUp(self):
        self.td = Path(tempfile.mkdtemp(prefix="rw-today-"))
        self.rewrites = self.td / "rewrites"
        self._p = [mock.patch.object(EG, "DATA_DIR", self.td),
                   mock.patch.object(EG, "beats_are_distinct",
                                     lambda sc: {"ok": True, "reasons": []}),
                   mock.patch.object(pacing, "too_few_beats", lambda sc, b=None: None),
                   mock.patch.object(RW, "REWRITES_DIR", self.rewrites),
                   mock.patch.object(RW, "PLANS_DIR", self.td / "plans"),
                   mock.patch.object(RW, "REPO", self.td)]
        for p in self._p:
            p.start()
        self.sc = _story(self.td)

    def tearDown(self):
        for p in self._p:
            p.stop()

    def _index(self):
        return json.loads((self.rewrites / "OPEN.json").read_text())


class TheSameWordsHeldAgainCarryTodaysReasons(_Box):
    def test_a_retired_reason_is_replaced_by_the_reason_the_run_gives_now(self):
        a = RW.file_request(self.sc, ["premise: no consequential number in the title or hook"],
                            rewrites_dir=self.rewrites)
        b = RW.file_request(self.sc, ["premise: brain: a flat fun fact with no stake"],
                            rewrites_dir=self.rewrites)
        self.assertEqual(a, b, "the same words are the same ask")
        reqs = RW.open_requests(self.rewrites)
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0]["held_for"], ["premise: brain: a flat fun fact with no stake"])
        self.assertEqual(reqs[0]["reasons"], reqs[0]["held_for"])
        self.assertTrue(reqs[0].get("refiled"), "a refreshed request says when")
        self.assertEqual(self._index()["open"][0]["why"],
                         ["premise: brain: a flat fun fact with no stake"])

    def test_the_same_reasons_again_touch_nothing(self):
        RW.file_request(self.sc, ["premise: x"], rewrites_dir=self.rewrites)
        before = Path(RW.open_requests(self.rewrites)[0]["_path"]).read_text()
        RW.file_request(self.sc, ["premise: x"], rewrites_dir=self.rewrites)
        after = Path(RW.open_requests(self.rewrites)[0]["_path"]).read_text()
        self.assertEqual(before, after)
        self.assertNotIn("refiled", json.loads(after))

    def test_a_refresh_carries_the_current_rules(self):
        RW.file_request(self.sc, ["premise: x"], rewrites_dir=self.rewrites)
        req = RW.open_requests(self.rewrites)[0]
        # a request written under an older rule set
        on_disk = json.loads(Path(req["_path"]).read_text())
        on_disk["rules"] = ["an old rule"]
        Path(req["_path"]).write_text(json.dumps(on_disk))
        RW.file_request(self.sc, ["premise: x"], rewrites_dir=self.rewrites)
        self.assertEqual(RW.open_requests(self.rewrites)[0]["rules"], RW.RULES)


class AStoryHeldForItsDataIsNotAWordsJob(_Box):
    DATA = "data: seg0 (myopia_share.json): source officiality='illustrative' — not a real source"

    def test_a_mixed_hold_files_nothing_and_retires_the_open_ask(self):
        RW.file_request(self.sc, ["premise: x"], rewrites_dir=self.rewrites)
        self.assertEqual(len(RW.open_requests(self.rewrites)), 1)
        results = [{"slug": "myopia", "ok": False, "error": "editorial_hold",
                    "reasons": [self.DATA, "premise: brain: vague"]}]
        filed = RW.file_for_run(results, {"myopia": self.sc}, rewrites_dir=self.rewrites)
        self.assertEqual(filed, [])
        self.assertEqual(RW.open_requests(self.rewrites), [], "the dead ask is still open")
        done = list(self.rewrites.glob("*/*.done.json"))
        self.assertEqual(len(done), 1)
        rec = json.loads(done[0].read_text())
        self.assertEqual(rec["decision"], "unpostable")
        self.assertEqual(rec["problems"], [self.DATA])
        self.assertEqual(self._index()["open"], [])

    def test_the_backlog_sweep_retires_it_too(self):
        RW.file_request(self.sc, ["premise: x"], rewrites_dir=self.rewrites)
        with mock.patch.object(RW, "gate_reasons", lambda sc: [self.DATA, "premise: y"]):
            filed = RW.sweep({"myopia": self.sc}, set(), rewrites_dir=self.rewrites)
        self.assertEqual(filed, [])
        self.assertEqual(RW.open_requests(self.rewrites), [])

    def test_a_story_whose_data_is_later_fixed_is_asked_again(self):
        RW.file_request(self.sc, ["premise: x"], rewrites_dir=self.rewrites)
        RW.retire("myopia", [self.DATA], rewrites_dir=self.rewrites)
        rid = RW.file_request(self.sc, ["premise: x"], rewrites_dir=self.rewrites)
        self.assertTrue(rid.endswith("_r1"), rid)
        self.assertEqual(len(RW.open_requests(self.rewrites)), 1)


class AReadoutIsAskedFor(_Box):
    def _readout(self):
        sc = json.loads(json.dumps(self.sc))
        sc["segments"][0]["say"] = "It went from 22 percent to 34 percent, up 12 points."
        return sc

    def test_a_not_current_narration_hold_is_filed_with_the_narration_reason(self):
        sc = self._readout()
        from shared import narration
        told = narration.problems(sc)
        self.assertTrue(told, "fixture is not a readout")
        results = [{"slug": "myopia", "ok": False, "error": "not_current", "reasons": told}]
        filed = RW.file_for_run(results, {"myopia": sc}, rewrites_dir=self.rewrites)
        self.assertEqual(len(filed), 1)
        req = RW.open_requests(self.rewrites)[0]
        self.assertTrue(any(r.startswith("narration: beat 1 reads off") for r in req["held_for"]),
                        req["held_for"])
        # the gate's own word holds ride along so one rewrite clears everything
        self.assertTrue(any(r.startswith("premise:") for r in req["held_for"]), req["held_for"])

    def test_a_hook_under_the_floor_is_filed_too(self):
        results = [{"slug": "myopia", "ok": False, "error": "not_current",
                    "reasons": ["the hook is under the floor: a quiz"]}]
        RW.file_for_run(results, {"myopia": self.sc}, rewrites_dir=self.rewrites)
        req = RW.open_requests(self.rewrites)[0]
        self.assertIn("hook: the hook is under the floor: a quiz", req["held_for"])

    def test_a_render_standard_hold_is_not_a_words_job(self):
        # the run checks the narration BEFORE it renders, so a story held
        # for its render's standard has a narration that already reads
        results = [{"slug": "myopia", "ok": False, "error": "not_current",
                    "reasons": ["rendered under the 2026-10-09 standard; today's is 2026-11-17"]}]
        with mock.patch.object(RW, "narration_holds", lambda sc: []):
            filed = RW.file_for_run(results, {"myopia": self.sc}, rewrites_dir=self.rewrites)
        self.assertEqual(filed, [])
        self.assertEqual(RW.open_requests(self.rewrites), [])

    def test_the_sweep_files_a_readout(self):
        sc = self._readout()
        filed = RW.sweep({"myopia": sc}, set(), rewrites_dir=self.rewrites)
        self.assertEqual(len(filed), 1)
        self.assertTrue(any(r.startswith("narration:")
                            for r in RW.open_requests(self.rewrites)[0]["held_for"]))


class TheAnswerMustReadAsAStory(_Box):
    READOUT = dict(GOOD_ANSWER, segments=[
        dict(GOOD_ANSWER["segments"][0],
             say="Nearsightedness climbed from 22 percent of people in 1990 to 34 percent by 2020."),
        GOOD_ANSWER["segments"][1]])

    def test_the_claim_refuses_a_readout_and_says_so(self):
        cand, problems = RW.validate(self.sc, self.READOUT, narration=True)
        self.assertIsNone(cand)
        self.assertTrue(any("narration: beat 1 reads off 2 numbers" in p for p in problems), problems)

    def test_the_brains_own_path_is_unchanged(self):
        # retell/tighten check the narration themselves; validate() alone does not
        cand, problems = RW.validate(self.sc, self.READOUT)
        self.assertEqual(problems, [])
        self.assertIsNotNone(cand)

    def test_claim_all_asks_narration_of_every_answer(self):
        cp = self.td / "niche.config.json"
        cp.write_text(json.dumps({"stories": [self.sc]}))
        RW.file_request(self.sc, RW.word_holds(self.sc), rewrites_dir=self.rewrites)
        req = RW.open_requests(self.rewrites)[0]
        ans = dict(self.READOUT, request_id=req["id"], slug="myopia", by="chatgpt")
        (Path(req["_path"]).parent / f"{req['id']}.answer.json").write_text(json.dumps(ans))
        rep = RW.claim_all(cp, rewrites_dir=self.rewrites)
        self.assertEqual(rep["applied"], [])
        self.assertEqual(len(rep["rejected"]), 1)
        self.assertTrue(any("narration:" in p for p in rep["rejected"][0]["problems"]))
        self.assertEqual(json.loads(cp.read_text())["stories"][0]["title"], "Nearsighted People")
        again = RW.open_requests(self.rewrites)
        self.assertEqual(len(again), 1, "the refusal was not re-filed")
        self.assertTrue(any("narration:" in p for p in again[0]["prior_rejection"]))

    def test_a_good_answer_still_applies(self):
        cp = self.td / "niche.config.json"
        cp.write_text(json.dumps({"stories": [self.sc]}))
        RW.file_request(self.sc, RW.word_holds(self.sc), rewrites_dir=self.rewrites)
        req = RW.open_requests(self.rewrites)[0]
        ans = dict(GOOD_ANSWER, request_id=req["id"], slug="myopia", by="chatgpt")
        (Path(req["_path"]).parent / f"{req['id']}.answer.json").write_text(json.dumps(ans))
        rep = RW.claim_all(cp, rewrites_dir=self.rewrites)
        self.assertEqual(rep["applied"], ["myopia"])


class TheRunStillWiresIt(unittest.TestCase):
    def test_post_stories_records_not_current_with_its_reasons(self):
        src = (ROOT / "scripts" / "post_stories.py").read_text()
        self.assertIn('"error": "not_current", "reasons": _told', src)
        self.assertIn("_rw.file_for_run(results, stories)", src)

    def test_the_mailbox_doc_names_the_new_outcomes(self):
        txt = (ROOT / "docs" / "REVIEW_MAILBOX.md").read_text()
        for word in ("refiled", "unpostable", "narration:"):
            self.assertIn(word, txt, word)


if __name__ == "__main__":
    unittest.main()
