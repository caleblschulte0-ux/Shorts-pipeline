"""The first sentence stops a thumb, is true, and sounds like a person.

Operator, 2026-09-25: *"real clickbaity. And not like scammy clickbaity."*
Operator, 2026-10-08: *"our word hooks are trash"* — a keyword score had
taught the forge to staple "your" and "vanished" onto everything. Code now
holds only a FLOOR; a listener hears the current hook beside the rewrites
and ranks them. These hold the floor, the listener, and that it never lies.
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
# The hook is PINNED: a render persists its sharpened hook into the config,
# and a test that read the live one stopped being about a soft hook.
COFFEE = dict(next(s for s in CFG["stories"]
                   if s["slug"] == "coffee-price-record"),
              hook="Your coffee habit is about to get pricier.")


class TheFloorIsWhatCodeCanSee(unittest.TestCase):
    def test_a_plain_true_hook_clears_it(self):
        for line in ("A degree costs triple. It pays half.",
                     "More than half the web is bots now.",
                     "Your coffee just hit the highest price ever."):
            self.assertEqual(H.floor(line), [], line)

    def test_a_quiz_is_not_a_hook(self):
        self.assertIn("quiz opener", H.floor(
            "Which animal could crush a bowling ball in its jaws?"))

    def test_an_accusing_question_is(self):
        self.assertEqual(H.floor(
            "Why is your coffee twice the price it was a year ago?"), [])

    def test_a_scam_tell_a_hedge_and_a_vague_size_fail(self):
        self.assertIn("scam tell", H.floor("Click now: your coffee DOUBLED"))
        self.assertIn("hedge", H.floor("Your coffee might get gutted."))
        self.assertTrue(any(w.startswith("vague") for w in H.floor(
            "Your nose can detect an astonishing number of scents")))

    def test_the_formula_tags_the_keyword_score_taught_fail(self):
        """Queued 2026-10-08, each one scored 6-8 under the old keyword
        score and each one is a tag bolted onto a fact."""
        for line in ("Your town's peanut allergies vanished 43% overnight, "
                     "shocking everyone",
                     "Diabetes doubled to 14 percent of adults, and nobody "
                     "told you.",
                     "Commercial whaling killed 2.9 million whales. Then "
                     "something incredible happened."):
            self.assertTrue(any(w.startswith("a formula tag")
                                for w in H.floor(line)), line)

    def test_a_stat_sheet_is_not_a_hook(self):
        """Operator, 2026-10-08, of "Doctors told parents to avoid peanuts,
        and allergies went from 0.4% to 1.4%": "thinking like a TMZ/youtube
        click bait ... not nerd ass oh the percentage point dropped". The
        hook says what the numbers MEAN; the video reads them out."""
        for line in ("Doctors told parents to avoid peanuts, and allergies "
                     "went from 0.4% to 1.4%.",
                     "In 1996 monarchs had 18 hectares. Now they have 0.9.",
                     "Your coffee just hit a record $4.41 a pound."):
            self.assertTrue(any(w.startswith(("a stat sheet", "a decimal"))
                                for w in H.floor(line)), line)
        self.assertEqual(H.floor("Doctors told parents to keep peanuts away "
                                 "from babies. It backfired."), [])
        self.assertEqual(H.floor("Your diamond ring lost 90% of its price."), [])

    def test_the_writer_and_the_listener_want_drama(self):
        self.assertIn("TMZ", H.DOCTRINE)
        self.assertIn("TMZ", H._LISTEN)
        self.assertIn("NOT THE STATISTIC", H.DOCTRINE)

    def test_the_floor_is_not_a_score(self):
        """Nothing in the module ranks by keywords any more: "you" and a
        verb off a list bought nothing (posted hooks scoring 7+ kept 31%
        of viewers, 0-2 kept 36%) and taught "your octopus"."""
        self.assertFalse(hasattr(H, "punch"))
        self.assertFalse(hasattr(H, "BAR"))
        self.assertNotIn("Put the VIEWER in it", H.DOCTRINE)


class ItNeverLies(unittest.TestCase):
    def setUp(self):
        self.allowed, self.labels = H.evidence(COFFEE)

    def _problems(self, line):
        return H.problems(line, COFFEE, self.allowed, self.labels)

    def test_a_number_from_the_data_passes(self):
        self.assertEqual(self._problems(
            "Your coffee just hit a record $4.41 a pound — gutted."), [])

    def test_a_number_from_nowhere_is_refused(self):
        self.assertTrue(self._problems("Your coffee costs 5 times more now."))

    def test_a_name_from_outside_is_refused_even_as_the_first_word(self):
        self.assertTrue(self._problems("Starbucks is hiding $4.41 coffee."))

    def test_a_later_beats_number_is_refused(self):
        """The hook is spoken over BEAT 1's picture: "11 million bags" is
        beat two's, and the viewer cannot see it during the hook."""
        self.assertTrue(self._problems(
            "Your coffee just got gutted: 11 million bags, gone overnight."))

    def test_a_name_the_story_uses_passes(self):
        self.assertEqual(self._problems(
            "Brazil's drought pushed your coffee to $4.41 a pound."), [])

    def test_contractions_and_common_words_are_not_names(self):
        self.assertEqual(self._problems(
            "You're paying $4.41 a pound now. One drought."), [])


