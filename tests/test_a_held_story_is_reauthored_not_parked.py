"""A HELD EXPLAINER STORY IS RE-AUTHORED BY CHATGPT — AND CODE DECIDES.

Operator, 2026-09-22: *"ChatGPT is supposed to render videos if nothing
else is available. And ChatGPT is always available."* The explainer had no
re-author loop; the deterministic gate held 312 of 337 stories that
morning for word reasons and nothing ever asked for a rewrite.

Held here, each by injection:
  1. a story the gate holds for WORD reasons is filed, with its data, the
     rules and the reasons; a story held for DATA reasons is not;
  2. filing is idempotent on the current words, and changed words
     supersede the old open request;
  3. a judge block is filed with the judge's own problems/fixes;
  4. an answer is refused when it invents a number, names an entity the
     data does not, changes the segment count, or still fails the gate;
  5. an accepted answer changes the config, marks `words_by`, drops the
     slug's scene plan, and settles the request; a refused one is settled
     with reasons and re-filed carrying them;
  6. the run claims at its start and files at its end; the claim workflow
     claims rewrites and persists WITHOUT [skip ci] when one applied.
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


def _data(td: Path, name: str, points, unit="percent"):
    p = td / name
    p.write_text(json.dumps({"key": name[:-5], "title": "share of people", "unit": unit,
                             "source": {"name": "s", "publisher": "p", "url": "u",
                                        "officiality": "official", "access_date": "2026-01-01"},
                             "points": points}))
    return p


def _story(td: Path, *, title="Nearsighted People", hook="It is rising.",
           topic0="myopia rate", say0="More than a third of people are nearsighted now."):
    _data(td, "myopia_share.json", [{"label": "1990", "value": 22.0, "period": "1990"},
                                    {"label": "2020", "value": 34.0, "period": "2020"}])
    _data(td, "screen_hours.json", [{"label": "2010", "value": 3.0, "period": "2010"},
                                    {"label": "2020", "value": 7.0, "period": "2020"}],
          unit="hours")
    return {"slug": "myopia", "title": title, "hook": hook, "closing": "Look up.",
            "question": "Do you wear glasses?",
            "segments": [
                {"source": "offline", "key": "myopia_share",
                 "params": {"file": "myopia_share.json"}, "insight_type": "trend",
                 "topic": topic0, "say": say0},
                {"source": "offline", "key": "screen_hours",
                 "params": {"file": "screen_hours.json"}, "insight_type": "trend",
                 "topic": "screen time", "say": "Screen time went from 3 hours a day to 7."}]}


GOOD_ANSWER = {
    "title": "Why 34% Of People Are Now Nearsighted — Screens Doubled It",
    "hook": "From 22 percent in 1990 to 34 percent by 2020.",
    "closing": "Look up once in a while.",
    "question": "Glasses or not?",
    "segments": [{"topic": "nearsighted share", "say": "Nearsightedness climbed from 22 percent of people in 1990 to 34 percent by 2020."},
                 {"topic": "screens per day", "say": "Daily screen time went from 3 hours to 7 hours in the same stretch."}],
}


class _Box(unittest.TestCase):
    def setUp(self):
        self.td = Path(tempfile.mkdtemp(prefix="rw-"))
        self.rewrites = self.td / "rewrites"
        # distinctness is the gate's own rule, held elsewhere; this fixture's
        # two beats are about the numbers/entities/premise checks
        self._p = [mock.patch.object(EG, "DATA_DIR", self.td),
                   mock.patch.object(EG, "beats_are_distinct",
                                     lambda sc: {"ok": True, "reasons": []}),
                   mock.patch.object(RW, "REWRITES_DIR", self.rewrites),
                   mock.patch.object(RW, "PLANS_DIR", self.td / "plans"),
                   mock.patch.object(RW, "REPO", self.td)]
        for p in self._p:
            p.start()
        self.sc = _story(self.td)

    def tearDown(self):
        for p in self._p:
            p.stop()

    def _answer(self, req, **over):
        a = dict(GOOD_ANSWER, request_id=req["id"], slug=req["slug"], by="chatgpt")
        a.update(over)
        (Path(req["_path"]).parent / f"{req['id']}.answer.json").write_text(json.dumps(a))


class TheHoldIsAWordsProblemAndItIsFiled(_Box):
    def test_the_fixture_story_is_held_for_word_reasons(self):
        reasons = RW.word_holds(self.sc)
        self.assertTrue(reasons)
        self.assertTrue(any(r.startswith("premise:") for r in reasons), reasons)

    def test_a_word_hold_files_a_request_with_data_rules_and_reasons(self):
        rid = RW.file_request(self.sc, RW.word_holds(self.sc), rewrites_dir=self.rewrites)
        req = RW.open_requests(self.rewrites)[0]
        self.assertEqual(req["id"], rid)
        self.assertEqual(req["current"]["title"], "Nearsighted People")
        self.assertEqual(req["segments"][0]["data"]["points"][1]["value"], 34.0)
        self.assertEqual(req["segments"][1]["data"]["unit"], "hours")
        self.assertIn("consequential NUMBER", " ".join(req["rules"]))
        self.assertTrue(req["held_for"])
        idx = json.loads((self.rewrites / "OPEN.json").read_text())
        self.assertEqual([o["slug"] for o in idx["open"]], ["myopia"])

    def test_a_data_hold_is_not_a_words_job(self):
        results = [{"slug": "myopia", "ok": False, "error": "editorial_hold",
                    "reasons": ["data: seg0: source officiality='blog' — not a real source"]}]
        self.assertEqual(RW.file_for_run(results, {"myopia": self.sc}, rewrites_dir=self.rewrites), [])
        self.assertEqual(RW.open_requests(self.rewrites), [])

    def test_the_same_words_are_asked_once_and_new_words_supersede(self):
        a = RW.file_request(self.sc, ["premise: x"], rewrites_dir=self.rewrites)
        b = RW.file_request(self.sc, ["premise: x"], rewrites_dir=self.rewrites)
        self.assertEqual(a, b)
        self.assertEqual(len(RW.open_requests(self.rewrites)), 1)
        sc2 = dict(self.sc, title="A Different Title Entirely")
        c = RW.file_request(sc2, ["premise: y"], rewrites_dir=self.rewrites)
        self.assertNotEqual(c, a)
        open_ids = [r["id"] for r in RW.open_requests(self.rewrites)]
        self.assertEqual(open_ids, [c], "the old request was not superseded")

    def test_a_judge_block_carries_the_judges_own_words(self):
        ledger = self.td / "verdicts.jsonl"
        ledger.write_text(json.dumps({"slug": "myopia", "verdict": "ship", "score": 80}) + "\n"
                          + json.dumps({"slug": "myopia", "verdict": "block", "score": 34,
                                        "one_line": "text on text at seg1",
                                        "problems": ["labels clipped"], "fixes": ["shorter labels"]}) + "\n")
        j = RW.last_block("myopia", ledger=ledger)
        self.assertEqual(j["one_line"], "text on text at seg1")
        results = [{"slug": "myopia", "ok": False, "error": "showrunner_block"}]
        with mock.patch.object(RW, "last_block", lambda slug, ledger=None: j):
            filed = RW.file_for_run(results, {"myopia": self.sc}, rewrites_dir=self.rewrites)
        req = RW.open_requests(self.rewrites)[0]
        self.assertEqual(filed, [req["id"]])
        self.assertEqual(req["judge"]["fixes"], ["shorter labels"])
        self.assertTrue(req["held_for"][0].startswith("judge:"))


class CodeDecidesWhatARewriteMayDo(_Box):
    def test_a_good_rewrite_passes_and_clears_the_gate(self):
        cand, problems = RW.validate(self.sc, GOOD_ANSWER)
        self.assertEqual(problems, [])
        self.assertEqual(cand["title"], GOOD_ANSWER["title"])
        self.assertEqual(RW.word_holds(cand), [])

    def test_an_invented_number_is_refused(self):
        # 61 would pass: 34 is 61% of 22+34, and a share of the total is a
        # number the picture can honestly show. 88 comes from nowhere.
        bad = dict(GOOD_ANSWER, segments=[dict(GOOD_ANSWER["segments"][0],
                                               say="Nearsightedness hit 88 percent by 2020.")]
                   + GOOD_ANSWER["segments"][1:])
        cand, problems = RW.validate(self.sc, bad)
        self.assertIsNone(cand)
        self.assertTrue(any("not derivable" in p and "88" in p for p in problems), problems)

    def test_a_derived_number_is_allowed(self):
        """A difference, a percent change, a share — the beat can show it."""
        ok = dict(GOOD_ANSWER, segments=[dict(GOOD_ANSWER["segments"][0],
                                              say="Nearsightedness rose 12 points, from 22 to 34 percent, by 2020.")]
                  + GOOD_ANSWER["segments"][1:])
        cand, problems = RW.validate(self.sc, ok)
        self.assertEqual(problems, [])

    def test_a_new_entity_the_data_does_not_name_is_refused(self):
        bad = dict(GOOD_ANSWER, hook="By 2020, Singapore was at 34 percent.")
        cand, problems = RW.validate(self.sc, bad)
        self.assertIsNone(cand)
        self.assertTrue(any("Singapore" in p for p in problems), problems)

    def test_the_wrong_segment_count_is_refused(self):
        cand, problems = RW.validate(self.sc, dict(GOOD_ANSWER, segments=GOOD_ANSWER["segments"][:1]))
        self.assertIsNone(cand)

    def test_a_rewrite_that_still_fails_the_gate_is_refused(self):
        bad = dict(GOOD_ANSWER, title="Nearsighted People", hook="It is rising.")
        cand, problems = RW.validate(self.sc, bad)
        self.assertIsNone(cand)
        self.assertTrue(any(p.startswith("still held by the gate") for p in problems), problems)

    def test_a_long_topic_is_refused_because_it_is_printed(self):
        bad = dict(GOOD_ANSWER, segments=[dict(GOOD_ANSWER["segments"][0],
                                               topic="the share of people who are nearsighted")]
                   + GOOD_ANSWER["segments"][1:])
        cand, problems = RW.validate(self.sc, bad)
        self.assertTrue(any("topic" in p for p in problems), problems)


class TheClaimAppliesOrRefilesNeverTrusts(_Box):
    def _cfg(self):
        cp = self.td / "niche.config.json"
        cp.write_text(json.dumps({"stories": [self.sc, {"slug": "other", "segments": []}]}))
        return cp

    def test_an_accepted_answer_changes_the_config_and_settles(self):
        cp = self._cfg()
        (self.td / "plans").mkdir()
        (self.td / "plans" / "myopia.json").write_text("{}")
        rid = RW.file_request(self.sc, RW.word_holds(self.sc), rewrites_dir=self.rewrites)
        req = RW.open_requests(self.rewrites)[0]
        self._answer(req)
        rep = RW.claim_all(cp, rewrites_dir=self.rewrites)
        self.assertEqual(rep["applied"], ["myopia"])
        got = json.loads(cp.read_text())
        st = got["stories"][0]
        self.assertEqual(st["title"], GOOD_ANSWER["title"])
        self.assertEqual(st["words_by"], RW.WORDS_BY)
        self.assertEqual(st["segments"][0]["topic"], "nearsighted share")
        self.assertEqual(got["stories"][1], {"slug": "other", "segments": []}, "another story was touched")
        self.assertFalse((self.td / "plans" / "myopia.json").exists(), "the old scene plan survived")
        self.assertEqual(RW.open_requests(self.rewrites), [])
        done = json.loads((Path(req["_path"]).parent / f"{rid}.done.json").read_text())
        self.assertEqual(done["decision"], "applied")

    def test_a_refused_answer_is_settled_with_reasons_and_refiled(self):
        cp = self._cfg()
        RW.file_request(self.sc, RW.word_holds(self.sc), rewrites_dir=self.rewrites)
        req = RW.open_requests(self.rewrites)[0]
        self._answer(req, hook="By 2020, Singapore was at 34 percent.")
        rep = RW.claim_all(cp, rewrites_dir=self.rewrites)
        self.assertEqual(rep["applied"], [])
        self.assertEqual(len(rep["rejected"]), 1)
        self.assertEqual(json.loads(cp.read_text())["stories"][0]["title"], "Nearsighted People")
        again = RW.open_requests(self.rewrites)
        self.assertEqual(len(again), 1, "the refusal was not re-filed")
        self.assertTrue(again[0]["prior_rejection"], "the re-file carries no reasons")

    def test_an_answer_for_another_request_is_refused(self):
        cp = self._cfg()
        RW.file_request(self.sc, ["premise: x"], rewrites_dir=self.rewrites)
        req = RW.open_requests(self.rewrites)[0]
        self._answer(req, request_id="myopia__deadbeef")
        rep = RW.claim_all(cp, rewrites_dir=self.rewrites)
        self.assertEqual(rep["applied"], [])
        self.assertEqual(json.loads(cp.read_text())["stories"][0]["title"], "Nearsighted People")

    def test_no_answer_stays_open(self):
        cp = self._cfg()
        RW.file_request(self.sc, ["premise: x"], rewrites_dir=self.rewrites)
        rep = RW.claim_all(cp, rewrites_dir=self.rewrites)
        self.assertEqual(rep["open"], 1)


class TheLoopIsWired(unittest.TestCase):
    def test_the_run_claims_first_and_files_last(self):
        src = (ROOT / "scripts" / "post_stories.py").read_text()
        self.assertLess(src.index("_rw.claim_all(args.config)"), src.index("for slug in slugs:"))
        self.assertGreater(src.index("_rw.file_for_run(results, stories)"),
                           src.index("classify_results(results)"))

    def test_the_claim_workflow_claims_rewrites_and_renders_what_it_applied(self):
        wf = (ROOT / ".github" / "workflows" / "claim_reviews.yml").read_text()
        self.assertIn("exchange/rewrites/**/*.answer.json", wf)
        self.assertIn("claim_rewrites.py claim", wf)
        self.assertIn("data_learning/niche.config.json", wf)
        # an applied rewrite is persisted WITHOUT [skip ci], so the push renders it
        i = wf.index("ChatGPT rewrite(s) applied")
        self.assertNotIn("[skip ci]", wf[i:i + 80])

    def test_render_workflows_persist_the_mailbox(self):
        for wf in ("explainer.yml", "daily.yml"):
            self.assertIn("exchange/rewrites", (ROOT / ".github" / "workflows" / wf).read_text(), wf)

    def test_the_round_and_the_playbook_name_it(self):
        txt = (ROOT / "docs" / "REVIEW_MAILBOX.md").read_text()
        self.assertIn("exchange/rewrites/OPEN.json", txt)
        self.assertIn("RE-AUTHORED, not parked", (ROOT / "CLAUDE.md").read_text())


if __name__ == "__main__":
    unittest.main()
