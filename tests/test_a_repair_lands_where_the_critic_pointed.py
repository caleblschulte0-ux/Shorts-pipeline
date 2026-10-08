"""A repair lands on the line the critic pointed at.

The critic names problems on the OUTPUT clock ("@63.0s repetition: 'are
you hacked?' plays twice"). The EDL the reviser edits is in each SOURCE's
own seconds. With three beats and a hook between them, the reviser was
guessing which line was meant: story backtest 6 (2026-10-08) repaired Kai's
"are you hacked" story three times and the same repetition, the same
garbled opening and the same unintroduced "Rage" were still there each
time (62 -> 68 -> 71). Every critic problem now arrives mapped to the beat
and source second it lands on, beside what each beat of that cut kept.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from third_capture import shot_plan, story, story_director     # noqa: E402

HAVE_FFMPEG = shutil.which("ffmpeg") is not None

# the cut the critic watched: beat 0 = A 10-30 (out 0-20),
# beat 1 = B 40-55 (out 20-35)
CUT = {"beats": [{"beat": 0, "source_id": "A", "role": "setup",
                  "start": 10.0, "end": 30.0,
                  "out_start": 0.0, "out_end": 20.0},
                 {"beat": 1, "source_id": "B", "role": "payoff",
                  "start": 40.0, "end": 55.0,
                  "out_start": 20.0, "out_end": 35.0}],
       "final_words": [{"w": "yo", "s": 1.0, "e": 1.3},
                       {"w": "bruce", "s": 1.4, "e": 1.8},
                       {"w": "are", "s": 23.0, "e": 23.2},
                       {"w": "you", "s": 23.2, "e": 23.4},
                       {"w": "hacked", "s": 23.4, "e": 23.9}]}


class TheCriticsSecondIsFound(unittest.TestCase):
    def test_an_output_second_maps_to_its_beat_and_source_second(self):
        self.assertEqual(story_director.locate(5.0, CUT["beats"]),
                         {"beat": 0, "source_id": "A", "source_s": 15.0})
        self.assertEqual(story_director.locate(23.4, CUT["beats"]),
                         {"beat": 1, "source_id": "B", "source_s": 43.4})

    def test_past_the_end_is_the_last_beat_and_nothing_is_none(self):
        self.assertEqual(story_director.locate(99.0, CUT["beats"])["beat"], 1)
        self.assertIsNone(story_director.locate(3.0, []))

    def test_the_cut_map_shows_each_beats_lines_in_source_seconds(self):
        m = story_director._cut_map(CUT)
        self.assertIn("beat 1 (payoff) source B 40.0-55.0s = output "
                      "20.0-35.0s", m)
        self.assertIn("[43.0-43.9] are you hacked", m)
        self.assertIn("[11.0-11.8] yo bruce", m)


class TheReviserIsToldWhere(unittest.TestCase):
    def test_each_problem_names_its_beat_and_the_cut_is_shown(self):
        seen = []

        def brain(user, system, **kw):
            seen.append(user)
            return None
        edl = {"is_story": True, "beats": []}
        with mock.patch.object(story_director, "_brain", side_effect=brain):
            story_director.revise_edl(
                edl, [{"type": "repetition", "at": 23.4,
                       "fix": "cut the duplicate take"}], [], cut=CUT)
        self.assertIn("at 23.4s (= beat 1, source B at 43.4s) "
                      "[repetition]", seen[0])
        self.assertIn("THE CUT THE CRITIC WATCHED", seen[0])
        self.assertIn("are you hacked", seen[0])

    def test_without_a_cut_it_still_works(self):
        seen = []

        def brain(user, system, **kw):
            seen.append(user)
            return None
        with mock.patch.object(story_director, "_brain", side_effect=brain):
            story_director.revise_edl(
                {"is_story": True, "beats": []},
                [{"type": "pacing", "at": 4.0, "fix": "x"}], [])
        self.assertIn("- at 4.0s [pacing]: x", seen[0])
        self.assertNotIn("THE CUT THE CRITIC WATCHED", seen[0])

    def test_the_repair_loop_passes_the_cut_it_is_repairing(self):
        src = (ROOT / "scripts" / "run_third.py").read_text()
        self.assertIn("cut=_best[3]", src)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg unavailable")
class TheRendererRecordsTheOutputClock(unittest.TestCase):
    def test_each_beat_says_where_it_sits_in_the_output(self):
        td = Path(self.enterContext(tempfile.TemporaryDirectory()))
        src = td / "src.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error",
                        "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30",
                        "-f", "lavfi", "-i", "sine=frequency=440",
                        "-t", "4", "-c:v", "libx264", "-preset", "ultrafast",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                        str(src)], check=True)
        story._AN_CACHE.clear()
        edl = {"structure": "chronological", "premise": "p",
               "beats": [{"source_id": "S", "start": 0.2, "end": 1.6,
                          "role": "setup", "purpose": "a"},
                         {"source_id": "S", "start": 1.8, "end": 3.2,
                          "role": "payoff", "purpose": "b"}],
               "ending": {"duration": 0.3}}
        srcinfo = {"S": {"path": str(src), "words": [],
                         "duration_s": 4.0, "source_url": "S"}}
        with mock.patch.object(shot_plan, "analyze",
                               return_value={"sw": 1280, "sh": 720,
                                             "subjects": []}), \
                mock.patch.object(shot_plan, "build",
                                  return_value=(None, {"layout": "wide"})):
            led = story.render_story(edl, srcinfo, td / "story.mp4", td / "w")
        b0, b1 = led["beats"]
        self.assertEqual((b0["beat"], b0["out_start"], b0["out_end"]),
                         (0, 0.0, 1.4))
        self.assertEqual(b1["beat"], 1)
        self.assertAlmostEqual(b1["out_start"], 1.4, places=2)
        self.assertAlmostEqual(b1["out_end"] - b1["out_start"],
                               b1["end"] - b1["start"], places=2)


if __name__ == "__main__":
    unittest.main()
