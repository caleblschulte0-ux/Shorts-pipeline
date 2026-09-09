"""A MACHINE THAT CRASHES LOOKS EXACTLY LIKE A MACHINE THAT REFUSED.

`viz_scene._guarded` is a net, by design: a beat whose picture blows up falls
back to a chart rather than taking the day's video with it. That is the right
production behaviour and it is not in question here.

What IS in question is that the net made a whole class of bug invisible to the
suite. Every existing sweep — the void sweep, the ratio sweep, the off-the-edge
sweep — calls `_guarded` and then does this:

    if got is None:
        continue          # refused honestly, nothing to judge

`None` means BOTH "this machine looked at the data and honestly declined" and
"this machine raised". So a machine could crash on every input in the
catalogue and every test would go green by skipping it, while production
quietly drew a chart instead.

That is not hypothetical. On 2026-09-09, fitting the bin labels in
`draw_sorter` bound `_st` — the name already holding that machine's `stage()`
dict — to a string. Every sorter beat in the catalogue raised `TypeError` and
fell back to a chart. The full suite passed. It was caught by a human looking
at a contact sheet and noticing the word REFUSED.

So: this file renders every machine in the dispatch table over the awkward
inputs, and asserts `_MACHINE_FAILED` stays EMPTY. A refusal is fine — a
refusal is an editorial answer. An exception is a bug, and now it has a test
that says so out loud instead of a `continue` that hides it.

Runs standalone:  python3 tests/test_a_machine_that_crashes_is_invisible.py
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
from data_learning.insights import Insight                # noqa: E402
from data_learning.sources.base import DataPoint, Source  # noqa: E402

BOX = (vs.RX0, vs.RTOP, vs.RX1, vs.MACHINE_BOT)
SRC = Source(name="X", publisher="Y", url="https://x", access_date="2026-09-09")

#: Shapes a real story hands a machine. Long multi-word labels are in here
#: deliberately: the short "A"/"B" pairs the older sweeps use are exactly what
#: hid both the off-the-edge bug and the crash above.
CASES = [
    [("1990 (pre-vaccine)", 4000.0), ("2019 (two-dose era)", 100.0)],
    [("Massachusetts", 96.5), ("Mississippi", 52.7)],
    [("Before the vaccine was introduced nationally", 4000.0),
     ("After", 100.0)],
    [("San Jose", 11.3), ("Los Angeles", 9.7), ("Miami", 8.2),
     ("Seattle", 6.8), ("Denver", 5.4)],
    [("Applied", 12000.0), ("Screened", 9800.0), ("Interviewed", 2100.0),
     ("Offered", 1700.0), ("Hired", 1500.0)],
    [("Housing", 4200.0), ("Transit", 2600.0), ("Parks", 1400.0),
     ("Admin", 900.0)],
    [(str(2016 + k), 42.0 + k * 7) for k in range(8)],
]
UNITS = ("count", "percent", "usd", "")
REVEALS = (0.0, 0.35, 0.92, 1.0)


def _render(kind, pairs, unit, reveal):
    ins = Insight(kind="scene", topic="cases per year", main_insight="m",
                  items=[DataPoint(label=a, value=float(b)) for a, b in pairs],
                  source=SRC, unit=unit, highlight_label=pairs[0][0])
    safe = vs.drawable_insight(ins)
    if safe is None:
        return
    img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    vs._guarded(kind, vs._MACHINE_DRAW[kind], d, img, BOX, safe,
                charts.HIGHLIGHT, reveal, safe.unit)


class NoMachineRAISESOnTheCatalogue(unittest.TestCase):
    def setUp(self):
        self._saved = set(vs._MACHINE_FAILED)
        vs._MACHINE_FAILED.clear()

    def tearDown(self):
        vs._MACHINE_FAILED.clear()
        vs._MACHINE_FAILED.update(self._saved)

    def test_every_machine_survives_every_shape(self):
        for kind in sorted(vs._MACHINE_DRAW):
            for pairs in CASES:
                _render(kind, pairs, "count", 0.92)
        self.assertEqual(sorted(vs._MACHINE_FAILED), [],
                         "machines that RAISED (production draws a chart "
                         "instead and every other test skips them)")

    def test_every_machine_survives_every_unit(self):
        """`unit` reaches the label formatter, which is where a fitter that
        measures one string and draws another goes wrong."""
        for kind in sorted(vs._MACHINE_DRAW):
            for unit in UNITS:
                _render(kind, CASES[0], unit, 0.92)
                _render(kind, CASES[3], unit, 0.92)
        self.assertEqual(sorted(vs._MACHINE_FAILED), [])

    def test_every_machine_survives_the_whole_reveal(self):
        """Machines gate work behind `reveal`; a crash at 1.0 in a branch that
        only runs at full reveal is a crash on the FINAL frame of the beat —
        the one the still thumbnail is cut from."""
        for kind in sorted(vs._MACHINE_DRAW):
            for r in REVEALS:
                _render(kind, CASES[0], "count", r)
                _render(kind, CASES[4], "count", r)
        self.assertEqual(sorted(vs._MACHINE_FAILED), [])

    def test_a_degenerate_input_is_REFUSED_not_raised(self):
        """Zeroes, negatives and one-item lists are what a thin source hands
        the kit on a bad day. Declining to draw is the right answer; dividing
        by zero is not."""
        for kind in sorted(vs._MACHINE_DRAW):
            for pairs in ([("Only", 1.0)],
                          [("A", 0.0), ("B", 0.0)],
                          [("A", -40.0), ("B", 12.0)],
                          [("A", 1.0), ("B", 1.0)],
                          [("A", 1e12), ("B", 1e-9)]):
                _render(kind, pairs, "count", 0.92)
        self.assertEqual(sorted(vs._MACHINE_FAILED), [])


class TheNetIsStillThere(unittest.TestCase):
    """Strengthening the suite must not tempt anyone to remove the fallback.
    A crash in production still has to draw a chart, not kill the day."""

    def test_guarded_still_swallows_and_reports(self):
        def boom(*a, **kw):
            raise ValueError("surprise")
        saved = set(vs._MACHINE_FAILED)
        vs._MACHINE_FAILED.clear()
        try:
            self.assertIsNone(vs._guarded("boom", boom))
            self.assertIn("boom", vs._MACHINE_FAILED)
        finally:
            vs._MACHINE_FAILED.clear()
            vs._MACHINE_FAILED.update(saved)

    def test_a_machine_may_still_decline(self):
        """`None` from a machine that looked at the data and said no must NOT
        register as a failure — that is the distinction this file rests on."""
        saved = set(vs._MACHINE_FAILED)
        vs._MACHINE_FAILED.clear()
        try:
            _render("chairs", [("People", 500.0), ("Seats", 500.0)],
                    "count", 1.0)
            self.assertEqual(sorted(vs._MACHINE_FAILED), [])
        finally:
            vs._MACHINE_FAILED.clear()
            vs._MACHINE_FAILED.update(saved)


class NoMachineCutsALabelMidWord(unittest.TestCase):
    """23 machines sliced their labels at a hardcoded character count, which
    is why "1990 (pre-vaccine)" shipped as "1990 (pre-vacc". `fit_text`
    replaced every one of them: it shrinks first and only ellipsises when the
    text would go below readable size.

    A slice is not just ugly — it is silent. It cannot be measured by the
    off-the-edge sweep (the text IS inside the frame) and the showrunner
    reads it as a word it does not recognise rather than as a defect.
    """

    def test_no_label_is_sliced_to_a_hardcoded_width(self):
        import re
        src = (_REPO / "data_learning" / "viz_scene.py").read_text()
        bad = []
        for m in re.finditer(r'(_label_of\([a-z_0-9]*\)|'
                             r'getattr\((?:p|p_|star|items\[[^]]+\]), '
                             r'"label", ""\)\)?)\[:\d+\]', src):
            bad.append(src[:m.start()].count("\n") + 1)
        self.assertEqual(bad, [], f"hardcoded label truncation at lines {bad}")


class TheFITTERSResultIsTheONEThatGetsDRAWN(unittest.TestCase):
    """`fit_text` returns a (font, text) PAIR because both halves matter: it
    may shrink the font, ellipsise the text, or do both.

    Three machines took the fitted TEXT and drew it at a hardcoded
    `_pil_font(34)` / `_pil_font(28)` — density, basket and skyline. Every one
    of them measured whether the label fitted at, say, 22pt and then drew it
    at 34pt, which is a longer string than the one that was measured. The
    fitter ran, returned the right answer, and the machine ignored it.

    Nothing catches this by rendering: the label overflows by a little, stays
    inside the frame, and the off-the-edge sweep reports 0.00%. It is only
    visible by reading the pair back at the call site.
    """

    def test_every_fit_text_call_draws_with_the_font_it_returned(self):
        import re
        src = (_REPO / "data_learning" / "viz_scene.py").read_text()
        bad = []
        for m in re.finditer(r"(\w+), (\w+) = fit_text\(", src):
            font, text = m.group(1), m.group(2)
            tail = src[m.end():m.end() + 700]
            i = tail.find("d.text(")
            seg = tail[i:i + 300] if i >= 0 else ""
            if not (f"font={font}" in seg
                    and re.search(r"\b" + re.escape(text) + r"\b", seg)):
                bad.append((src[:m.start()].count("\n") + 1, font, text))
        self.assertEqual(bad, [], "fitted text drawn at an unfitted size")


class AFitterMayNotSHADOWWhatTheMachineStillNeeds(unittest.TestCase):
    """The sorter crash in this file's docstring, stated as a rule.

    `stage(insight, ...)` is bound to `_st` in twenty-odd machines and read
    again further down for its particle and flourish. A fitter unpacking into
    `_st` replaces the dict with a string, and the machine dies on the next
    subscript. Short throwaway names around a long function are how that
    happens, so the fitter's targets stay out of the names the kit reserves.
    """

    RESERVED = ("_st", "_stage", "items", "vals", "box", "d", "canvas",
                "color", "reveal", "unit", "insight", "e")

    def test_no_fit_text_target_shadows_a_reserved_name(self):
        import re
        src = (_REPO / "data_learning" / "viz_scene.py").read_text()
        bad = []
        for m in re.finditer(r"(\w+), (\w+) = fit_text\(", src):
            for name in (m.group(1), m.group(2)):
                if name in self.RESERVED:
                    bad.append((src[:m.start()].count("\n") + 1, name))
        self.assertEqual(bad, [], "a fitter overwrote a name the machine reads")


if __name__ == "__main__":
    unittest.main()
