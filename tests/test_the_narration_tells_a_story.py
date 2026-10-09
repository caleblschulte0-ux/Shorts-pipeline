"""The narration tells a STORY — it does not read the data out.

Operator, 2026-10-09: *"instead of saying the organization's name, we can
just say the experts ... unless it's a really famous one, like WHO or the
White House ... this whole thing is just us reading off numbers to people
... they're hard to follow."* `shared/narration.py` finds a beat that reads
off a list or names a group nobody knows, and has the brain retell it,
validated like any rewrite and heard against the old words by a listener.
"""
from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import narration as N  # noqa: E402

CFG_PATH = ROOT / "data_learning" / "niche.config.json"
CFG = json.loads(CFG_PATH.read_text())
SLUG = "measles-ninety-five-rule"
RETOLD = {"segments": [
    {"say": "One person with measles infects about 15 others, far more than the flu."},
    {"say": "Stopping it takes 95 percent immunity, and American kindergartners are just short of that."},
    {"say": "That small gap brought measles roaring back: 2,566 cases this year."}],
    "closing": "Measles only needs a small gap to come back."}


def _story():
    for s in CFG["stories"]:
        if s["slug"] == SLUG:
            return copy.deepcopy(s)
    raise unittest.SkipTest(f"{SLUG} left the queue")


def _brain(*answers):
    calls = []

    def ask(prompt):
        calls.append(prompt)
        return answers[min(len(calls), len(answers)) - 1]
    ask.calls = calls
    return ask


class WhatCodeCanSee(unittest.TestCase):
    def test_a_list_of_numbers_is_a_readout(self):
        found = N.problems({"segments": [{"say": "Only 9% recycles, 50% lands "
                                                 "in dumps, 22% disappears."}]})
        self.assertTrue(any("reads off 3 numbers" in p for p in found), found)

    def test_one_number_a_beat_is_a_story(self):
        self.assertEqual(N.problems({"segments": [
            {"say": "Since 1970, nearly a third of the birds are just gone, 3 billion of them."},
            {"say": "The jackpot is 1 in 292 million."}]}), [])

    def test_even_a_from_to_is_one_number_too_many(self):
        """caaleb, 2026-10-09: 'the less numbers we just throw at them in a
        row, the better'."""
        found = N.problems({"segments": [
            {"say": "In 1970 there were 10.1 billion birds; now only 7.2 billion."}]})
        self.assertTrue(any("reads off 2 numbers" in p for p in found), found)

    def test_a_group_nobody_knows_is_named(self):
        found = N.problems({"segments": [{"say": "The OECD forecast says 17 percent."}],
                            "closing": "RAND did the math."})
        self.assertTrue(any("OECD" in p for p in found), found)
        self.assertTrue(any("closing names RAND" in p for p in found), found)

    def test_a_famous_one_is_fine(self):
        self.assertEqual(N.problems({"segments": [
            {"say": "The WHO and NASA agree, and so does the FBI."}]}), [])

    def test_the_writers_are_told(self):
        from shared import rewrite_mailbox as rw
        self.assertTrue(any("the experts" in r for r in rw.RULES))
        src = (ROOT / "scripts" / "story_forge.py").read_text()
        self.assertIn("_narration.DOCTRINE", src)


class TheRetell(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = self.tmp / "niche.config.json"
        shutil.copy(CFG_PATH, self.cfg)
        self.sc = _story()
        if not N.problems(self.sc):
            raise unittest.SkipTest(f"{SLUG} already reads as a story")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _saved(self):
        return next(s for s in json.loads(self.cfg.read_text())["stories"]
                    if s["slug"] == SLUG)

    def test_a_story_the_listener_prefers_is_retold_and_saved(self):
        brain = _brain(json.dumps(RETOLD), '{"pick": "B", "why": "follows"}')
        r = N.retell(self.sc, config_path=self.cfg, brain=brain, log=lambda m: None)
        self.assertTrue(r["changed"], r)
        self.assertEqual(self.sc["segments"][0]["say"], RETOLD["segments"][0]["say"])
        saved = self._saved()
        self.assertEqual(saved["segments"][2]["say"], RETOLD["segments"][2]["say"])
        self.assertEqual(saved.get("retold"), N.RETOLD)
        again = _brain("{}")
        self.assertFalse(N.retell(self.sc, config_path=self.cfg, brain=again,
                                  log=lambda m: None)["changed"])
        self.assertEqual(again.calls, [], "a retold story is not asked again")

    def test_an_invented_number_is_refused(self):
        bad = copy.deepcopy(RETOLD)
        bad["segments"][0]["say"] = "One person with measles infects about 777 others."
        brain = _brain(json.dumps(bad))
        before = copy.deepcopy(self.sc)
        r = N.retell(self.sc, config_path=self.cfg, brain=brain, log=lambda m: None)
        self.assertFalse(r["changed"])
        self.assertEqual(self.sc["segments"], before["segments"])
        self.assertIn("REFUSED", brain.calls[-1], "the refusal is fed back")

    def test_the_listener_can_keep_the_old_words(self):
        before = copy.deepcopy(self.sc)
        brain = _brain(json.dumps(RETOLD), '{"pick": "A", "why": "B overstates"}')
        r = N.retell(self.sc, config_path=self.cfg, brain=brain, log=lambda m: None)
        self.assertFalse(r["changed"])
        self.assertEqual(self.sc["segments"], before["segments"])
        self.assertNotEqual(self._saved().get("retold"), N.RETOLD)

    def test_no_brain_keeps_the_story(self):
        r = N.retell(self.sc, config_path=self.cfg, brain=lambda p: None,
                     log=lambda m: None)
        self.assertFalse(r["changed"])


class ItIsWiredIn(unittest.TestCase):
    def test_post_stories_retells_before_the_gate(self):
        src = (ROOT / "scripts" / "post_stories.py").read_text()
        i = src.index("_narration.retell(")
        self.assertLess(src.index("_pacing.tighten("), i)
        self.assertLess(i, src.index("_eg.pre_render_verdict(sc)"))


if __name__ == "__main__":
    unittest.main()
