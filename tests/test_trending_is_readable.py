"""Every trending video of 2026-09-26 was blocked for things a viewer cannot
read or reads as broken:

- all four graph races auto-failed `unreadable`: tip labels in the series'
  own colour ("dim purple text on a purple mark", "dark brown on
  near-black"), on a 78% plate the line ran through, ticks too small;
- five reddit stories showed "a thin grey horizontal line ... in every
  frame" — a deliberate divider the judge reads as a compositing seam;
- two had "two captions printed on top of each other".
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines import chart_race as cr   # noqa: E402
import make_reddit_story as M          # noqa: E402


def _contrast_on_black(hex_color):
    h = hex_color.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
           for v in rgb]
    lum = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    return (lum + 0.05) / 0.05


class ARaceReadsOnAPhone(unittest.TestCase):
    def test_every_series_colour_contrasts_with_the_ground(self):
        for c in cr.PALETTE + ["#6b3fa0", "#5a3a1a", "#2c3e50", "#7f1d1d"]:
            self.assertGreaterEqual(_contrast_on_black(cr.visible_on_black(c)),
                                    4.5, c)

    def test_a_colour_that_already_reads_is_left_alone(self):
        self.assertEqual(cr.visible_on_black("#f5c518"), "#f5c518")

    def test_labels_wear_ink_on_an_opaque_plate(self):
        src = (ROOT / "engines" / "chart_race.py").read_text()
        self.assertIn("color=TIP_INK,", src)
        self.assertIn('facecolor="#05070c", alpha=1.0', src)
        self.assertNotIn('textcoords="offset points", color=s["color"]', src)
        self.assertIn("labelsize=20", src)
        self.assertIn('s["color"] = visible_on_black(s["color"])', src)


class ARedditStoryHasNoSeam(unittest.TestCase):
    def test_no_divider_is_drawn(self):
        src = (ROOT / "make_reddit_story.py").read_text()
        self.assertNotIn("drawbox", src)


class CaptionsNeverStack(unittest.TestCase):
    def test_no_two_events_are_on_screen_at_once(self):
        evs = M.no_overlap([(0.0, 1.2, "a"), (1.0, 1.5, "b"),
                            (1.45, 2.0, "c"), (3.0, 3.5, "d")])
        for (a0, a1, _), (b0, _b1, _) in zip(evs, evs[1:]):
            self.assertLessEqual(a1, b0)

    def test_short_gaps_close_long_ones_stay(self):
        evs = M.no_overlap([(0.0, 1.0, "a"), (1.3, 2.0, "b"), (3.0, 3.5, "c")])
        self.assertEqual(evs[0][1], 1.3)       # bridged
        self.assertEqual(evs[1][1], 2.0)       # a real pause stays a pause

    def test_the_writer_uses_it(self):
        import tempfile
        from types import SimpleNamespace as W
        words = [W(text="one", start=0.0, end=0.6),
                 W(text="two", start=0.5, end=1.1),
                 W(text="three", start=1.0, end=1.6),
                 W(text="four", start=1.55, end=2.2),
                 W(text="five", start=2.1, end=2.8)]
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "c.ass"
            M._karaoke_ass(words, p, 0.0, 3.0)
            spans = []
            for ln in p.read_text().splitlines():
                if ln.startswith("Dialogue:"):
                    f = ln.split(",")
                    spans.append((M_t(f[1]), M_t(f[2])))
        spans.sort()
        for (a0, a1), (b0, _b1) in zip(spans, spans[1:]):
            self.assertLessEqual(a1, b0 + 1e-6)


def M_t(s):
    h, m, rest = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


if __name__ == "__main__":
    unittest.main()
