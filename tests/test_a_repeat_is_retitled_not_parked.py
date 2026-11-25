"""A REPEAT IS RETITLED, NOT PARKED (doctor aaeb12de3ebd, 2026-11-25).

The posting run holds a story whose TITLE is too close to a video already
up before the gate ever sees it, and its own message has said since
2026-10-02: "The story is fine; the PACKAGING repeats. Retitle it and it
ships." Nothing ever asked anyone to retitle it — `rewrite_mailbox.
file_for_run` had no branch for `duplicate_hold` — so three stories sat
`duplicate_hold` on every one of the twelve explainer runs of 11-23..11-25
while the channel posted nothing. One of them, "The Ocean Lost 71% Of Its
Sharks Since 1970", was held against "The World Lost 35% Of Its Wetlands
Since 1970": the title template repeats, the story does not, and a retitle
is exactly the fix.

Held here, each by injection:
  1. the run marks every `duplicate_hold` with its KIND (title / story /
     posted) — read off the code, so a new hold cannot forget to;
  2. a TITLE repeat is filed for a rewrite, as a `repeat:` reason that
     names the posted video, and `repeat:` is a word reason the refresh
     keeps;
  3. a STORY repeat (the brain's reading) retires the story's open asks
     instead of filing — no retitle can post it; a slug another run posted
     meanwhile files nothing;
  4. the claim refuses a retitle that still collides, by the run's own
     matcher over the run's own corpus (the explainer log and the data
     channels'), and names the video; one that does not collide applies.
"""
from __future__ import annotations

import ast
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import rewrite_mailbox as RW                               # noqa: E402
from tests.test_a_held_story_is_reauthored_not_parked import (       # noqa: E402
    GOOD_ANSWER, _Box)

POSTED = "Why 34% Of People Are Now Nearsighted — Screens Doubled Them"
HOLD = {"slug": "myopia", "ok": False, "error": "duplicate_hold",
        "duplicate_of": POSTED, "repeat": "title"}


class TheRunSaysWhichKindOfRepeat(unittest.TestCase):
    def test_every_duplicate_hold_result_carries_its_kind(self):
        """Read off the CODE: each results.append({... "error":
        "duplicate_hold" ...}) in post_stories names `repeat`."""
        tree = ast.parse((ROOT / "scripts" / "post_stories.py").read_text())
        seen, kinds = 0, set()
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "append" and node.args
                    and isinstance(node.args[0], ast.Dict)):
                continue
            d = {k.value: v for k, v in zip(node.args[0].keys, node.args[0].values)
                 if isinstance(k, ast.Constant)}
            err = d.get("error")
            if not (isinstance(err, ast.Constant) and err.value == "duplicate_hold"):
                continue
            seen += 1
            self.assertIn("repeat", d, f"a duplicate_hold at line {node.lineno} says not which kind")
            self.assertIsInstance(d["repeat"], ast.Constant)
            kinds.add(d["repeat"].value)
        self.assertGreaterEqual(seen, 3, "the three repeat holds were not found")
        self.assertEqual(kinds, {"title", "story", "posted"})

    def test_repeat_is_a_word_reason(self):
        self.assertEqual(RW.words_only([RW.repeat_reason(POSTED), "data: x"]),
                         [RW.repeat_reason(POSTED)])
        self.assertIn(POSTED, RW.repeat_reason(POSTED))
        self.assertTrue(RW.repeat_reason(POSTED).startswith(RW.REPEAT_PREFIX))


