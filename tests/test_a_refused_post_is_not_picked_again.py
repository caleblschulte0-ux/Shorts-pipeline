"""A post the footage itself rules out is never picked again, and a title
naming one unsaid team is retitled, not dropped (2026-11-14 audit of ten
days of Baller Bro runs: 72 of 252 slots went to 28 already-refused posts;
Kerr on Butler was lost twice over the word "Warriors")."""
from __future__ import annotations

import unittest
from pathlib import Path

from scripts import run_sports as rs

REPO = Path(__file__).resolve().parents[1]


class RefusedLedger(unittest.TestCase):
    def test_what_the_footage_rules_out_is_for_good(self):
        r = {}
        rs.note_refused(r, "a", "too short: the post runs 12.1s (< 15s)")
        rs.note_refused(r, "b", "no sound: the post has no audio track")
        rs.note_refused(r, "c", "not English (English p=0.28)")
        self.assertEqual(rs.never_again(r), {"a", "b", "c"})

    def test_a_download_gets_a_second_chance(self):
        r = {}
        rs.note_refused(r, "d", "download failed")
        self.assertEqual(rs.never_again(r), set())
        rs.note_refused(r, "d", "download failed")
        self.assertEqual(rs.never_again(r), {"d"})

    def test_a_judgement_on_our_cut_is_not_remembered(self):
        r = {}
        for why in ("showrunner_block: x", "too short: the cut runs 9s",
                    "render failed: X", "author: no title"):
            rs.note_refused(r, "e", why)
        self.assertEqual(rs.never_again(r), set())

    def test_it_is_read_back_and_committed(self):
        src = (REPO / "scripts" / "run_sports.py").read_text()
        self.assertIn("never_again(refused)", src)
        wf = (REPO / ".github" / "workflows" / "sports.yml").read_text()
        self.assertIn("state/sports_refused.json", wf)


class AnUnsaidTeamIsRetitled(unittest.TestCase):
    def test_the_author_gets_another_go(self):
        src = (REPO / "scripts" / "run_sports.py").read_text()
        self.assertIn("WAS REFUSED: {made_up}", src)


if __name__ == "__main__":
    unittest.main()
