"""A story says each line once — on screen and at its end.

Story backtest #4 (2026-10-06) showed two ways a cut repeats itself:

- Kai Cenat's stream burns in its own live subtitles, and the story
  captioned every beat again underneath them, so every word was on screen
  twice. The scene analyst now reports `own_subtitles` (only from frames it
  actually saw), and the renderer does not caption a beat from such a
  source.
- The best cut was trimmed to end on "...than my bed." and the ending's
  hold (it extends the last beat so the reaction lands) then let "I have"
  back in. The hold may run into silence, never into the next line.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from third_capture import scene_analysis, story                 # noqa: E402

WORDS = [{"w": "than", "s": 10.0, "e": 10.3},
         {"w": "my", "s": 10.4, "e": 10.6},
         {"w": "bed.", "s": 10.7, "e": 11.0},
         {"w": "I", "s": 11.4, "e": 11.5},
         {"w": "have", "s": 11.6, "e": 11.9}]


class _Base(unittest.TestCase):
    def cut(self, srcinfo, start, end):
        seen = {}

        def fake(src, out, work, tag, **kw):
            seen.update(kw)
            raise RuntimeError("stop after the first beat")

        edl = {"beats": [{"source_id": "u", "start": start, "end": end,
                          "role": "payoff", "purpose": "p"}],
               "hook_overlay": "H"}
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(story, "_extract_segment",
                                  side_effect=fake):
            with self.assertRaises(RuntimeError):
                story.render_story(edl, {"u": srcinfo},
                                   Path(td) / "o.mp4", Path(td))
        return seen


class TheEndingHoldStopsBeforeTheNextLine(_Base):
    def test_the_hold_does_not_let_the_next_line_back_in(self):
        seen = self.cut({"path": "x.mp4", "duration_s": 30.0,
                         "words": WORDS}, 5.0, 11.1)
        self.assertLessEqual(seen["end"], 11.4,
                             '"I" starts at 11.4 — it must not be heard')
        self.assertGreaterEqual(seen["end"], 11.1)

    def test_the_hold_still_runs_into_silence(self):
        seen = self.cut({"path": "x.mp4", "duration_s": 30.0,
                         "words": WORDS[:3]}, 5.0, 11.1)
        self.assertAlmostEqual(seen["end"], 11.1 + 1.0, places=2)

    def test_the_hold_never_shortens_the_beat(self):
        w = WORDS[:3] + [{"w": "x", "s": 11.12, "e": 11.3}]
        seen = self.cut({"path": "x.mp4", "duration_s": 30.0,
                         "words": w}, 5.0, 11.1)
        self.assertGreaterEqual(seen["end"], 11.1)


class AStreamWithItsOwnSubtitlesIsNotCaptionedAgain(_Base):
    def test_own_subtitles_means_no_second_caption(self):
        seen = self.cut({"path": "x.mp4", "duration_s": 30.0,
                         "words": WORDS, "own_subtitles": True}, 5.0, 11.1)
        self.assertEqual(seen["words"], [])

    def test_otherwise_the_beat_is_captioned(self):
        seen = self.cut({"path": "x.mp4", "duration_s": 30.0,
                         "words": WORDS}, 5.0, 11.1)
        self.assertEqual(seen["words"], WORDS)

    def _report(self, out, vision):
        with tempfile.TemporaryDirectory() as td:
            v = Path(td) / "c.mp4"
            v.write_bytes(b"")
            with mock.patch.object(scene_analysis.clip_edit,
                                   "transcribe_words", return_value=WORDS), \
                    mock.patch.object(scene_analysis.clip_qa,
                                      "contact_sheet",
                                      return_value=(Path(td) / "s.jpg"
                                                    if vision else None)), \
                    mock.patch.object(scene_analysis, "_call_claude",
                                      return_value=out), \
                    mock.patch.object(scene_analysis, "_call_text_fallback",
                                      return_value=out):
                return scene_analysis.analyze_source(
                    v, {"title": "t", "channel": "kaicenat"}, Path(td))

    def test_the_analyst_reports_it_from_frames(self):
        out = {"summary": "s", "own_subtitles": True}
        self.assertTrue(self._report(out, vision=True)["own_subtitles"])

    def test_a_text_only_analyst_cannot_claim_it(self):
        out = {"summary": "s", "own_subtitles": True}
        self.assertFalse(self._report(out, vision=False)["own_subtitles"])

    def test_the_analyst_is_asked(self):
        self.assertIn("own_subtitles", scene_analysis._SCENE_SYSTEM)


if __name__ == "__main__":
    unittest.main()