def _brain(hooks, ranking):
    """A fake brain: the first call writes hooks, the second listens."""
    calls = []

    def brain(prompt):
        calls.append(prompt)
        if "fact-checker" in prompt:
            return json.dumps({"ranking": ranking}) if ranking is not None \
                else "no idea"
        return json.dumps({"hooks": hooks})
    brain.calls = calls
    return brain


class TheSharpener(unittest.TestCase):
    GOOD = "Your coffee just hit the highest price ever recorded."

    def test_the_listeners_first_choice_ships(self):
        # candidates heard: 1 = the current hook, 2 = GOOD (the 5x line is
        # refused by code before the listener hears it)
        b = _brain(["Your coffee costs 5 times more now.", self.GOOD], [2, 1])
        got = H.sharpen(dict(COFFEE), brain=b, log=lambda m: None)
        self.assertEqual(got, self.GOOD)
        self.assertIn("1. " + COFFEE["hook"], b.calls[1])
        self.assertNotIn("5 times", b.calls[1])

    def test_the_current_hook_is_kept_when_it_is_ranked_first(self):
        """A plain good hook is not traded for a louder one: "A degree costs
        triple. It pays half." scored 1 and was going to be rewritten."""
        b = _brain([self.GOOD], [1, 2])
        self.assertIsNone(H.sharpen(dict(COFFEE), brain=b, log=lambda m: None))

    def test_a_hook_the_listener_fails_never_ships(self):
        b = _brain([self.GOOD], [1])
        self.assertIsNone(H.sharpen(dict(COFFEE), brain=b, log=lambda m: None))
        b = _brain([self.GOOD], [])
        self.assertIsNone(H.sharpen(dict(COFFEE), brain=b, log=lambda m: None))

    def test_no_verdict_means_no_change(self):
        """Fails CLOSED: a soft hook is a missed click, a false one a lie."""
        b = _brain([self.GOOD], None)
        self.assertIsNone(H.sharpen(dict(COFFEE), brain=b, log=lambda m: None))

    def test_no_brain_means_no_change(self):
        self.assertIsNone(H.sharpen(dict(COFFEE), brain=lambda p: None,
                                    log=lambda m: None))

    def test_a_hook_under_the_floor_is_not_heard(self):
        bad = "Your coffee vanished 4.41— and nobody told you"
        b = _brain([self.GOOD], [1])
        got = H.sharpen(dict(COFFEE, hook=bad), brain=b, log=lambda m: None)
        self.assertEqual(got, self.GOOD)
        self.assertNotIn(bad, b.calls[1])


class ANothingRoundIsAskedAgain(unittest.TestCase):
    def test_the_second_round_is_told_why_and_can_ship(self):
        prompts = []
        first = "Your coffee is secretly ruining your whole life."

        def brain(prompt):
            prompts.append(prompt)
            if "fact-checker" in prompt:
                if first in prompt.split("CANDIDATES:")[1]:
                    return json.dumps({"ranking": [], "why": {"2": "never said"}})
                return json.dumps({"ranking": [2]})
            if "ALREADY REFUSED" in prompt:
                return json.dumps({"hooks": [TheSharpener.GOOD]})
            return json.dumps({"hooks": [first]})
        got = H.sharpen(dict(COFFEE), brain=brain, log=lambda m: None)
        self.assertEqual(got, TheSharpener.GOOD)
        self.assertIn(first + " -> never said", prompts[2])
        self.assertEqual(H.ROUNDS, 2)


class TheListenerHearsLikeAViewer(unittest.TestCase):
    """2026-10-08, "our word hooks are trash". The listener is told what a
    viewer refuses, and it is the same call that checks the facts."""

    def test_it_is_told_to_fail_nonsense_and_templates(self):
        for words in ("fact-checker", "heard once", "not the viewer",
                      "template", "stop scrolling"):
            self.assertIn(words, H._LISTEN)

    def test_the_doctrine_shows_what_the_channel_got_wrong(self):
        for words in ("your octopus", "nobody told you", "Read it out loud"):
            self.assertIn(words.lower(), H.DOCTRINE.lower())

    def test_a_bare_number_into_a_dash_is_garbled(self):
        self.assertTrue(H.garbled("Your sky vanished 29.9— the ozone hole is healing"))
        self.assertEqual(H.garbled("Now it's 45% — and still spreading toward you."), [])
        self.assertEqual(H.garbled(TheSharpener.GOOD), [])


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
        self.assertIn("_hd.floor(", src)


if __name__ == "__main__":
    unittest.main()
