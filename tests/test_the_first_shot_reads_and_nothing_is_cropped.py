"""The first shot reads in a second, nothing is cropped, and Data holds still.

Operator, 2026-10-11, of the pollen and polio videos posted that day:

  * *"on the carbon dioxide one at the beginning ... I have no idea what the
    fuck's going on here. It makes me instantly want to scroll ... the dotted
    lines make it really confusing ... our first shots need to be great. They
    need to be instantly recognizable"* — a gas tank under dashed ghost
    circles. A HOOK scene may not draw the dashed scale marks (they belong to
    the beats), and its brief asks for one big everyday thing.
  * *"it's cropped terribly and cut off at the end"* — the last beat was
    shrunk into a box under the closing line, and its "1990" ran off the
    right edge. A label off the frame is refused; the closing is full frame.
  * *"he'll do something, and then instead of ... standing still ... he'll
    just flail his arms around a bunch"* — measured: 15 to 21 swings back and
    forth in a 6-second beat, the act restarting before it landed. A new
    beat of the same act now waits for the last one to land and rest.
"""
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_learning import scene_author as SA  # noqa: E402
from data_learning import subject_scenes as SS  # noqa: E402

GHOSTED = '''
def scene(cr, t, u, pts, host):
    cr.arc(500, 500, 100, 0, 6.28)
    ghost(cr, a=0.9)
    host("point", 540, 1400, 300)
'''
CLEAN = '''
def scene(cr, t, u, pts, host):
    cr.arc(500, 500, 100, 0, 6.28)
    cr.fill()
    host("point", 540, 1400, 300)
'''


class TheOpeningIsAnInstantRead(unittest.TestCase):
    def test_dashed_scale_marks_are_refused_in_an_opening(self):
        self.assertTrue(SA.opening_problems(GHOSTED))
        self.assertIn("ghost", SA.opening_problems(GHOSTED)[0])
        self.assertTrue(SA.opening_problems(CLEAN.replace("cr.fill()",
                                                          "cr.set_dash([4, 4])")))
        self.assertEqual(SA.opening_problems(CLEAN), [])

    def test_the_hook_is_drawn_and_redrawn_as_an_opening(self):
        src = inspect.getsource(SA.scene_for_bookend)
        self.assertIn('opening=kind == "hook"', src)
        self.assertIn('opening=index == "hook"', inspect.getsource(SA.redraw))
        self.assertIn("opening_problems(code)", inspect.getsource(SA.author))

    def test_a_saved_hook_with_ghosts_is_redrawn(self):
        story = {"hook": "x", "hook_scene": SA.stamped(GHOSTED), "hook_data": 0,
                 "segments": [{}]}
        with mock.patch.object(SA, "_saved_craft", return_value=[]):
            self.assertIsNone(SA.saved_bookend(story, "hook", 1, log=lambda m: None))
            story["hook_scene"] = SA.stamped(CLEAN)
            self.assertIsNotNone(SA.saved_bookend(story, "hook", 1, log=lambda m: None))

    def test_the_brief_asks_for_a_familiar_thing(self):
        self.assertIn("instantly want to scroll", SA.HOOK_BRIEF)
        self.assertIn("NO dashed outlines", SA.HOOK_BRIEF)


class NothingRunsOffTheFrame(unittest.TestCase):
    def test_a_label_past_the_edge_is_refused(self):
        code = CLEAN.replace("cr.fill()",
                             'cr.fill()\n    text(cr, "1990", 1050, 600, 60)')
        probs = SA.verify(SA.compile_scene(code), [["1990", 1.0], ["2020", 2.0]])
        self.assertTrue(any("off the edge of the frame" in p for p in probs), probs)

    def test_a_label_inside_is_not(self):
        code = CLEAN.replace("cr.fill()",
                             'cr.fill()\n    text(cr, "1990", 700, 600, 60)')
        probs = SA.verify(SA.compile_scene(code), [["1990", 1.0], ["2020", 2.0]])
        self.assertFalse(any("off the edge" in p for p in probs), probs)

    def test_saved_scenes_are_rejudged_under_it(self):
        self.assertGreater(SA.STANDARD, "2026-10-11")


_SEEN = []


def text(cr, s, *a, **k):            # the scene below's `text`, recorded
    _SEEN.append(s)


def _beat_scene(cr, t, u, pts, host):
    _SEEN.append(("u", u))
    text(cr, "21%", 100, 300, 120)
    host("point", 540, 1400, 300)


class TheClosingIsFullFrame(unittest.TestCase):
    def test_the_finish_is_the_finished_picture_without_its_words(self):
        import cairo
        _SEEN.clear()
        fin = SS.wordless_finish(_beat_scene)
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
        fin(cairo.Context(surf), 1.0, 0.2, [], lambda *a, **k: None)
        self.assertEqual(_SEEN, [("u", 1.0)])           # u held, no words
        self.assertIs(globals()["text"], text)          # restored after
        self.assertIs(SS.text, SS.I.text)

    def test_the_renderer_uses_it_and_never_shrinks_a_closing(self):
        src = (ROOT / "data_learning" / "studio_render.py").read_text()
        self.assertIn("_ss.wordless_finish(_scene)", src)
        self.assertIn('"host_baked": True, "closing": True', src)
        self.assertIn('and not sp.get("closing")', src)


class DataHoldsStill(unittest.TestCase):
    def test_a_fast_beat_does_not_restart_the_act_before_it_lands(self):
        clock, starts, last = {}, 0, None
        for f in range(180):                       # beat bumped every 18 frames
            ph = SS.act_phase(clock, ("dig", f // 18), f)
            if last is not None and ph < last:
                starts += 1
            last = ph
        # 9 bumps in 6s; one swing plus its rest is 39 frames: at most 4 restarts
        self.assertLessEqual(starts, 4)
        self.assertGreaterEqual(starts, 3)

    def test_a_new_act_starts_at_once(self):
        clock = {}
        SS.act_phase(clock, ("point", 0), 0)
        self.assertEqual(SS.act_phase(clock, ("dig", 0), 5), 0.0)


if __name__ == "__main__":
    unittest.main()
