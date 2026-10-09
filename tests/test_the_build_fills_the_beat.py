"""The build fills the beat; the end is not a long still.

Operator, 2026-10-09: *"some animations hold too long at the end after all
the cool stuff has already happened ... in the self check out video the
first animation is great ... but by the end it's just stacking boxes"*.

Two things. A scene that finishes its story early is PACED to its window
(`scene_author.paced`): the build is stretched to land by `land_by`, so only
the last READ_S or so is the held picture. And a picture has to be made of
what the narration says happens: the glance's judge is given the beat's
narration and refuses a generic stack, tower or bar.
"""
from __future__ import annotations

import ast
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_learning import scene_author as SA  # noqa: E402


class TheHoldIsShort(unittest.TestCase):
    def test_a_beat_holds_about_the_reading_time_not_three_seconds(self):
        for secs in (6.0, 8.0):
            hold = (1 - SA.land_by(secs)) * secs
            self.assertLessEqual(hold, 2.3, secs)
            self.assertGreaterEqual(hold, SA.READ_S - 1e-9, secs)

    def test_an_early_scene_is_stretched_to_land_on_time(self):
        landed, target = 0.5, 0.7
        self.assertAlmostEqual(SA.paced(0.0, landed, target), 0.0)
        self.assertAlmostEqual(SA.paced(target, landed, target), landed)
        self.assertAlmostEqual(SA.paced(1.0, landed, target), 1.0)
        self.assertLess(SA.paced(0.35, landed, target), 0.35)   # the build is slower
        us = [SA.paced(k / 100, landed, target) for k in range(101)]
        self.assertEqual(us, sorted(us))                         # never runs backwards

    def test_a_scene_already_on_time_is_drawn_as_authored(self):
        for u in (0.0, 0.3, 0.9):
            self.assertEqual(SA.paced(u, 0.69, 0.7), u)
            self.assertEqual(SA.paced(u, None, 0.7), u)

    def test_the_renderer_paces_every_scene(self):
        tree = ast.parse((ROOT / "data_learning" / "subject_scenes.py").read_text())
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "_render_frames")
        src = ast.unparse(fn)
        self.assertIn("_sa.landed_at(scene, pts)", src)
        self.assertIn("_sa.paced(", src)

    def test_the_self_checkout_scene_lands_late_enough_now(self):
        from data_learning import subject_scenes as SS
        cfg = json.loads((ROOT / "data_learning" / "niche.config.json").read_text())
        sc = next((s for s in cfg["stories"] if s["slug"] == "self-checkout-cashier-jobs"), None)
        if sc is None:
            self.skipTest("story gone")
        from shared import rewrite_mailbox as rw
        g = sc["segments"][0]
        fn = SA.saved_scene(g, log=lambda m: None)
        if fn is None:
            self.skipTest("no saved scene")
        pts = [(str(p["label"]), float(p["value"])) for p in rw._dataset(g)["points"]]
        landed = SA.landed_at(fn, pts)
        self.assertLess(landed, SA.land_by(6.0) - 0.05)   # it was early ...
        self.assertAlmostEqual(SA.paced(SA.land_by(6.0), landed, SA.land_by(6.0)), landed)
        self.assertIsNotNone(SS)


class ThePictureIsTheStory(unittest.TestCase):
    def _glance(self, judge):
        seen = {"object": "a tower of cardboard boxes", "object_from": "its own shape",
                "tells": "", "substance": "boxes", "change": "boxes stack higher",
                "how_much": "dramatic", "shot": "a place"}
        answers = [seen, judge]
        with mock.patch.object(SA, "glance_frames", return_value=[]), \
             mock.patch.object(SA, "declared", return_value={
                 "HERO": "a tower of boxes", "SUBSTANCE": "cartons",
                 "CAUSE": "Data stacks them"}), \
             mock.patch.object(SA, "ask_glance", side_effect=lambda p, i: answers.pop(0)) as ask:
            out = SA.glance(lambda *a: None, [], log=lambda m: None,
                            say="Self-checkout loses 4 percent to theft.")
        return out, ask

    def test_a_generic_stack_is_refused_for_a_story_about_theft(self):
        out, ask = self._glance({"is_hero": True, "substance_fits": True,
                                 "cause_makes_sense": True, "story_fit": False})
        self.assertTrue(any("generic stand-in" in p for p in out), out)
        self.assertIn("loses 4 percent to theft", ask.call_args_list[1].args[0])

    def test_a_picture_of_the_story_passes(self):
        out, _ = self._glance({"is_hero": True, "substance_fits": True,
                               "cause_makes_sense": True, "story_fit": True})
        self.assertEqual(out, [])

    def test_the_writer_is_told(self):
        src = (ROOT / "data_learning" / "scene_author.py").read_text()
        self.assertIn("17. THE PICTURE IS WHAT THE NARRATION SAYS HAPPENS", src)
        self.assertIn("glance(fn, pts, log=log, say=say)", src)


if __name__ == "__main__":
    unittest.main()
