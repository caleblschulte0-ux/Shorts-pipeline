"""WHAT THE JUDGE NAMED ON THE FIRST RUN OF THE COLD-OPEN FIXES.

Explainer run 461 (2026-09-22, the first on #421) was blocked 30-47 on
every video. Two of its complaints come from one place each:

  * "a cyan ellipse is drawn over '88.7%'", "over '699,173'", "over the
    'By sea 80%' text" (four stories). The spoken-number ring was drawn
    round every anchor, and a scene machine's anchor is a POINT ON ITS MARK
    with a guessed 220x90 box, not the box of the number it printed.
  * the timeline beat, in three stories: its title ran off both edges
    ("·gest container ship capacity by ye"), "one thin timeline sits at
    y~330 and the whole lower half of the frame is empty dark gradient"
    (empty_void), a ghost year sat on a tick, and the headline number
    showed the final value while the dot was still passing an early year.
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
import numpy as np                                           # noqa: E402
from PIL import Image                                        # noqa: E402

from data_learning import charts, story as _story            # noqa: E402
from data_learning import studio_render as SR, viz_scene as vs  # noqa: E402
from data_learning.insights import Insight                   # noqa: E402
from data_learning.sources.base import DataPoint, Source     # noqa: E402

SRC = Source(name="X", publisher="Y", url="https://x", access_date="2026-09-22")
WINDOWS = [(0.0, 3.0), (3.0, 13.0), (13.0, 20.0)]


def _marks(anchor):
    punch = {"text": "82", "phrase": "82", "duration": 1.8, "color": "#ffffff"}
    spans = [{"kind": "scene", "anchors": [anchor], "t0": 3.0, "t1": 13.0,
              "full_by": 0.2}]
    real = _story.Segment(sentence="x 82 y", chart_path=None, punches=[punch],
                          source_footer="", topic="t", anchors=[])
    real.spans = spans
    st = _story.Story(slug="s", title="t", hook="h", closing="c",
                      segments=[real], hashtags=[], sources=[], question="")
    with mock.patch.object(SR, "_phrase_frac", return_value=0.7):
        ev = SR._plan_events(st, WINDOWS)
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "s.ass"
        SR.build_story_ass(st, WINDOWS, ev, out)
        return [l for l in out.read_text().splitlines() if ",Mark,," in l]


class TheRingCirclesOnlyAMeasuredNumber(unittest.TestCase):
    def test_a_machine_anchor_is_marked_unmeasured(self):
        a = vs._as_anchor((82.0, "art", 500, 900))
        self.assertIs(a["measured"], False)

    def test_no_ring_round_a_guess(self):
        self.assertEqual(_marks(vs._as_anchor((82.0, "art", 500, 900))), [])

    def test_a_measured_number_still_gets_its_ring(self):
        self.assertEqual(len(_marks({"value": 82.0, "cx": 100.0, "cy": 200.0,
                                     "w": 40.0, "h": 20.0})), 1)


def _timeline(topic="largest container ship capacity by year"):
    ins = Insight(kind="timeline", topic=topic, main_insight="m",
                  items=[DataPoint(label=str(y), value=float(v), period=y)
                         for y, v in ((1996, 6600), (2006, 12500),
                                      (2013, 18000), (2019, 24000))],
                  source=SRC, unit="TEU", highlight_label="2019")
    td = tempfile.mkdtemp()
    fn = getattr(charts._render_timeline, "__wrapped__", charts._render_timeline)
    pattern, _ = fn(ins, Path(td), "tl")
    return pattern


class TheTimelineFillsItsFrame(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pattern = _timeline()
        cls.last = np.asarray(Image.open(cls.pattern % 16))[..., 3] > 8

    def test_the_title_stays_inside_the_frame(self):
        a = self.last
        band = a[280:380, :]
        self.assertFalse(band[:, :6].any() or band[:, -6:].any(),
                         "the title touches a frame edge")

    def test_the_series_stands_above_the_line(self):
        """Every data year has a stem rising from the axis — the band just
        above the line is ink at each year's x, not empty ground."""
        x0, x1, lo, hi = 110, 970, 1996, 2019
        for year in (1996, 2006, 2013, 2019):
            x = int(x0 + (x1 - x0) * (year - lo) / (hi - lo))
            self.assertTrue(self.last[1150:1260, x - 6:x + 7].any(), year)
        self.assertGreater(self.last[560:1240, 110:970].mean(), 0.02)

    def test_the_headline_says_what_the_dot_has_reached(self):
        from data_learning.charts import _render_timeline  # noqa: F401
        src = (ROOT / "data_learning" / "charts.py").read_text()
        body = src[src.index("def _render_timeline("):src.index("@_fullframe(\"fill_vessel\")")]
        self.assertIn("_past", body)
        early = np.asarray(Image.open(self.pattern % 4))[..., 3] > 8
        late = self.last
        # the headline region differs between an early and the last frame:
        # it is not the final value from the first frame on
        self.assertFalse(np.array_equal(early[400:520, :], late[400:520, :]))


if __name__ == "__main__":
    unittest.main()
