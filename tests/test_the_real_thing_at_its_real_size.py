"""The real thing, at its real size, in its real place.

Operator, 2026-10-28, of two frames from one video (NYC's 311 line and its
noise calls): a brick walk-up with a fire escape and a water tower among
other buildings looked good; a red rotary phone the size of a truck, alone
on an empty desert with Data standing on top of it pointing, *"look like
shit ai slop"*. A giant icon of an object is the look of a generated
picture. The blind viewer now says whether the main object is true to life
or blown up, a blown-up one is refused, prompt rule 24 says so, and the look
again names it.

The rule is new, so the scene STANDARD moved; a scene drawn to the last one
is in GRACE: the posting run keeps using it, and only the predraw re-judges
it, on its own clock (a bump with no grace cost the whole of 2026-10-23).
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_learning import scene_author as SA  # noqa: E402

PTS = [["Noise", 18.0], ["Everything else", 82.0]]
#: the truck-sized phone the operator saw (nyc-noise-complaints-per-day hook)
GIANT_PHONE = "dd021fa54f684e20a66f19bb1e00c54bc8ba50259a16baa4f9a35b9099293784"


class ABlownUpObjectIsRefused(unittest.TestCase):
    def _glance(self, size, setting="its own place"):
        seen = {"object": "red rotary telephone", "object_from": "its own shape",
                "tells": "dial, handset", "substance": "sound waves",
                "change": "the handset jumps and rings louder",
                "how_much": "dramatic", "shot": "a place", "heap": "no",
                "size": size, "setting": setting}
        answers = [seen, {"is_hero": True, "substance_fits": True,
                          "cause_makes_sense": True, "story_fit": True,
                          "heap_fits": True}]
        with mock.patch.object(SA, "glance_frames", return_value=[]), \
             mock.patch.object(SA, "declared", return_value={
                 "HERO": "a telephone", "SUBSTANCE": "sound waves",
                 "CAUSE": "Data answers it"}), \
             mock.patch.object(SA, "ask_glance",
                               side_effect=lambda p, i: answers.pop(0)):
            return SA.glance(lambda *a: None, PTS, log=lambda m: None,
                             say="New York is losing its patience.")

    def test_a_truck_sized_phone_is_refused(self):
        out = self._glance("blown up", "bare ground")
        self.assertTrue(any("real size" in p and "rule 24" in p for p in out), out)
        self.assertTrue(any("bare ground" in p for p in out), out)

    def test_a_phone_at_its_real_size_passes(self):
        self.assertEqual(self._glance("true to life"), [])

    def test_bare_ground_alone_is_not_a_refusal(self):
        # THE PILE, a bar the operator chose, was called "bare ground" by one
        # viewer in two; only the size refuses.
        self.assertEqual(self._glance("true to life", "bare ground"), [])


class TheViewerIsAskedAndTheBrainIsTold(unittest.TestCase):
    def test_the_viewer_is_asked_about_size_and_setting(self):
        self.assertIn('"size"', SA._LOOK)
        self.assertIn("blown up", SA._LOOK)
        self.assertIn('"setting"', SA._LOOK)

    def test_rule_24_is_in_the_prompt(self):
        p = SA.build_prompt("t", "x", "y", PTS, "")
        self.assertIn("24. THE REAL THING, AT ITS REAL SIZE, IN ITS REAL PLACE", p)
        self.assertIn("shit ai slop", p)

    def test_the_look_again_names_it(self):
        self.assertIn("blown up to the", SA._LOOK_AGAIN)


class TheNewStandardDoesNotCostAPostingDay(unittest.TestCase):
    def setUp(self):
        self._strict = SA.STRICT

    def tearDown(self):
        SA.STRICT = self._strict

    def test_the_standard_moved_for_the_new_rule(self):
        self.assertGreaterEqual(SA.STANDARD, "2026-10-28")

    def test_the_posting_run_keeps_a_graced_scene(self):
        SA.STRICT = False
        code = "# scene standard: 2026-10-22\ndef scene(cr, t, u, pts, host):\n    pass\n"
        self.assertTrue(SA.current(code))
        self.assertTrue(SA.current(SA.stamped(code)))
        self.assertFalse(SA.current(code.replace("2026-10-22", "2026-10-16.2")))

    def test_the_predraw_rejudges_a_graced_scene(self):
        SA.STRICT = True
        code = "# scene standard: 2026-10-22\ndef scene(cr, t, u, pts, host):\n    pass\n"
        self.assertFalse(SA.current(code))
        self.assertTrue(SA.current(SA.stamped(code)))

    def test_the_predraw_runs_strict(self):
        tree = ast.parse((ROOT / "scripts" / "predraw_scenes.py").read_text())
        main = next(n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == "main")
        sets = [n for n in ast.walk(main) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Attribute) and t.attr == "STRICT"
                        for t in n.targets)
                and isinstance(n.value, ast.Constant) and n.value.value is True]
        self.assertTrue(sets, "predraw must set scene_author.STRICT = True")

    def test_saved_scenes_are_checked_through_current(self):
        src = (ROOT / "data_learning" / "scene_author.py").read_text()
        self.assertNotIn("standard_of(code) != STANDARD", src)


class TheGiantPhoneIsGone(unittest.TestCase):
    def test_no_saved_scene_is_the_giant_phone(self):
        cfg = json.loads((ROOT / "data_learning" / "niche.config.json").read_text())
        for s in cfg.get("stories", []):
            codes = [s.get("hook_scene"), s.get("closing_scene")] + [
                g.get("illustrated_scene") for g in s.get("segments") or []]
            for c in codes:
                if isinstance(c, str):
                    self.assertNotEqual(
                        hashlib.sha256(c.encode()).hexdigest(), GIANT_PHONE,
                        s.get("slug"))


if __name__ == "__main__":
    unittest.main()
