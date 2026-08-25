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

# These tests pin GEOMETRY — the clamp's arithmetic and where the host is
# baked — against what matplotlib actually draws. They must not also depend
# on the SVG rasterizer: the auto-merge tests job has neither cairosvg nor
# a Playwright chromium, so there `_host_img` returns None, `_bake_host`
# silently bakes nothing, and the geo assertions fail for a reason that has
# nothing to do with the contract under test (first seen the day pipefail
# made this job's failures visible at all). A fixed 300x300 opaque raster
# exercises the identical placement arithmetic deterministically in any
# environment; REAL rasterization is proven by preview_explainer.yml's
# mascot primitive gate and every preview render.
_REAL_HOST_IMG = None


def setUpModule():
    global _REAL_HOST_IMG
    import numpy as np
    _REAL_HOST_IMG = C._host_img
    stub = np.zeros((300, 300, 4), dtype=float)
    stub[..., 3] = 1.0
    C._host_img = lambda action, phase: stub
    C._HOST_IMG_CACHE.clear()


def tearDownModule():
    C._host_img = _REAL_HOST_IMG
    C._HOST_IMG_CACHE.clear()

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


class TestTheAnchorTravelsAcrossTheBeat(unittest.TestCase):
    """The last cause the verdicts kept naming after grip acts landed.

    2026-08-24/25, verbatim: "Data just hovers/slides in the same spot above
    the 1972-1983 bars with no setup->action->payoff ... only at seg4:end
    does he finally ride the falling line down". The act was right by then;
    the ANCHOR was standing still — every compositor derives it from
    `reveal`, and `reveal` saturates at `full_by` and sits at 1.0 for the
    rest of the beat. `_TOUR` is beat progress instead, so he still has
    somewhere to be at second twelve.
    """

    def test_reveal_saturates_but_the_tour_does_not(self):
        """The bug in one assertion: the quantity the anchor used to follow
        stops moving well before the beat ends."""
        frames, full_by = 30, 0.6
        reveal = [min(1.0, (f / frames) / full_by) for f in range(1, frames + 1)]
        self.assertEqual(reveal[-1], reveal[int(frames * full_by) + 1])
        tour = [f / frames for f in range(1, frames + 1)]
        self.assertGreater(tour[-1], tour[int(frames * full_by) + 1])

    def test_he_works_up_the_field_and_ends_on_the_winner(self):
        n = 5
        self.assertAlmostEqual(C._tour_index(n, 0.0), n - 1)
        self.assertEqual(C._tour_index(n, 1.0), 0.0)
        self.assertEqual(C._tour_index(n, C.TOUR_FINALE), 0.0)

    def test_the_position_never_runs_backwards(self):
        seq = [C._tour_index(5, i / 200) for i in range(201)]
        for a, b in zip(seq, seq[1:]):
            self.assertLessEqual(b, a + 1e-9, "the tour must not backtrack")

    def test_he_is_never_parked_for_most_of_the_beat(self):
        """The actual regression guard: across the first TOUR_FINALE of the
        beat he must not sit at one anchor for a long stretch."""
        step = C.TOUR_FINALE / 5
        moved = sum(1 for i in range(160)
                    if abs(C._tour_index(5, (i + 1) / 200)
                           - C._tour_index(5, i / 200)) > 1e-9)
        self.assertGreater(moved, 20, "the anchor barely moves — that is the "
                                      "'hovers in the same spot' note again")
        self.assertGreater(step, 0)

    def test_transit_is_interpolated_not_a_teleport(self):
        """Snapping bar-to-bar trades 'hovers' for 'teleports' — the same
        note in a different costume. Steps must be small."""
        seq = [C._tour_index(5, i / 400) for i in range(401)]
        self.assertLess(max(abs(b - a) for a, b in zip(seq, seq[1:])), 0.35)

    def test_the_tip_is_interpolated_between_the_two_bars(self):
        vals = [100.0, 80.0, 60.0, 40.0, 20.0]
        self.assertAlmostEqual(C._tour_tip(vals, 4.0), 20.0)
        self.assertAlmostEqual(C._tour_tip(vals, 0.0), 100.0)
        mid = C._tour_tip(vals, 3.5)
        self.assertGreater(mid, 20.0)
        self.assertLess(mid, 40.0)

    def test_a_single_value_chart_is_untouched(self):
        for t in (0.0, 0.5, 1.0):
            self.assertEqual(C._tour_index(1, t), 0.0)
        self.assertAlmostEqual(C._tour_tip([42.0], 0.0), 42.0)

    def test_an_empty_series_does_not_crash(self):
        self.assertEqual(C._tour_tip([], 0.0), 0.0)

    def test_both_ranked_compositors_use_the_tour(self):
        src = (ROOT / "data_learning" / "charts.py").read_text()
        for fn in ("_story_bars", "_story_pictorial_race"):
            body = src.split(f"def {fn}(", 1)[1].split("\ndef ", 1)[0]
            self.assertIn("_tour_index", body, fn)
            self.assertIn("_tour_tip", body, fn)

    def test_the_build_loop_advances_the_tour_by_beat_progress(self):
        src = (ROOT / "data_learning" / "charts.py").read_text()
        body = src.split("def render_story_build(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("_TOUR = f / max(1, frames)", body)

    def test_the_host_actually_moves_in_a_rendered_beat(self):
        """End to end on the real compositor: bake the same chart at three
        points in the beat and require the host's drawn position to differ."""
        pts = [DataPoint(l, v, "kg") for l, v in RANKED]
        ins = Insight(kind="rank", topic="T", main_insight="Slovenia leads",
                      items=pts, source=SRC, unit="kg",
                      highlight_label=pts[0].label)
        seen = []
        for tour in (0.05, 0.45, 0.95):
            C._TOUR = tour
            fig, plt = C._card_base()
            C._story_bars(fig, plt, ins, "sub", 1.0)
            boxes = _host_extents(fig)
            self.assertTrue(boxes, f"no host baked at tour {tour}")
            seen.append(boxes[0])
            plt.close(fig)
        C._TOUR = 1.0
        self.assertNotAlmostEqual(seen[0][2], seen[1][2], places=3,
                                  msg="host did not move between beats")
        self.assertNotAlmostEqual(seen[1][2], seen[2][2], places=3,
                                  msg="host did not move between beats")
