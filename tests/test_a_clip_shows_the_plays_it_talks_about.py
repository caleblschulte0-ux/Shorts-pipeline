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
        self.assertIn('broll(c, words, dur, meta["edit"], raw,', src)
        self.assertIn('"cut_in")', src)

    def test_the_author_is_told_their_own_plays_count(self):
        self.assertIn("Their OWN plays count", author.SYSTEM)
        self.assertNotIn("Never the person already on screen talking",
                         author.SYSTEM)


if __name__ == "__main__":
    unittest.main()


class TheGameItselfGetsNoCutIn(unittest.TestCase):
    def _run(self, talks):
        with mock.patch.object(sports_samples, "talking",
                               return_value=talks), \
             mock.patch.object(sports_samples, "_brain", return_value={
                 "broll": [{"who": "x", "look": "x", "at": 3,
                            "said": "fined"}]}) as b:
            edit = sports_samples.broll(C, WORDS, 30.0, {},
                                        Path("/tmp/raw.mp4"), Path("/tmp/w"))
        return edit, b

    def test_a_broadcast_of_the_play_is_left_alone(self):
        edit, b = self._run(False)
        b.assert_not_called()
        self.assertNotIn("broll", edit)

    def test_a_locker_room_is_asked(self):
        edit, b = self._run(True)
        self.assertTrue(edit["broll"])

    def test_no_brain_to_look_means_nothing_added(self):
        from shared import shot_relevance
        with mock.patch.object(shot_relevance, "judge_panels",
                               return_value=None), \
             mock.patch("funnel.find_footage._frame",
                        return_value=Path("/tmp/f.png")):
            self.assertFalse(sports_samples.talking(
                Path("/tmp/raw.mp4"), {}, 30.0, Path("/tmp/w")))
        with mock.patch.object(shot_relevance, "judge_panels",
                               return_value={0: {"depicts": True},
                                             1: {"depicts": True},
                                             2: {"depicts": False}}), \
             mock.patch("funnel.find_footage._frame",
                        return_value=Path("/tmp/f.png")):
            self.assertTrue(sports_samples.talking(
                Path("/tmp/raw.mp4"), {}, 30.0, Path("/tmp/w")))


class NeverTheSamePlayTwice(unittest.TestCase):
    def test_the_second_cut_in_avoids_the_first(self):
        from third_capture import cut_in
        from funnel import find_footage
        calls = []

        def fake(who, look, **kw):
            calls.append(kw.get("avoid"))
            return {"path": f"/x{len(calls)}.mp4", "url": "u", "from_s": 40.0,
                    "secs": 3.2}
        items = [{"who": "Cam Skattebo", "look": "a", "at": 5, "secs": 3.2},
                 {"who": "Cam Skattebo", "look": "b", "at": 15, "secs": 3.2}]
        with mock.patch.object(find_footage, "find", side_effect=fake):
            got = cut_in.ready(items, Path("/tmp"))
        self.assertEqual(calls[0], [])
        self.assertEqual(calls[1], [{"url": "u", "from_s": 40.0}])
        self.assertEqual(len(got), 2)

    def test_find_skips_an_avoided_shot_and_names_each_cut_apart(self):
        src = (REPO / "funnel" / "find_footage.py").read_text()
        self.assertIn("for a in avoid or []", src)
        self.assertIn('_{start:.0f}_cut.mp4', src)
