"""THE HOST NEVER HIDES A WORD.

The showrunner's most frequent explainer complaint of 2026-09-24..26 — 24
verdicts on 11 stories, every one inside an `unreadable` auto-fail — was
Data composited on top of type the machine had already drawn:

  * "Data stands over the Oct 2023 label, so it reads '10 00'" (Waymo, x5)
  * "the mascot covers the label 'ISS orbital speed', so it reads
    'ISS o...tal speed'" (ISS, 2026-09-26)
  * "the label reads 'Before 201' because the mascot covers the last digit"
  * "the Cruise label ... ends clipped at 'shutdow'"

Forty machines place him by their own arithmetic, and each was patched at its
own site the day it was named. `render_scene` now brings every word he lands
on to the front (`viz_scene.watch_hosts` / `ink_over_host`). This measures
it the way a viewer would: render a real beat, render it again with an
invisible host, and every fully-inked word must look the same in both.
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

import matplotlib  # noqa: E402
matplotlib.use("Agg")
from PIL import Image, ImageChops, ImageDraw               # noqa: E402

from data_learning import viz_scene as vs                  # noqa: E402
from data_learning.insights import Insight                 # noqa: E402
from data_learning.sources.base import DataPoint, Source   # noqa: E402

SRC = Source(name="X", publisher="Y", url="https://x", access_date="2026-09-26")

# The beats the judge named, as the data they were drawn from.
WAYMO = [("Waymo, weekly paid rides (Oct 2023)", 10000),
         ("Waymo, weekly paid rides (2025)", 250000),
         ("Cruise, weekly rides (after Dec 2024 shutdown)", 0)]
ISS = [("Commercial jet cruising speed (km/h)", 900),
       ("ISS orbital speed", 27600)]
CASES = [("race_track", ISS), ("skyline", WAYMO), ("funnel", WAYMO),
         ("inout", WAYMO), ("road", WAYMO)]
FRAMES = 6


def _insight(kind, pairs):
    ins = Insight(kind="scene", topic="Waymo weekly paid robotaxi rides",
                  main_insight="m",
                  items=[DataPoint(label=a, value=float(b)) for a, b in pairs],
                  source=SRC, unit="", highlight_label=pairs[-1][0])
    ins.scene = {"title": True,
                 "elements": [{"type": kind, "region": "full",
                               "anim": "grow"}]}
    return ins


def _render(kind, pairs, invisible: bool):
    """Every frame of the beat, un-pushed, plus the words each one drew."""
    draws: list = []

    class _Keep(vs.InkDraw):
        # records its own words, so this measures the old code too
        def __init__(self, draw):
            super().__init__(draw)
            self.words = []
            draws.append(self)

        def text(self, xy, text, fill=None, *a, **k):
            self.words.append(("text", xy, text, vs._lift_rest(fill), a, k))
            return super().text(xy, text, fill, *a, **k)

        def multiline_text(self, xy, text, fill=None, *a, **k):
            self.words.append(("multiline_text", xy, text,
                               vs._lift_rest(fill), a, k))
            return super().multiline_text(xy, text, fill, *a, **k)

    real_host = vs.scene_host

    def _ghost(*a, **k):
        im = real_host(*a, **k)
        if im is None or not invisible:
            return im
        im = im.copy()                      # same size, same bbox, unseen
        im.putalpha(im.getchannel("A").point(lambda v: 1 if v else 0))
        return im

    with tempfile.TemporaryDirectory() as tmp, \
            mock.patch.object(vs, "InkDraw", _Keep), \
            mock.patch.object(vs, "_push", lambda c, r: c), \
            mock.patch.object(vs, "scene_host", _ghost):
        out = vs.render_scene(_insight(kind, pairs), Path(tmp), "t",
                              frames=FRAMES)
        if not out:
            return None
        pattern = out[0] if isinstance(out, tuple) else out
        frames = [Image.open(pattern % f).convert("RGBA").copy()
                  for f in range(1, FRAMES + 1)]
    return frames, [d.words for d in draws]


def _glyphs(size, entry):
    method, xy, text, _fill, args, kw = entry
    m = Image.new("L", size, 0)
    kw = {k: v for k, v in kw.items() if k not in ("stroke_width",
                                                     "stroke_fill")}
    getattr(ImageDraw.Draw(m), method)(xy, text, 255, *args, **kw)
    return m.point(lambda v: 255 if v > 128 else 0)


def _opaque(fill) -> bool:
    return not (isinstance(fill, (tuple, list)) and len(fill) > 3
                and fill[3] < 230)


class TheHostNeverHidesAWord(unittest.TestCase):
    def test_every_word_reads_through_the_host(self):
        hidden = {}
        for kind, pairs in CASES:
            seen = _render(kind, pairs, invisible=False)
            ghost = _render(kind, pairs, invisible=True)
            self.assertIsNotNone(seen, kind)
            (frames, drawn), (gframes, _) = seen, ghost
            for f, (im, gim) in enumerate(zip(frames, gframes)):
                diff = ImageChops.difference(im.convert("RGB"),
                                             gim.convert("RGB")).convert("L")
                changed = diff.point(lambda v: 255 if v > 60 else 0)
                for entry in drawn[f]:
                    if not _opaque(entry[3]) or not str(entry[2]).strip():
                        continue
                    g = _glyphs(im.size, entry)
                    n = g.histogram()[255]
                    if n < 20:
                        continue
                    lost = ImageChops.multiply(g, changed).histogram()[255]
                    if lost / n > 0.05:
                        hidden.setdefault(kind, []).append(
                            (f + 1, str(entry[2])[:40], round(lost / n, 2)))
        self.assertEqual(hidden, {},
                         "the host is drawn over these words: " + repr(hidden))

    def test_a_word_he_does_not_touch_is_left_alone(self):
        # the re-ink is clipped to his silhouette: text beside him is the
        # original pixels, not a second, heavier copy
        canvas = Image.new("RGBA", (400, 200), (10, 12, 30, 255))
        d = vs.InkDraw(ImageDraw.Draw(canvas))
        seen = vs.watch_hosts(canvas, d)
        d.text((20, 20), "LEFT", fill=(240, 240, 240, 255))
        d.text((250, 20), "RIGHT", fill=(240, 240, 240, 255))
        host = Image.new("RGBA", (80, 60), (200, 60, 60, 255))
        host.info[vs.HOST_MARK] = True
        canvas.alpha_composite(host, (240, 5))
        before = canvas.convert("RGB")
        self.assertEqual(vs.ink_over_host(canvas, d, seen), 1)
        self.assertEqual(ImageChops.difference(
            before.crop((0, 0, 200, 200)),
            canvas.convert("RGB").crop((0, 0, 200, 200))
        ).getbbox(), None, "LEFT was nowhere near him and must not change")
        self.assertIsNotNone(ImageChops.difference(
            before.crop((240, 5, 320, 65)),
            canvas.convert("RGB").crop((240, 5, 320, 65))
        ).getbbox(), "RIGHT must be brought over him")

    def test_scene_host_carries_the_mark_through_a_resize(self):
        h = vs.scene_host("point", 0.5)
        if h is None:
            self.skipTest("no host renderer here")
        self.assertTrue(vs._fit(h, 40, 60).info.get(vs.HOST_MARK))
        self.assertTrue(h.copy().info.get(vs.HOST_MARK))


if __name__ == "__main__":
    unittest.main()
