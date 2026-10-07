"""Operator, 2026-10-07, on two brain-drawn scenes side by side: "I like the
pile one but the bone one no." The pile: a field, one number, a heap of
plastic that grows to three times its size with its old outline on it. The
bone: a femur standing still in a window, -1.5%, 1% and 1.5x stacked beside
it, and a label printed across Data.

What separates them is held here: at most MAX_HEADLINES big numbers in a
frame, no label on top of Data (measured in verify), and a viewer who must
see the change as more than 'barely' and the picture as a place, not a
diagram (asked in the glance). The teachers pass both: that is
test_the_brain_draws_the_scene.TheTeachersPassTheSameChecks."""
import unittest
from unittest import mock

from tests.test_the_brain_draws_the_scene import GOOD_MIN

PTS = [["2019", 1.05], ["2025", 4.41]]

CROWDED = '''
def scene(cr, t, u, pts, host):
    """HERO: a jar
    SUBSTANCE: water
    CAUSE: Data pours water into the jar"""
    vgrad(cr, [(0, (90, 120, 160)), (1, (40, 60, 90))], 0, H)
    host("pour", 300, 1450, 220)
    fit_readout(cr, "1.05", "2019", 80, 420, size=130)
    fit_readout(cr, "4.41", "2025", 80, 700, size=110)
    fit_readout(cr, "3.36", "more", 80, 980, size=90)
'''

ON_DATA = '''
def scene(cr, t, u, pts, host):
    """HERO: a jar
    SUBSTANCE: water
    CAUSE: Data pours water into the jar"""
    vgrad(cr, [(0, (90, 120, 160)), (1, (40, 60, 90))], 0, H)
    host("pour", 540, 1450, 220)
    fit_readout(cr, "4.41", "2025", 80, 420, size=130)
    text(cr, "since 2019", 540, 1340, 40, INK, anchor="center")
'''


def _problems(src):
    from data_learning import scene_author as SA
    return SA.verify(SA.compile_scene(src), PTS)


class AViewerGlancesTheyDoNotReadATable(unittest.TestCase):

    def test_three_big_numbers_in_one_frame_are_refused(self):
        ps = _problems(CROWDED)
        self.assertTrue(any("big numbers at once" in p for p in ps), ps)

    def test_a_label_on_top_of_data_is_refused(self):
        ps = _problems(ON_DATA)
        self.assertTrue(any("over Data" in p for p in ps), ps)

    def test_the_brain_is_told(self):
        from data_learning import scene_author as SA
        p = SA.build_prompt("t", "x", "y", PTS, "")
        self.assertIn("ONE NUMBER, AND THE CHANGE IS BIG ON SCREEN", p)
        self.assertIn(f"At most {SA.MAX_HEADLINES} big numbers", p)


class TheChangeMustBeSeenAndTheShotMustBeAPlace(unittest.TestCase):

    def _glance(self, how_much, shot):
        from data_learning import scene_author as SA

        def viewer(prompt, images):
            if images:
                return {"object": "a glass jar", "object_from": "its own shape",
                        "tells": "lid", "substance": "water",
                        "change": "the water rises", "how_much": how_much,
                        "shot": shot}
            return {"is_hero": True, "substance_fits": True,
                    "cause_makes_sense": True, "why": ""}
        fn = SA.compile_scene(GOOD_MIN)
        with mock.patch.object(SA, "ask_glance", viewer):
            return SA.glance(fn, PTS, log=lambda m: None)

    def test_a_change_that_barely_shows_is_refused(self):
        ps = self._glance("barely", "a place")
        self.assertTrue(any("BIG enough to see" in p for p in ps), ps)

    def test_a_diagram_is_refused(self):
        ps = self._glance("dramatic", "a diagram")
        self.assertTrue(any("diagram, not a place" in p for p in ps), ps)

    def test_a_clear_change_in_a_place_passes(self):
        self.assertEqual(self._glance("clear", "a place"), [])

    def test_the_blind_viewer_is_asked_both(self):
        from data_learning import scene_author as SA
        self.assertIn('"how_much"', SA._LOOK)
        self.assertIn('"shot"', SA._LOOK)


if __name__ == "__main__":
    unittest.main()


BROKEN = '''
def scene(cr, t, u, pts, host):
    """HERO: a jar
    SUBSTANCE: water
    CAUSE: Data pours water into the jar"""
    raise ValueError("no")
'''


class TheBrainLooksAtWhatItDrew(unittest.TestCase):
    """The brain that draws had never seen a frame of its own: it wrote
    code, the code was measured, another viewer named the object. A scene
    that passes now gets one look again — its own frames beside THE SHOT —
    and only a redraw that passes every same check replaces it."""

    def _author(self, redraw, budget=None):
        import os
        from pathlib import Path
        from data_learning import scene_author as SA
        asks = []

        def brain(prompt, model=None, timeout=None, images=False):
            asks.append((prompt, images))
            if images:
                for line in prompt.splitlines():
                    if line.startswith("- ") and line.endswith(".png"):
                        self.assertTrue(Path(line[2:]).exists(), line)
                return redraw
            return GOOD_MIN
        old = SA._DEADLINE
        try:
            if budget is not None:
                SA.set_budget(budget)
            with mock.patch.object(SA, "ask_brain", brain), \
                    mock.patch.object(SA, "ask_glance", return_value=None):
                fn, code = SA.author("t", "x", "y", PTS, log=lambda m: None)
        finally:
            SA._DEADLINE = old
        return fn, code, asks

    def test_a_redraw_that_passes_replaces_the_first_draft(self):
        better = GOOD_MIN.replace("def scene(", "# looked again\ndef scene(")
        fn, code, asks = self._author(better)
        self.assertEqual(len(asks), 2)
        self.assertFalse(asks[0][1])
        self.assertTrue(asks[1][1], "the look again must let the brain READ")
        self.assertIn("THE SHOT", asks[1][0])
        self.assertIn("the bone one no", asks[1][0])
        self.assertIn("# looked again", code)

    def test_a_redraw_that_fails_keeps_the_scene_that_passed(self):
        fn, code, asks = self._author(BROKEN)
        self.assertEqual(len(asks), 2)
        self.assertEqual(code, GOOD_MIN)
        self.assertIsNotNone(fn)

    def test_no_budget_for_it_skips_it(self):
        from data_learning import scene_author as SA
        fn, code, asks = self._author(BROKEN, budget=SA.LOOK_AGAIN_MIN_S - 60)
        self.assertEqual(len(asks), 1)
        self.assertIsNotNone(fn)
