"""Operator, 2026-10-11, of Alinity talking in her kitchen, posted as a
zoomed copy of the frame on top, the frame itself in the middle and a
blurred smear under the hook: "Bro what the fuck was this video", then
"the clip's just shit. Some girl talking about how she needs to pee and
then it cuts off."

The stacked layout is for a STREAM: a small facecam box in a corner over
gameplay. A face big enough that its cam panel would take most of the
frame is an IRL camera, and stacking it shows the same picture twice.
"""
from __future__ import annotations

import unittest

from third_capture import author
from third_capture import shot_plan as sp


def _an(face_h: float, cx: float, cy: float, sw=1920, sh=1080) -> dict:
    s = sp.Subject(cx=cx * sw, cy=cy * sh, n=40,
                   hs=[face_h * sh] * 40, xs=[cx * sw] * 40, talk=1.0)
    s.presence = 0.9
    return {"sw": sw, "sh": sh, "subjects": [s]}


class AnIrlCameraIsNotAFacecam(unittest.TestCase):
    def test_alinitys_kitchen_is_shown_whole(self):
        # measured on the posted render's own frames: face 0.27 of the
        # height, centre-left, locked
        layout, _, why = sp.classify(_an(0.27, 0.41, 0.23))
        self.assertEqual(layout, "wide", why)

    def test_a_real_corner_facecam_still_stacks(self):
        layout, _, why = sp.classify(_an(0.10, 0.88, 0.80))
        self.assertEqual(layout, "facecam_gameplay", why)

    def test_the_limit_is_the_panel_the_render_would_crop(self):
        for h in (0.06, 0.10, 0.14):
            s = _an(h, 0.5, 0.5)["subjects"][0]
            self.assertLessEqual(sp._cam_area(s, 1920, 1080), sp.CAM_AREA_MAX)
        s = _an(0.27, 0.5, 0.5)["subjects"][0]
        self.assertGreater(sp._cam_area(s, 1920, 1080), sp.CAM_AREA_MAX)

    def test_a_big_face_is_still_a_closeup(self):
        layout, _, _ = sp.classify(_an(0.40, 0.5, 0.4))
        self.assertEqual(layout, "closeup")


def _words(text: str, start=20.0, step=0.4):
    return [{"w": w, "s": start + i * step, "e": start + (i + 1) * step - 0.05}
            for i, w in enumerate(text.split())]


class AClipDoesNotEndMidSentence(unittest.TestCase):
    def test_the_alinity_ending_is_refused(self):
        ws = _words("so I land in Austin and I have to pee so I pee and")
        dur = ws[-1]["e"] + 0.2
        why = author.cut_off_mid_sentence(ws, dur, dur)
        self.assertIsNotNone(why)
        self.assertIn("and", why)

    def test_a_finished_line_is_fine(self):
        ws = _words("and then the whole plane started clapping")
        dur = ws[-1]["e"] + 0.2
        self.assertIsNone(author.cut_off_mid_sentence(ws, dur, dur))

    def test_a_cut_that_stops_before_the_source_ends_is_not_judged_here(self):
        ws = _words("we made it and then the pilot said so")
        dur = ws[-1]["e"] + 8.0
        self.assertIsNone(author.cut_off_mid_sentence(ws, ws[-1]["e"], dur))

    def test_silence_after_the_last_word_is_an_ending(self):
        ws = _words("that is the funniest thing and")
        dur = ws[-1]["e"] + 3.0
        self.assertIsNone(author.cut_off_mid_sentence(ws, dur, dur))

    def test_the_clip_gate_uses_it(self):
        import ast
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent / "scripts"
               / "run_third.py").read_text()
        calls = {n.func.attr for n in ast.walk(ast.parse(src))
                 if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute)}
        self.assertIn("cut_off_mid_sentence", calls)
