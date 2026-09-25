"""The closing lands on a picture the viewer has not seen yet.

"seg4 shows the same frame seg3 ended on, so the payoff adds nothing new to
see" (Waymo, local re-render, 2026-09-25). The last beat's window runs to
the end of the closing, so its last visual started mid-beat and the closing
replayed it, shrunk, under the takeaway. `payoff_spans` gives the closing its
own span: the beat's other pictures share the time before it.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_learning import studio_render as sr  # noqa: E402


class ThePayoffGetsItsOwnSpan(unittest.TestCase):
    def test_the_last_picture_opens_at_the_closing(self):
        spans = sr.payoff_spans(33.4, 52.8, 45.8, 2)
        self.assertEqual(spans, [(33.4, 45.8), (45.8, 52.8)])

    def test_three_pictures_share_the_time_before_it(self):
        spans = sr.payoff_spans(20.0, 52.8, 45.8, 3)
        self.assertEqual(len(spans), 3)
        self.assertAlmostEqual(spans[1][1], 45.8)
        self.assertEqual(spans[2], (45.8, 52.8))
        for (a, b), (c, _d) in zip(spans, spans[1:]):
            self.assertAlmostEqual(b, c)             # consecutive, no gap

    def test_one_picture_or_too_little_time_keeps_the_even_split(self):
        self.assertEqual(sr.payoff_spans(33.4, 52.8, 45.8, 1),
                         [(33.4, 52.8)])
        short = sr.payoff_spans(40.0, 52.8, 45.8, 3)   # 5.8s for two spans
        self.assertEqual(short, sr._visual_spans(40.0, 52.8, 3))

    def test_the_master_uses_it_and_does_not_replay_a_fresh_picture(self):
        src = (ROOT / "data_learning" / "studio_render.py").read_text()
        self.assertIn("payoff_spans(start, end, windows[-1][0], len(kinds))",
                      src)
        self.assertIn("0.0 if t0 >= _close0 - 0.05 else", src)


class ThePayoffIsOnScreenLongEnoughToSee(unittest.TestCase):
    """"the Feb 2025 200,000 point is never drawn on the timeline" — the dot
    reached the END of a dated axis on the last frame of its span."""

    def test_the_timeline_shows_its_headline_with_a_quarter_to_spare(self):
        import tempfile
        from unittest import mock
        from PIL import ImageDraw
        from data_learning import charts as C
        from tests._machine_samples import mk
        ins = mk([("Oct 2023", 10000), ("Aug 2024", 100000),
                  ("Feb 2025", 200000)], "count", topic="waymo rides a week")
        for p, per in zip(ins.items, ("2023-10", "2024-08", "2025-02")):
            p.period = per
        frames = 20
        per_frame: dict = {}
        real = ImageDraw.ImageDraw.text
        state = {"f": 0}

        def spy(self_, xy, text, *a, **k):
            per_frame.setdefault(state["f"], []).append(str(text))
            return real(self_, xy, text, *a, **k)

        real_save = __import__("PIL.Image", fromlist=["Image"]).Image.save

        def save(self_, *a, **k):
            state["f"] += 1
            return real_save(self_, *a, **k)

        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(ImageDraw.ImageDraw, "text", spy), \
                mock.patch("PIL.Image.Image.save", save), \
                mock.patch.object(C, "_host_pose", lambda *a, **k: None):
            C._render_timeline(ins, Path(td), "t", frames=frames)
        at_three_quarters = per_frame.get(int(frames * 0.8), [])
        self.assertIn("200,000", at_three_quarters)


class OnlyTheLeaderCelebrates(unittest.TestCase):
    def test_a_runner_at_nothing_does_not_cheer(self):
        from unittest import mock
        from PIL import Image, ImageDraw
        from data_learning import charts, viz_scene as vs
        from tests._machine_samples import mk
        asked = []

        def host(role, *a, **k):
            asked.append(role)
            return Image.new("RGBA", (100, 200), (40, 200, 180, 255))

        ins = mk([("Waymo", 200000), ("Cruise", 0)], "count",
                 topic="waymo against cruise")
        img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 255))
        with mock.patch.object(vs, "scene_host", host), \
                mock.patch.object(vs, "_race_objects", lambda items: None):
            vs.draw_race(ImageDraw.Draw(img), img,
                         (vs.RX0, vs.RTOP, vs.RX1, vs.RBOT),
                         vs.drawable_insight(ins), charts.HIGHLIGHT, 1.0,
                         "count")
        self.assertIn("shock", asked)


if __name__ == "__main__":
    unittest.main()
