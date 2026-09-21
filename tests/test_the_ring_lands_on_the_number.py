"""THE BLUE RING CIRCLES THE NUMBER BEING SAID — ON THE PICTURE ON SCREEN.

Operator, 2026-09-21: *"the blue circle that circles the data we are
talking about misses about 75% of the time or it comes too early or late."*

Two structural causes, read off the renderer:

  WHERE. `_plan_events` placed the ring from `seg.anchors`, the coordinates
  of the CHEAP build `story.build` runs to discover which numbers a line
  names. Since the per-span edit a beat shows a sequence of visuals — a
  mechanic, a machine, then maybe a chart — each with its own geometry, and
  that cheap chart is almost never on screen. The ring circled where a
  number sat on a picture nobody saw. Now: the anchors of the span that is
  on screen when the number is said; none during a full-frame visual (it
  records no number positions) rather than a wrong one; and never before
  the span's build has reached its final frame, where the anchors are.

  WHEN. `_phrase_frac` measured the fraction by WORD COUNT of the written
  sentence. "$1,920" is one written word and eleven spoken syllables. Now it
  measures characters of the SPOKEN text (`_tts_text`), finds the phrase in
  that same spelled text, and returns None — no ring — when the phrase is
  not in the sentence, instead of a mid-sentence guess.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib                                            # noqa: E402
matplotlib.use("Agg")

from data_learning import studio_render as SR                # noqa: E402
from data_learning import charts                             # noqa: E402


class _Seg:
    def __init__(self, sentence, punches, anchors=None, spans=None, role=""):
        self.sentence = sentence
        self.punches = punches
        self.anchors = anchors or []
        self.role = role
        if spans is not None:
            self.spans = spans


class _Story:
    def __init__(self, segments):
        self.segments = segments


def _anchor(value, cx=100.0, cy=200.0, w=40.0, h=20.0):
    return {"value": float(value), "cx": cx, "cy": cy, "w": w, "h": h}


def _punch(text, phrase=None):
    return {"text": text, "phrase": phrase if phrase is not None else text,
            "duration": 1.8, "color": "#ffffff"}


WINDOWS = [(0.0, 3.0), (3.0, 13.0), (13.0, 20.0)]     # hook, seg0, closing


class WhereTheRingLands(unittest.TestCase):

    def test_it_uses_the_span_on_screen_not_the_beats_cheap_chart(self):
        stale = _anchor(82, cx=900, cy=900)
        live = _anchor(82, cx=100, cy=200)
        seg = _Seg("It made 82 million tons of it.", [_punch("82", "82")],
                   anchors=[stale],
                   spans=[{"kind": "mechanic", "anchors": [], "t0": 3.0, "t1": 8.0, "full_by": 0.8},
                          {"kind": "bars", "anchors": [live], "t0": 8.0, "t1": 13.0, "full_by": 0.5}])
        with mock.patch.object(SR, "_phrase_frac", return_value=0.7):   # said at 10.0s
            ev = SR._plan_events(_Story([seg]), WINDOWS)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["xy"], SR._screen(100, 200))
        self.assertNotEqual(ev[0]["xy"], SR._screen(900, 900), "the stale chart's anchor")

    def test_no_ring_during_a_full_frame_visual(self):
        """A mechanic records no number positions: nothing to circle."""
        seg = _Seg("It made 82 million tons.", [_punch("82")], anchors=[_anchor(82)],
                   spans=[{"kind": "mechanic", "anchors": [], "t0": 3.0, "t1": 13.0, "full_by": 0.8}])
        with mock.patch.object(SR, "_phrase_frac", return_value=0.3):
            ev = SR._plan_events(_Story([seg]), WINDOWS)
        self.assertIsNone(ev[0]["xy"])
        self.assertIsNone(ev[0]["ring0"])
        self.assertEqual(ev[0]["punch"]["text"], "82", "the punch text still shows")

    def test_a_full_frame_anchor_dict_is_in_frame_coordinates_already(self):
        with mock.patch.dict(charts.FULLFRAME_RENDERERS, {"fake_full": object()}):
            seg = _Seg("x 82 y", [_punch("82")],
                       spans=[{"kind": "fake_full", "anchors": [_anchor(82, cx=500, cy=700)],
                               "t0": 3.0, "t1": 13.0, "full_by": 0.5}])
            with mock.patch.object(SR, "_phrase_frac", return_value=0.9):
                ev = SR._plan_events(_Story([seg]), WINDOWS)
        self.assertEqual(ev[0]["xy"], (500.0, 700.0))

    def test_the_nearest_stranger_is_not_a_match(self):
        """A punch for 82 must not circle a 61 because 61 is the closest
        number on this span."""
        seg = _Seg("x 82 y", [_punch("82")],
                   spans=[{"kind": "bars", "anchors": [_anchor(61)], "t0": 3.0, "t1": 13.0, "full_by": 0.5}])
        with mock.patch.object(SR, "_phrase_frac", return_value=0.5):
            ev = SR._plan_events(_Story([seg]), WINDOWS)
        self.assertIsNone(ev[0]["xy"])

    def test_a_story_read_before_render_still_gets_the_old_answer(self):
        seg = _Seg("x 82 y", [_punch("82")], anchors=[_anchor(82, cx=300, cy=400)])
        with mock.patch.object(SR, "_phrase_frac", return_value=0.5):
            ev = SR._plan_events(_Story([seg]), WINDOWS)
        self.assertEqual(ev[0]["xy"], SR._screen(300, 400))


class WhenTheRingAppears(unittest.TestCase):

    def test_it_waits_for_the_build_to_put_the_number_there(self):
        """Said at 4.0s, but the bars finish rising at 3 + 10*0.6 = 9.0s."""
        seg = _Seg("x 82 y", [_punch("82")],
                   spans=[{"kind": "bars", "anchors": [_anchor(82)], "t0": 3.0, "t1": 13.0, "full_by": 0.6}])
        with mock.patch.object(SR, "_phrase_frac", return_value=0.1):
            ev = SR._plan_events(_Story([seg]), WINDOWS)
        self.assertAlmostEqual(ev[0]["ring0"], 9.0, places=3)
        self.assertGreaterEqual(ev[0]["ring1"], ev[0]["ring0"] + 0.8)

    def test_it_is_on_the_number_as_it_is_said_once_the_build_is_done(self):
        seg = _Seg("x 82 y", [_punch("82")],
                   spans=[{"kind": "bars", "anchors": [_anchor(82)], "t0": 3.0, "t1": 13.0, "full_by": 0.2}])
        with mock.patch.object(SR, "_phrase_frac", return_value=0.7):    # 10.0s
            ev = SR._plan_events(_Story([seg]), WINDOWS)
        self.assertAlmostEqual(ev[0]["ring0"], 9.85, places=3)

    def test_the_ass_track_uses_the_ring_window(self):
        import tempfile
        seg = _Seg("x 82 y", [_punch("82")],
                   spans=[{"kind": "bars", "anchors": [_anchor(82)], "t0": 3.0, "t1": 13.0, "full_by": 0.6}])
        with mock.patch.object(SR, "_phrase_frac", return_value=0.1):
            ev = SR._plan_events(_Story([seg]), WINDOWS)
        from data_learning import story as _story
        real = _story.Segment(sentence=seg.sentence, chart_path=None,
                              punches=seg.punches, source_footer="", topic="t",
                              anchors=seg.anchors)
        real.spans = seg.spans
        st = _story.Story(slug="s", title="t", hook="h", closing="c",
                          segments=[real], hashtags=[], sources=[], question="")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "s.ass"
            SR.build_story_ass(st, WINDOWS, ev, out)
            marks = [l for l in out.read_text().splitlines() if ",Mark,," in l]
        self.assertEqual(len(marks), 1)
        self.assertIn("0:00:09.00", marks[0], "the ring starts when the build is done")


class WhereInTheSentence(unittest.TestCase):

    def test_spoken_length_not_written_words(self):
        """'$1,920' is one written word and a mouthful; the ring for the
        number after it must come later than a word-count guess."""
        s = "Rent hit $1,920 and then 82 percent of people moved."
        by_chars = SR._phrase_frac(s, "82")
        words = s.split()
        by_words = words.index("82") / len(words)
        self.assertGreater(by_chars, by_words)

    def test_a_formatted_number_is_found_in_the_spoken_text(self):
        f = SR._phrase_frac("The world made 82 million tons of e-waste.", "82 million")
        self.assertIsNotNone(f)
        self.assertLess(f, 0.5)

    def test_a_phrase_not_in_the_sentence_is_None_not_a_guess(self):
        self.assertIsNone(SR._phrase_frac("Nothing here matches.", "82"))
        self.assertIsNone(SR._phrase_frac("x", ""))

    def test_an_untimed_punch_gets_no_ring(self):
        seg = _Seg("Nothing here matches.", [_punch("82")],
                   spans=[{"kind": "bars", "anchors": [_anchor(82)], "t0": 3.0, "t1": 13.0, "full_by": 0.5}])
        ev = SR._plan_events(_Story([seg]), WINDOWS)
        self.assertFalse(ev[0]["timed"])
        self.assertIsNone(ev[0]["xy"])


class TheSpanRecordsWhenItsBuildIsDone(unittest.TestCase):
    def test_full_by_is_written_on_every_span(self):
        import ast
        import inspect
        src = inspect.getsource(SR.render)
        tree = ast.parse(src.lstrip())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                node.value = ""
        code = ast.unparse(tree)
        self.assertIn("'': float(_fb)", code)
        self.assertIn("full_by=_fb", code)


if __name__ == "__main__":
    unittest.main()