class ATitleRepeatIsAskedToRetitle(_Box):
    def test_a_title_repeat_files_a_request_naming_the_video(self):
        filed = RW.file_for_run([HOLD], {"myopia": self.sc}, rewrites_dir=self.rewrites)
        reqs = RW.open_requests(self.rewrites)
        self.assertEqual(len(reqs), 1)
        self.assertEqual(filed, [reqs[0]["id"]])
        held = reqs[0]["held_for"]
        self.assertTrue(held[0].startswith("repeat:"), held)
        self.assertIn(POSTED, held[0])
        # ...plus what the gate would say, so the writer fixes it all at once
        self.assertTrue(any(r.startswith("premise:") for r in held), held)

    def test_the_same_repeat_again_refreshes_not_duplicates(self):
        RW.file_for_run([HOLD], {"myopia": self.sc}, rewrites_dir=self.rewrites)
        RW.file_for_run([dict(HOLD, duplicate_of="Another Posted Title")],
                        {"myopia": self.sc}, rewrites_dir=self.rewrites)
        reqs = RW.open_requests(self.rewrites)
        self.assertEqual(len(reqs), 1)
        self.assertIn("Another Posted Title", reqs[0]["held_for"][0])

    def test_a_story_repeat_retires_the_asks_and_files_nothing(self):
        RW.file_request(self.sc, ["premise: x"], rewrites_dir=self.rewrites)
        rid = RW.open_requests(self.rewrites)[0]["id"]
        filed = RW.file_for_run([dict(HOLD, repeat="story")], {"myopia": self.sc},
                                rewrites_dir=self.rewrites)
        self.assertEqual(filed, [])
        self.assertEqual(RW.open_requests(self.rewrites), [])
        done = json.loads(next(self.rewrites.glob(f"*/{rid}.done.json")).read_text())
        self.assertEqual(done["decision"], "unpostable")
        self.assertIn(POSTED, done["problems"][0])

    def test_a_slug_another_run_posted_files_nothing(self):
        for how in ("posted", None):
            r = dict(HOLD, repeat=how)
            if how is None:
                del r["repeat"]
            self.assertEqual(RW.file_for_run([r], {"myopia": self.sc},
                                             rewrites_dir=self.rewrites), [])
        self.assertEqual(RW.open_requests(self.rewrites), [])


class TheClaimRefusesARetitleThatStillRepeats(_Box):
    def _cfg(self):
        cp = self.td / "niche.config.json"
        cp.write_text(json.dumps({"stories": [self.sc]}))
        return cp

    def _log(self, *titles):
        lp = self.td / "state" / "explainer_posted_log.json"
        lp.parent.mkdir(parents=True, exist_ok=True)
        lp.write_text(json.dumps({"posted": {f"s{i}": {"title": t, "state": "posted",
                                                       "at": "2026-11-20T00:00:00+00:00"}
                                             for i, t in enumerate(titles)}}))
        return lp

    def test_validate_refuses_a_colliding_title_and_names_the_video(self):
        cand, problems = RW.validate(self.sc, GOOD_ANSWER, posted_titles=[POSTED])
        self.assertIsNone(cand)
        self.assertTrue(any("repeat:" in p and POSTED in p for p in problems), problems)
        cand, problems = RW.validate(self.sc, GOOD_ANSWER,
                                     posted_titles=["Why The Moon Is Drifting Away"])
        self.assertEqual(problems, [])

    def test_the_run_corpus_is_the_explainer_log_and_the_data_channels(self):
        lp = self._log(POSTED)
        self.assertIn(POSTED, RW.posted_titles(lp))
        # REPO is the sandbox here, so the data channels' corpus is read from
        # it too: the explainer's log reaches the claim even with no log path
        self.assertIn(POSTED, RW.posted_titles(self.td / "missing.json"))
        (self.td / "state" / "explainer_posted_log.json").unlink()
        self.assertEqual(RW.posted_titles(self.td / "missing.json"), [])

    def test_claim_refuses_the_collision_and_applies_a_real_retitle(self):
        cp = self._cfg()
        lp = self._log(POSTED)
        RW.file_for_run([HOLD], {"myopia": self.sc}, rewrites_dir=self.rewrites)
        req = RW.open_requests(self.rewrites)[0]
        self._answer(req)                       # GOOD_ANSWER's title collides
        rep = RW.claim_all(cp, rewrites_dir=self.rewrites, log_path=lp)
        self.assertEqual(rep["applied"], [])
        self.assertEqual(len(rep["rejected"]), 1)
        self.assertTrue(any(POSTED in p for p in rep["rejected"][0]["problems"]),
                        rep["rejected"])
        again = RW.open_requests(self.rewrites)
        self.assertEqual(len(again), 1, "the refusal was not re-filed")
        self.assertTrue(any(POSTED in p for p in again[0]["prior_rejection"]))
        # a title of its own ships
        self._answer(again[0], title="Screens Made A Third Of Us Nearsighted")
        rep = RW.claim_all(cp, rewrites_dir=self.rewrites, log_path=lp)
        self.assertEqual(rep["applied"], ["myopia"])
        self.assertEqual(json.loads(cp.read_text())["stories"][0]["title"],
                         "Screens Made A Third Of Us Nearsighted")

    def test_the_claim_script_hands_the_claim_its_log(self):
        src = (ROOT / "scripts" / "claim_rewrites.py").read_text()
        self.assertIn("log_path=args.log", src)


if __name__ == "__main__":
    unittest.main()
