"""No coloured dots.

Operator ruling, 2026-09-10: *"colored dots are not something we should be
using."*

A dot is a MARK only when its POSITION or its AREA is the datum — a city on
a map, a proportional bubble. Everywhere else the channel was using small
coloured circles as decoration, and decoration made of small coloured
circles is the most spreadsheet thing a chart can do:

  - a marker on every vertex of a line (the Excel default)
  - a dot standing in for an icon that failed to resolve — a unit that
    depicts nothing, pretending to be a pictograph
  - a white ring around either, which is what turns a mark into a sticker
"""
from __future__ import annotations

import ast
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib                                            # noqa: E402
matplotlib.use("Agg")

from data_learning import charts as C                        # noqa: E402
from data_learning import viz_scene as VS                    # noqa: E402
from data_learning.insights import Insight                   # noqa: E402
from data_learning.sources.base import DataPoint, Source     # noqa: E402

SRC = Source(name="X", publisher="P", url="https://x", access_date="2026-09-04")


def _code(fn) -> str:
    tree = ast.parse(inspect.getsource(fn).lstrip())
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            node.value = ""
    return ast.unparse(tree)


def _ins(kind, pairs, **kw):
    return Insight(kind=kind, topic="T", main_insight="m",
                   items=[DataPoint(label=a, value=b) for a, b in pairs],
                   source=SRC, **kw)


def _lum(c):
    from matplotlib.colors import to_rgb
    def _l(x):
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = (_l(v) for v in to_rgb(c))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)))
    return (lb + 0.05) / (la + 0.05)


class ALineHasNoMarkers(unittest.TestCase):
    """It was `"o"` at markersize 9 on every revealed point — a row of gold
    dots down the line. The line already says where the points are, and the
    two that matter (peak and end) are directly labelled."""

    def test_the_trend_draws_no_point_markers(self):
        ins = _ins("trend", [(str(y), v) for y, v in
                             ((1993, 2.1), (2000, 2.6), (2007, 3.1),
                              (2014, 3.6), (2021, 4.4), (2024, 4.9))],
                   unit="count", highlight_label="2024")
        fig, plt = C._card_base()
        try:
            ax, _ = C._story_trend(fig, plt, ins, "")
            marked = [ln for ln in ax.lines
                      if ln.get_marker() not in (None, "None", "", " ")]
            self.assertEqual(marked, [], "the line still wears dots")
        finally:
            plt.close(fig)


