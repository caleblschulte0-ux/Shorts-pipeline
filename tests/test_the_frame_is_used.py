"""A picture must USE the 9:16 frame, not leave half of it empty.

`empty_void` is the showrunner's most-cited block on the data channel, and its
notes are exact enough to be turned into a number:

    "the seesaw in the top ~40% and the entire bottom half as empty gradient"
    "the entire lower two-thirds as blank blue gradient"
    "a hairline timeline at ~45% height ... everything below it empty"
    "one lone bill tile top-left ... and the entire lower 70% empty"

Every one of those is a wide horizontal band of frame with no ink in it. A
vision model catching that is slow, expensive, non-deterministic and only
happens AFTER a full render. `shared/frame_occupancy.py` computes the same
fact from the drawn layer in milliseconds, which is what lets a machine be
TUNED against it rather than argued about.

The root cause was one constant. `RBOT` was 1180 of 1920 — "above the game
strip", a layout this channel has not had for a long time — so the whole
scene kit drew inside the top 61% and left 39% of the frame empty. 158 of the
configured scenes have more than one element and every one of them was
drawing into that box.

MEASURED WITH THE FURNITURE. The studio draws the beat title near the top and
burns the spoken caption near the bottom of every frame, so measuring a bare
machine over-reports the void at both ends — the first cut of this test
flagged ten machines that are fine in production. Only a gap still empty WITH
the title and caption present is a real one.

Runs standalone:  python3 tests/test_the_frame_is_used.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from PIL import Image, ImageDraw                          # noqa: E402
from data_learning import charts, viz_scene as vs         # noqa: E402
from shared import frame_occupancy as fo                  # noqa: E402

BOX = (vs.RX0, vs.RTOP, vs.RX1, vs.MACHINE_BOT)


def _furniture(d, topic):
    """What the studio puts on every frame, so the measure matches reality."""
    vs.draw_caption(d, (vs.RX0, 250, vs.RX1, 250), str(topic), 1.0, size=52)
    d.rounded_rectangle([300, 1690, 780, 1748], radius=8,
                        fill=(255, 255, 255, 255))
    d.rounded_rectangle([420, 1860, 660, 1884], radius=6,
                        fill=(255, 255, 255, 160))


class TheSceneKitOwnsTheFrame(unittest.TestCase):
    def test_the_safe_box_reaches_down_the_frame(self):
        """The one constant this whole class is about."""
        self.assertGreaterEqual(
            vs.RBOT, 1500,
            "the scene box stops in the upper half again — every "
            "multi-element scene will leave the bottom of the frame empty")
        self.assertLessEqual(vs.RBOT, 1600,
                             "the box now runs into the caption band")

    def test_a_lone_machine_uses_the_same_box(self):
        self.assertEqual(vs.MACHINE_BOT, vs.RBOT)

    def test_the_regions_all_reach_it(self):
        for name in ("full", "hero", "left", "right", "bottom"):
            self.assertEqual(vs.REGIONS[name][3], vs.RBOT, name)


class NoMachineLeavesAVoid(unittest.TestCase):
    """Every machine, at production size, with the production furniture."""

    CEILING = 0.34

    def test_every_machine_fills_its_box(self):
        from tests._machine_samples import SAMPLES
        bad = {}
        for kind, ins in SAMPLES.items():
            if kind not in vs._MACHINE_DRAW:
                continue
            img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            safe = vs.drawable_insight(ins)
            if safe is None:
                continue
            got = vs._guarded(kind, vs._MACHINE_DRAW[kind], d, img, BOX, safe,
                              charts.HIGHLIGHT, 0.95, safe.unit)
            if got is None:
                continue
            _furniture(d, ins.topic)
            v = fo.verdict(img, max_void=self.CEILING)
            if not v["ok"]:
                bad[kind] = f"{v['void'] * 100:.0f}% at {v['void_at'] * 100:.0f}%"
        self.assertEqual(bad, {}, f"machines leaving a void: {bad}")


class TheMeasureItself(unittest.TestCase):
    def test_a_blank_layer_is_all_void(self):
        img = Image.new("RGBA", (200, 400), (0, 0, 0, 0))
        self.assertAlmostEqual(fo.measure(img)["void"], 1.0, places=3)

    def test_a_full_layer_has_none(self):
        img = Image.new("RGBA", (200, 400), (255, 255, 255, 255))
        self.assertAlmostEqual(fo.measure(img)["void"], 0.0, places=3)

    def test_it_finds_the_band_and_says_where(self):
        img = Image.new("RGBA", (200, 400), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 199, 99], fill=(255, 255, 255, 255))
        d.rectangle([0, 300, 199, 399], fill=(255, 255, 255, 255))
        m = fo.measure(img)
        self.assertAlmostEqual(m["void"], 0.5, places=2)
        self.assertAlmostEqual(m["void_at"], 0.25, places=2)

    def test_a_single_rule_is_not_content(self):
        """A 1px line across an otherwise empty band must not count as ink —
        that is exactly the "hairline timeline" the reviewer blocked."""
        img = Image.new("RGBA", (200, 400), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.line([(0, 200), (199, 200)], fill=(255, 255, 255, 255), width=1)
        self.assertGreater(fo.measure(img)["void"], 0.45)


if __name__ == "__main__":
    unittest.main(verbosity=2)
