"""A tip label never sits on the ring that marks the pass.

Self-repair 2026-09-27. After #479 put every tip label in ink on an opaque
plate, graph races still auto-failed `unreadable` at the one moment they
exist to show:

- "the gold tip ring sits over the end of the 'Wind + solar 721' label, and
  the 'Coal 688' label is packed right under it. At the crossover the two
  tip labels and markers collide at the right edge" (wind/solar, 83, block);
- "the dim grey 'Coal 703/688/652' label sits under the orange 'Wind +
  solar' label box at the crossover, and a leftover ring marker overlaps
  the digits" (wind/solar, 83, block);
- "the crossover glow ring covers them at the overtake" (chicken, 83).

`_spread` kept the labels apart from EACH OTHER and never knew the ring was
there. A "finally passed" race crosses near its last year, which is where
the labels flip left to, so both plates landed on the ring.

This renders the real races (icons off, no encode) and measures every frame
after the pass, in pixels, with the renderer's own artists: no label plate
may touch the held ring, and no two plates may touch each other.
"""
from __future__ import annotations

import math
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines import chart_race as cr   # noqa: E402

try:
    import matplotlib  # noqa: F401
    HAVE_MPL = True
except Exception:  # noqa: BLE001
    HAVE_MPL = False


WIND_SOLAR = {   # state/trending_packages/20260926/01_graph-wind-solar-passed-coal.json
    "title": "Wind And Solar Finally Passed Coal",
    "hook": "Coal lost its lead.",
    "y_label": "U.S. electricity generated per year (TWh)",
    "source": "U.S. Energy Information Administration, Electric Power Annual",
    "years": [2010, 2012, 2014, 2016, 2018, 2020, 2022, 2024],
    "series": [
        {"name": "Wind + solar", "color": "#F9A825",
         "values": [96, 145, 200, 263, 339, 427, 580, 757]},
        {"name": "Coal", "color": "#455A64",
         "values": [1847, 1514, 1582, 1239, 1146, 774, 828, 652]},
    ],
}

CHICKEN = {      # state/trending_packages/20260925/02_chicken-passed-beef-consumption.json
    "title": "Chicken Quietly Passed Beef In America",
    "hook": "Chicken Beat Beef",
    "y_label": "US per-capita meat availability (lbs)",
    "source": "USDA Economic Research Service",
    "years": [1970, 1980, 1990, 2000, 2010, 2020, 2023],
    "series": [
        {"name": "Beef", "color": "#d32f2f",
         "values": [84, 72, 64, 64, 57, 55, 58]},
        {"name": "Chicken", "color": "#ffb300",
         "values": [27, 32, 42, 54, 58, 65, 68]},
    ],
}


def _measure(spec: dict) -> list[str]:
    """Render `spec` and return every collision seen after the pass."""
    from matplotlib.figure import Figure
    from matplotlib.transforms import Bbox

    spec = dict(spec, icons=False)
    found: list[str] = []
    real_savefig = Figure.savefig
    real_sub = cr.subprocess

    def measure(fig, *a, **k):
        ax = fig.axes[0]
        rings = [ln for ln in ax.lines
                 if ln.get_marker() == "o" and ln.get_markersize() == 26
                 and ln.get_markerfacecolor() == "none"
                 and ln.get_markeredgecolor() == "white"]
        if not rings:
            return None                       # before the pass: not measured
        fig.canvas.draw()
        r = fig.canvas.get_renderer()
        plates = []
        for t in ax.texts:
            patch = t.get_bbox_patch()
            if patch is None or t.get_ha() == "center":
                continue                      # the pass caption, in headroom
            plates.append((t.get_text(), patch.get_window_extent(r)))
        ring = rings[0]
        cx, cy = ax.transData.transform(
            (ring.get_xdata()[0], ring.get_ydata()[0]))
        rad = (ring.get_markersize() + ring.get_markeredgewidth()) \
            * fig.dpi / 72.0 / 2.0
        yr = ax.get_xlim()[1]
        for name, bb in plates:
            dx = max(bb.x0 - cx, 0.0, cx - bb.x1)
            dy = max(bb.y0 - cy, 0.0, cy - bb.y1)
            if math.hypot(dx, dy) < rad:
                found.append(f"{name!r} on the pass ring (x_hi {yr:.1f})")
        for i in range(len(plates)):
            for j in range(i + 1, len(plates)):
                if Bbox.intersection(plates[i][1], plates[j][1]) is not None:
                    found.append(f"{plates[i][0]!r} on {plates[j][0]!r}")
        return None

    Figure.savefig = measure
    cr.subprocess = types.SimpleNamespace(run=lambda *a, **k: None)
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            cr.render(spec, Path(d) / "race.mp4")
    finally:
        Figure.savefig = real_savefig
        cr.subprocess = real_sub
    return found


@unittest.skipUnless(HAVE_MPL, "matplotlib not installed")
class NoLabelSitsOnThePass(unittest.TestCase):
    def test_wind_and_solar(self):
        hits = _measure(WIND_SOLAR)
        self.assertEqual(hits, [], f"{len(hits)} collisions, e.g. {hits[:3]}")

    def test_chicken_and_beef(self):
        hits = _measure(CHICKEN)
        self.assertEqual(hits, [], f"{len(hits)} collisions, e.g. {hits[:3]}")


class ClearBand(unittest.TestCase):
    def test_leader_goes_above_trailer_below(self):
        out = cr._clear_band([757, 652], [757, 700], min_sep=20, floor=0,
                             ceil=2000, lo=660, hi=760)
        self.assertGreaterEqual(out[0], 760)
        self.assertLessEqual(out[1], 660)

    def test_positions_already_clear_are_left_alone(self):
        self.assertEqual(
            cr._clear_band([900, 300], [900, 300], min_sep=20, floor=0,
                           ceil=2000, lo=500, hi=600), [900, 300])

    def test_no_room_below_puts_everyone_above_in_order(self):
        out = cr._clear_band([60, 40], [60, 40], min_sep=20, floor=38,
                             ceil=500, lo=35, hi=65)
        self.assertGreaterEqual(out[1], 65)
        self.assertGreaterEqual(out[0] - out[1], 20)

    def test_no_room_anywhere_changes_nothing(self):
        self.assertEqual(
            cr._clear_band([60, 40], [60, 40], min_sep=20, floor=38,
                           ceil=70, lo=35, hi=65), [60, 40])

    def test_rank_order_and_spacing_hold_for_three(self):
        out = cr._clear_band([100, 90, 80], [100, 80, 60], min_sep=20,
                             floor=0, ceil=500, lo=70, hi=110)
        self.assertEqual(out, sorted(out, reverse=True))
        for a, b in zip(out, out[1:]):
            self.assertGreaterEqual(a - b, 20)
        self.assertTrue(all(v >= 110 or v <= 70 for v in out))


if __name__ == "__main__":
    unittest.main()
