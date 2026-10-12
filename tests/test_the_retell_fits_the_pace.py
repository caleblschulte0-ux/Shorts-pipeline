"""A retell that is right except for its length still posts.

2026-10-12: the morning run held all 94 queued stories and posted nothing.
The 14 that cleared the editorial gate were held because their narration
read off numbers, and the retell that fixes that was refused four times
each, mostly for two reasons that had nothing to do with the facts:

  * a say of 25 to 28 words against a cap of 24 (44 of 106 refusals). The
    writer is now asked for a few words under the cap, and a refusal says
    how many words to cut;
  * the on-screen TOPIC label, written in Title Case, was checked as part of
    the beat's sentence, so "Bats Collapse Versus Farms" named three new
    things. A label word the narration also uses in lower case is a common
    word; a real name ("France") is still refused.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import narration as N  # noqa: E402
from shared import pacing as P  # noqa: E402
from shared import rewrite_mailbox as RW  # noqa: E402


class ATopicLabelIsNotASentence(unittest.TestCase):
    ORIG = "Bat numbers fell by ninety percent across the states."
    PLAIN = ORIG + " The colonies collapsed, and farms pay for the pests versus the bats."

    def test_title_case_common_words_are_not_names(self):
        self.assertEqual(RW._topic_entities("Bats Collapse Versus Farms",
                                            self.ORIG, set(), self.PLAIN), [])

    def test_a_real_name_in_a_label_is_still_refused(self):
        self.assertEqual(RW._topic_entities("Farms Pay France",
                                            self.ORIG, set(), self.PLAIN),
                         ["France"])

    def test_a_name_inside_the_say_is_still_refused(self):
        self.assertEqual(RW._entities_ok("The bats fled to France last year.",
                                         self.ORIG, set()), ["France"])


class ARefusalSaysHowMuchToCut(unittest.TestCase):
    def test_cut_by(self):
        self.assertEqual(N._cut_by("segment 2: say is 26 words (max 24)"),
                         "segment 2: say is 26 words (max 24): cut "
                         f"{2 + N.AIM_UNDER} words from it")
        self.assertEqual(N._cut_by("segment 1: new named entity"),
                         "segment 1: new named entity")

    def test_both_writers_are_asked_for_less_than_the_cap(self):
        self.assertIn("{aim}", N._PROMPT)
        self.assertIn("{aim}", P._PROMPT)
        sc = {"title": "t", "hook": "h", "closing": "c", "question": "q",
              "segments": [{"topic": "x", "say": "one two"}]}
        aim = P.budget()["say_words"] - 4
        self.assertIn(f"aim for about {aim}", P._prompt(sc, P.budget()))

    def test_the_retell_prompt_formats(self):
        seen = []
        sc = {"slug": "s", "title": "Bats", "hook": "h", "closing": "c",
              "segments": [{"topic": "x", "say": "1 2 and 3 bats"}]}
        N.retell(sc, brain=lambda p: seen.append(p) or None, log=lambda m: None,
                 tries=1)
        if seen:
            self.assertIn(f"aim for about {RW.MAX_SAY_WORDS - N.AIM_UNDER} words",
                          seen[0])


if __name__ == "__main__":
    unittest.main()
