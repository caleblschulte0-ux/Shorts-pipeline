"""The host performs ON the data, INSIDE the card — pinned geometrically.

2026-08-22/23: 36 renders, 36 blocks, and `decorative_mascot` on nearly all
of them. The verdicts were spatial facts, not taste: "floating over the
title, occluding 'cereal'" (bar-race top row parked his head across the
title band), "sits on top of the '1972' label" (a trend tip hung him over
the x ticks), "parked in empty lower-left of the map" (`_story_geo` baked
him at a hard-coded (0.30, 0.10) bound to nothing). These tests render the
real figures and measure the real extents — the clamp's arithmetic is
verified against what matplotlib actually draws, not against itself.

    python -m unittest tests.test_mascot_anchoring -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data_learning import charts as C                       # noqa: E402
from data_learning.insights import (Insight, DataPoint,     # noqa: E402
                                    Source)

SRC = Source(name="WDI", publisher="World Bank", url="u")
RANKED = [("Slovenia", 101756.0), ("Malawi", 59978.0), ("Costa Rica", 23435.0),
          ("Iceland", 20897.0), ("Estonia", 20163.0)]


def _insight(kind: str, items=None) -> Insight:
    pts = [DataPoint(l, v, "kg") for l, v in (items or RANKED)]
    return Insight(kind=kind, topic="T", main_insight="Slovenia leads",
                   items=pts, source=SRC, unit="kg",
                   highlight_label=pts[0].label)


def _host_extents(fig):
    """Figure-fraction (x0, x1, y0, y1) of every AnnotationBbox actually
    drawn — the ground truth the clamp must agree with."""
    from matplotlib.offsetbox import AnnotationBbox
    fig.canvas.draw()
    fw = fig.get_size_inches()[0] * fig.dpi
    fh = fig.get_size_inches()[1] * fig.dpi
    out = []
    for ax in fig.axes:
        for a in ax.artists:
            if isinstance(a, AnnotationBbox):
                e = a.get_window_extent(fig.canvas.get_renderer())
                out.append((e.x0 / fw, e.x1 / fw, e.y0 / fh, e.y1 / fh))
    return out


class TestTheClampKeepsHimOnTheCard(unittest.TestCase):

    def test_race_top_row_head_stays_below_the_title(self):
        """The exact 08-23 block: pictorial_race bakes the host on the TOP
        row's tip at zoom 1.0 — unclamped, his head crossed SUB_Y by ~90px."""
        fig, plt = C._card_base()
        C._heading(fig, "World cereal land just sank below its 1972 level",
                   "KG PER HECTARE")
        C._story_pictorial_race(fig, plt, _insight("pictorial_race"),
                                "sub", 1.0)
        boxes = _host_extents(fig)
        self.assertTrue(boxes, "no host baked at all")
        for x0, x1, y0, y1 in boxes:
            self.assertLessEqual(y1, C.SUB_Y, f"host top {y1:.3f} is in the "
                                 "title band — the occlusion is back")
            self.assertLessEqual(x1, 0.99)
            self.assertGreaterEqual(x0, 0.01)
        plt.close(fig)

    def test_an_in_bounds_bake_is_untouched(self):
        """The praised bit ("arms on the Slovenia bar tip") must come back
        byte-identical: a bake already inside the bounds is a no-op."""
        fig, plt = C._card_base()
        ax = fig.add_axes([0.1, 0.3, 0.8, 0.4])
        ax.set_xlim(0, 10); ax.set_ylim(0, 10)
        x, y = C._clamp_host(ax, 5.0, 5.0, (300, 300), 0.5, (0.5, 0.5))
        self.assertAlmostEqual(x, 5.0, places=9)
        self.assertAlmostEqual(y, 5.0, places=9)
        plt.close(fig)

    def test_the_attach_log_records_the_clamped_point(self):
        """The sidecar is the contract the benchmark validator reads — it
        must describe where the host actually IS, not where the raw call
        asked for."""
        src = (ROOT / "data_learning" / "charts.py").read_text()
        body = src.split("def _bake_host(", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(body.index("_clamp_host"),
                        body.index("_ATTACH_FRAME.append"))


class TestGeoIsADemonstrationNow(unittest.TestCase):
    """The 08-22 verdict, verbatim: "a decorative map whose dots are not
    placed on Slovenia, Malawi, Costa Rica, Iceland or Estonia — a number
    list, not a demonstration". The dots were a legend column at a fixed
    x=0.655; no country->position lookup existed in the repo at all."""

    def test_centroids_land_on_the_five_judged_countries(self):
        want = {"Slovenia": (14.8, 46.1), "Malawi": (34.0, -13.5),
                "Costa Rica": (-84.2, 9.9), "Iceland": (-18.6, 64.9),
                "Estonia": (25.5, 58.7)}
        for nm, (wlon, wlat) in want.items():
            c = C.region_centroid("world", nm)
            self.assertIsNotNone(c, nm)
            self.assertLess(abs(c[0] - wlon), 4.0, nm)
            self.assertLess(abs(c[1] - wlat), 4.0, nm)

    def test_an_unknown_region_is_none_not_a_crash(self):
        self.assertIsNone(C.region_centroid("world", "Atlantis"))

    def test_markers_are_on_the_map_not_a_side_column(self):
        """The map axes itself must carry one scatter per pinned region —
        markers in lon/lat space, not figure-fraction swatches."""
        fig, plt = C._card_base()
        ax, specs = C._story_geo(fig, plt, _insight("geo_world"), "s",
                                 1.0, "world")
        self.assertGreaterEqual(len(ax.collections), 5,
                                "fewer map markers than ranked regions")
        lons = sorted(c.get_offsets()[0][0] for c in ax.collections[:5])
        self.assertLess(lons[0], -60.0, "no marker out at Costa Rica")
        self.assertGreater(lons[-1], 25.0, "no marker out at Malawi")
        plt.close(fig)

    def test_the_host_performs_on_the_winning_bar(self):
        """He is baked at the ranked strip's winning tip (the contact the
        judge praised), never at the old hard-coded empty corner."""
        src = (ROOT / "data_learning" / "charts.py").read_text()
        body = src.split("def _story_geo(", 1)[1].split("\ndef ", 1)[0]
        self.assertNotIn("_bake_host(leg, 0.30, 0.10", body)
        self.assertIn("_bake_host(bax", body)
        fig, plt = C._card_base()
        C._story_geo(fig, plt, _insight("geo_world"), "s", 1.0, "world")
        self.assertTrue(_host_extents(fig), "geo beat lost its host")
        plt.close(fig)

    def test_negative_values_do_not_break_the_bars(self):
        items = [("Japan", -0.5), ("Italy", -0.3), ("Germany", 0.2),
                 ("France", 0.4), ("Spain", 0.9)]
        fig, plt = C._card_base()
        ax, specs = C._story_geo(fig, plt, _insight("geo_world", items),
                                 "s", 1.0, "world")
        self.assertEqual(len(specs), 5)
        plt.close(fig)

    def test_geo_city_now_bakes_a_host_too(self):
        """geo_city was the ONLY pin renderer and had no bake at all, so
        the drifting overlay covered it."""
        items = [("New York", 90.0), ("Chicago", 60.0), ("Miami", 30.0)]
        ins = _insight("geo_city", items)
        fig, plt = C._card_base()
        C._story_geo_city(fig, plt, ins, "s", 1.0)
        self.assertTrue(_host_extents(fig), "geo_city still host-less")
        self.assertTrue(ins.host_baked)
        plt.close(fig)

    def test_the_studio_suppresses_the_overlay_on_geo_beats(self):
        from data_learning import studio_render as SR
        for k in ("geo_us", "geo_world", "geo_city"):
            self.assertIn(k, SR.BAKED_CHART_KINDS, k)


if __name__ == "__main__":
    unittest.main()
