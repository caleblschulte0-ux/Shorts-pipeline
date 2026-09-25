"""The first sentence is a 2000s download-site ad — and still true.

Operator, 2026-09-25: *"Our intros need to be 2000s ... LimeWire type shit
... real clickbaity. And not like scammy clickbaity."* `shared/hook_doctrine`
scores a hook, and at render time has the brain rewrite any hook under the
bar. These hold the two halves: it hits harder, and it never lies.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import hook_doctrine as H  # noqa: E402

CFG = json.loads((ROOT / "data_learning" / "niche.config.json").read_text())
COFFEE = next(s for s in CFG["stories"] if s["slug"] == "coffee-price-record")


class TheScoreKnowsAnAdFromAFact(unittest.TestCase):
    def test_the_voice_outscores_the_queue(self):
        ad = H.punch("Your coffee just got gutted: 11 million bags, gone overnight.")
        soft = H.punch("Your coffee habit is about to get pricier.")
        self.assertGreaterEqual(ad["score"], H.BAR)
        self.assertLess(soft["score"], H.BAR)

    def test_a_quiz_is_not_a_hook(self):
        self.assertLess(H.punch("Which animal could crush a bowling ball "
                                "in its jaws?")["score"], H.BAR)

    def test_an_accusing_question_is(self):
        q = H.punch("Why is your coffee twice the price it was a year ago?")
        self.assertNotIn("quiz opener", q["notes"])

    def test_a_scam_tell_sinks_it(self):
        self.assertLess(H.punch("Click now: your coffee DOUBLED and doctors "
                                "hate it")["score"], H.BAR)

    def test_a_hedge_costs(self):
        a = H.punch("Your coffee got gutted by 11 million bags.")
        b = H.punch("Your coffee might get gutted by 11 million bags.")
        self.assertLess(b["score"], a["score"])


class ItNeverLies(unittest.TestCase):
    def setUp(self):
        self.allowed, self.labels = H.evidence(COFFEE)

    def _problems(self, line):
        return H.problems(line, COFFEE, self.allowed, self.labels)

    def test_a_number_from_the_data_passes(self):
        self.assertEqual(self._problems(
            "Your coffee just got gutted: 11 million bags, gone overnight."), [])

    def test_a_number_from_nowhere_is_refused(self):
        self.assertTrue(self._problems("Your coffee costs 5 times more now."))

    def test_a_name_from_outside_is_refused_even_as_the_first_word(self):
        self.assertTrue(self._problems("Starbucks is hiding 11 million bags."))

    def test_a_name_the_story_uses_passes(self):
        self.assertEqual(self._problems(
            "Brazil's drought erased 11 million bags of your coffee."), [])

    def test_contractions_and_common_words_are_not_names(self):
        self.assertEqual(self._problems(
            "You're paying for 11 million bags that are gone. One drought."), [])


def _brain(hooks, supported):
    """A fake brain: the first call writes hooks, the second fact-checks."""
    calls = []

    def brain(prompt):
        calls.append(prompt)
        if "fact-checker" in prompt:
            return json.dumps({"supported": supported}) if supported is not None \
                else "no idea"
        return json.dumps({"hooks": hooks})
    brain.calls = calls
    return brain


class TheSharpener(unittest.TestCase):
    GOOD = "Your coffee just got gutted: 11 million bags, gone overnight."

    def test_a_soft_hook_is_replaced_by_a_true_hard_one(self):
        b = _brain(["Your coffee costs 5 times more now.", self.GOOD], [1])
        got = H.sharpen(dict(COFFEE), brain=b, log=lambda m: None)
        self.assertEqual(got, self.GOOD)

    def test_a_hook_the_fact_check_refuses_never_ships(self):
        b = _brain([self.GOOD], [])
        self.assertIsNone(H.sharpen(dict(COFFEE), brain=b, log=lambda m: None))

    def test_no_fact_check_means_no_change(self):
        """Fails CLOSED: a soft hook is a missed click, a false one a lie."""
        b = _brain([self.GOOD], None)
        self.assertIsNone(H.sharpen(dict(COFFEE), brain=b, log=lambda m: None))

    def test_no_brain_means_no_change(self):
        self.assertIsNone(H.sharpen(dict(COFFEE), brain=lambda p: None,
                                    log=lambda m: None))

    def test_a_hook_that_already_hits_is_left_alone(self):
        sc = dict(COFFEE, hook=self.GOOD)
        b = _brain(["anything"], [1])
        self.assertIsNone(H.sharpen(sc, brain=b, log=lambda m: None))
        self.assertEqual(b.calls, [])


class SavingAHookDoesNotRewriteTheFile(unittest.TestCase):
    """The config is 29,000 lines and several writers touch it. Saved back
    at a different indent, one sharpened hook was a diff of every line."""

    def test_the_render_save_keeps_the_files_indent(self):
        import tempfile
        from data_learning import studio_render as sr
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cfg.json"
            cfg = {"stories": [{"slug": "s", "hook": "old", "segments": []}]}
            p.write_text(json.dumps(cfg, indent=1) + "\n")
            before = p.read_text().splitlines()
            sr._PERSISTED.append("s")
            sr._save_persisted_mechanics(
                p, {"slug": "s", "hook": "new", "hook_was": "old",
                    "segments": []}, "s")
            after = p.read_text().splitlines()
            self.assertIn('   "hook": "new",', after)
            import difflib
            changed = [ln for ln in difflib.unified_diff(before, after, n=0)
                       if ln[:1] in "+-" and ln[:3] not in ("+++", "---")]
            # the hook line, `hook_was` added, and the comma JSON moves
            self.assertLessEqual(len(changed), 6, changed)


class ItIsWiredIn(unittest.TestCase):
    def test_the_renderer_sharpens_and_persists(self):
        src = (ROOT / "data_learning" / "studio_render.py").read_text()
        self.assertIn("_hd.sharpen(", src)
        self.assertIn('"hook", "hook_was"', src)

    def test_the_forge_writes_to_the_same_doctrine(self):
        src = (ROOT / "scripts" / "story_forge.py").read_text()
        self.assertIn("_HOOK_DOCTRINE", src)
        self.assertIn("_hd.punch(", src)


if __name__ == "__main__":
    unittest.main()