class NothingWearsAWhiteRing(unittest.TestCase):
    def test_no_composer_rings_a_mark_in_white(self):
        src = Path(ROOT / "data_learning" / "charts.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg not in ("edgecolor", "edgecolors"):
                    continue
                if isinstance(kw.value, ast.Constant) and \
                        str(kw.value.value).lower() in ("white", "#fff",
                                                        "#ffffff"):
                    self.fail(f"white ring at charts.py:{node.lineno}")


class ColourRampsStayInOneHue(unittest.TestCase):
    """The map ramped ACCENT -> HIGHLIGHT -> WARN: three hues, ending on the
    ALARM colour, so the biggest city was painted the same amber the
    baseline warning uses and meant nothing by it."""

    def test_the_geo_ramp_is_neutral_to_accent(self):
        for fn in (C._story_geo, C._story_geo_city):
            src = _code(fn)
            self.assertIn("[REST, HIGHLIGHT]", src, fn.__name__)
            self.assertNotIn("WARN]", src, fn.__name__)


class AUnitIsATileNotADot(unittest.TestCase):
    """When the icon does not resolve, the fallback must still be a mark
    that says "one of these" — a waffle unit — not a featureless disc."""

    def test_the_dot_field_falls_back_to_tiles(self):
        src = _code(VS.draw_dot_field)
        self.assertIn("rounded_rectangle", src)
        self.assertNotIn("ellipse", src)

    def test_the_pictograph_falls_back_to_tiles(self):
        src = _code(C._story_pictograph)
        self.assertNotIn("marker='o'", src.replace('"', "'"))

    def test_the_pictorial_race_draws_nothing_when_the_icon_fails(self):
        """It drew a 340pt white-ringed disc — a sticker where a picture
        should be. The bar already ends in a rounded cap at that point."""
        src = _code(C._story_pictorial_race)
        self.assertNotIn("scatter", src)


class ALabelInsideAMarkIsLegibleOnIt(unittest.TestCase):
    """Three times in one day: a label drawn inside a mark, in a colour
    hardcoded for the mark that used to be there, and then the mark's colour
    changed somewhere else for a good reason. `_ink_on` makes luminance
    decide so the pairing cannot go stale."""

    def test_every_mark_that_hosts_a_label_gets_readable_ink(self):
        for mark in (C.HIGHLIGHT, C.REST, C.WARN, C.CARD, C.GRID):
            ink = C._ink_on(mark)
            self.assertGreater(_contrast(ink, mark), 4.5,
                               f"{ink} on {mark} is not readable")

    def test_the_mid_tone_accent_never_fills_a_mark(self):
        """`ACCENT` (the dim partner) sits at luminance 0.19 — NEITHER ink
        clears 4.5 on it, which is what a mid-tone is. It used to fill the
        losing versus column, the supporting bars and the non-subject
        bubbles, and every label on those was a coin flip. `look.REST` is
        the neutral those became; nothing fills with `ACCENT` now."""
        best = max(_contrast(C.TEXT, C.ACCENT), _contrast(C.CARD, C.ACCENT))
        self.assertLess(best, 4.5, "ACCENT is no longer a mid-tone — "
                                   "this test's premise needs rechecking")
        src = Path(ROOT / "data_learning" / "charts.py").read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg in ("facecolor", "color") and \
                        isinstance(kw.value, ast.Name) and \
                        kw.value.id == "ACCENT":
                    self.fail(f"ACCENT fills a mark at charts.py:{node.lineno}")

    def test_the_ink_is_the_better_of_the_two_not_a_threshold(self):
        """A threshold is another constant that can be wrong for the next
        colour; a comparison cannot be."""
        for mark in ("#808080", "#7F7F7F", "#818181", C.HIGHLIGHT, C.REST):
            ink = C._ink_on(mark)
            other = C.TEXT if ink == C.CARD else C.CARD
            self.assertGreaterEqual(_contrast(ink, mark),
                                    _contrast(other, mark), mark)

    def test_a_bright_mark_gets_dark_ink_and_a_dark_one_bright(self):
        self.assertEqual(C._ink_on(C.HIGHLIGHT), C.CARD)
        self.assertEqual(C._ink_on(C.REST), C.TEXT)

    def test_the_bubble_number_is_readable_on_every_bubble(self):
        ins = _ins("bubbles", [("China", 11.4), ("US", 5.0),
                               ("India", 2.8), ("Russia", 1.7)],
                   unit="count", highlight_label="China")
        fig, plt = C._card_base()
        try:
            ax, _ = C._story_bubbles(fig, plt, ins, "")
            circles = [p for p in ax.patches if hasattr(p, "get_radius")]
            self.assertTrue(circles)
            for circ in circles:
                face = circ.get_facecolor()
                near = min(ax.texts,
                           key=lambda t: (t.get_position()[0] - circ.center[0]) ** 2
                           + (t.get_position()[1] - circ.center[1]) ** 2)
                self.assertGreater(_contrast(near.get_color(), face), 4.5,
                                   f"{near.get_text()!r} on {face}")
        finally:
            plt.close(fig)

    def test_no_composer_hardcodes_an_ink_for_a_mark(self):
        src = Path(ROOT / "data_learning" / "charts.py").read_text()
        self.assertNotIn('color="#0B1020"', src)


if __name__ == "__main__":
    unittest.main()
