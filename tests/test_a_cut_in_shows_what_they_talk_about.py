"""A cut-in is the default, not the exception (operator, 2026-11-14: "it's
a cut-in. They're talking about something, it shows that something").
A watched play longer than the slot keeps its end instead of being thrown
away, and what the judge says was never shown becomes a cut-in on the
repair."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from funnel import find_footage as ff
from scripts import sports_samples as ss


def _words(n=40):
    return [{"w": f"w{i}", "s": float(i), "e": i + 0.5} for i in range(n)]


class TheJudgesMissingThingIsCutIn(unittest.TestCase):
    def test_notes_reach_the_question_and_add_to_the_authors_picks(self):
        seen = {}

        def brain(user, system):
            seen["user"] = user
            return {"broll": [{"who": "Jimmy Butler", "at": 12.0,
                               "look": "Jimmy Butler sideline coach outfit"}]}

        edit = {"broll": [{"who": "Steph Curry", "at": 3.0, "look": "x"}],
                "show": [{"thing": "y", "at": 20.0}]}
        with mock.patch.object(ss, "_brain", brain):
            ss.broll({"who": "Steve Kerr", "post_title": "t"}, _words(),
                     40.0, edit,
                     notes="Problem: Butler's coach outfit is never shown")
        self.assertIn("coach outfit is never shown", seen["user"])
        self.assertEqual([b["at"] for b in edit["broll"]], [3.0, 12.0])

    def test_the_brief_makes_it_the_default(self):
        self.assertIn("THE DEFAULT", ss.BROLL_SYSTEM)
        self.assertNotIn("[] when the words name nothing showable",
                         ss.BROLL_SYSTEM)


class ALongPlayKeepsItsEnd(unittest.TestCase):
    def test_a_moment_longer_than_the_slot_is_cut_to_its_end(self):
        cuts = {}

        def cut(video, start, length, out):
            cuts["at"] = (start, length)
            return out

        with mock.patch("funnel.hot_clips.youtube",
                        lambda *a, **k: [{"url": "u", "title": "Brunson"}]), \
             mock.patch.object(ff, "_downloads",
                               lambda c, f: iter([(0, c[0], Path("v.mp4"))])), \
             mock.patch.object(ff, "_seconds", lambda v: 300.0), \
             mock.patch.object(ff, "portrait", lambda v: False), \
             mock.patch.object(ff, "_frame", lambda *a, **k: Path("f.png")), \
             mock.patch.object(ff, "judge",
                               lambda fr, l, t="": {i: {"depicts": True}
                                                    for i, _ in fr}), \
             mock.patch.object(ff, "watch", lambda *a, **k: (160.5, 166.0)), \
             mock.patch.object(ff, "cut", cut):
            hit = ff.find("Jalen Brunson", "Brunson footwork", secs=4.8,
                          work="/tmp")
        self.assertIsNotNone(hit)
        start, length = cuts["at"]
        self.assertAlmostEqual(start + length, 166.0, places=2)
        self.assertAlmostEqual(length, 4.8, places=2)


if __name__ == "__main__":
    unittest.main()
