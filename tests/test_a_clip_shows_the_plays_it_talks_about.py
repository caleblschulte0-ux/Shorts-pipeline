"""A clip that talks about a play SHOWS the play.

Operator, 2026-10-28, after the edit-basics fixes: *"Now we are going to
far the wrong way like that can skattebo clip show the plays he got fined
on"*. Skattebo talked about the fines for lowering his helmet; the author,
asked for `broll` among a dozen other things, gave none on any clip of
the batch, and the plays never appeared.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.append(str(REPO / "scripts"))

from scripts import sports_samples  # noqa: E402
from third_capture import author  # noqa: E402

WORDS = [{"w": w, "s": float(i), "e": i + 0.8} for i, w in enumerate(
    "I got fined for lowering my helmet and I will play for free".split())]
C = {"who": "Cam Skattebo", "post_title": "Skattebo says he'll play for free"}


class AClipWithNoCutInIsAsked(unittest.TestCase):
    def test_no_broll_gets_its_own_question(self):
        ans = {"broll": [{"who": "Cam Skattebo", "at": 2.1, "said": "fined",
                          "look": "Cam Skattebo lowers helmet run Giants"}]}
        with mock.patch.object(sports_samples, "_brain",
                               return_value=ans) as b:
            edit = sports_samples.broll(C, WORDS, 30.0, {"mood": ""})
        self.assertIn("own plays", b.call_args[0][1].lower())
        self.assertIn("[5.0] my helmet", b.call_args[0][0])  # fine stamps
        self.assertEqual(edit["broll"][0]["said"], "fined")

    def test_an_author_cut_in_is_kept_and_nothing_asked(self):
        have = {"broll": [{"who": "x", "look": "x", "at": 3}]}
        with mock.patch.object(sports_samples, "_brain") as b:
            sports_samples.broll(C, WORDS, 30.0, have)
        b.assert_not_called()

    def test_nothing_showable_leaves_the_clip_alone(self):
        with mock.patch.object(sports_samples, "_brain",
                               return_value={"broll": []}):
            self.assertNotIn("broll", sports_samples.broll(
                C, WORDS, 30.0, {}))
        with mock.patch.object(sports_samples, "_brain", return_value=None):
            self.assertNotIn("broll", sports_samples.broll(
                C, WORDS, 30.0, {}))

    def test_make_asks_and_the_ledger_says_what_was_cut_in(self):
        src = (REPO / "scripts" / "sports_samples.py").read_text()
        self.assertIn('broll(c, words, dur, meta["edit"])', src)
        self.assertIn('"cut_in")', src)

    def test_the_author_is_told_their_own_plays_count(self):
        self.assertIn("Their OWN plays count", author.SYSTEM)
        self.assertNotIn("Never the person already on screen talking",
                         author.SYSTEM)


if __name__ == "__main__":
    unittest.main()
