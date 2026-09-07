"""Every machine, against every hostile insight. Nothing may raise.

A raise inside a render is not a bad picture — it is a lost video. The
machines are 42 independent drawing functions doing arithmetic on numbers
that come from live sources, so the failure mode is not hypothetical: the
first sweep of this matrix found 215 raises in 5,400 calls, and 38 of the 42
machines died on a single NaN.

None of it was exotic data. A rate with a zero denominator, a division inside
a transform, a source that ships `null` as `NaN`, a series that legitimately
goes below zero. The two fixes are both at the choke point rather than in
forty draw functions, which is the only version of this that stays true:

  * `drawable_insight` strips values a picture cannot be drawn from, ONCE,
    before anything is pruned or drawn. A machine left with too little then
    refuses on its own and the beat falls back to a chart.
  * `_SIGN_SAFE` says which machines can honestly draw a negative — the ones
    that encode POSITION against the series' range. The rest turn a value
    into a height, a length or a count of objects, and a negative one of
    those does not exist. Refusing is better than `abs()`, which renders a
    net migration of -5 the same size as +5 and shows nobody the sign flip.

Runs standalone:  python3 tests/test_machines_never_crash.py
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

from PIL import Image, ImageDraw                       # noqa: E402
from data_learning import charts, viz_scene as vs      # noqa: E402
from data_learning.insights import Insight             # noqa: E402
from data_learning.sources.base import DataPoint, Source  # noqa: E402

SRC = Source(name="X", publisher="Y", url="https://x", access_date="2026-01-01")
BOX = (vs.RX0, vs.RTOP, vs.RX1, vs.MACHINE_BOT)
REVEALS = (0.0, 0.001, 0.37, 0.5, 0.999, 1.0)


def _mk(pairs, unit="count", topic="t", main="m", baseline=None):
    ins = Insight(kind="scene", topic=topic, main_insight=main,
                  items=[DataPoint(label=l, value=v) for l, v in pairs],
                  source=SRC, unit=unit,
                  highlight_label=pairs[0][0] if pairs else "")
    if baseline:
        ins.baseline = DataPoint(label=baseline[0], value=baseline[1])
    return ins


CASES = {
    "empty": _mk([]),
    "one item": _mk([("A", 5.0)]),
    "two items": _mk([("A", 5.0), ("B", 3.0)]),
    "all zero": _mk([("A", 0.0), ("B", 0.0), ("C", 0.0)]),
    "one zero": _mk([("A", 0.0), ("B", 3.0), ("C", 9.0)]),
    "all negative": _mk([("A", -5.0), ("B", -12.0), ("C", -1.0)]),
    "mixed sign": _mk([("A", -5.0), ("B", 12.0), ("C", 0.0)]),
    "identical": _mk([("A", 7.0)] * 6),
    "huge": _mk([("A", 9.9e15), ("B", 1.0), ("C", 4.4e12)]),
    "tiny": _mk([("A", 1e-9), ("B", 2e-9), ("C", 5e-10)]),
    "one huge rest zero": _mk([("A", 1e9), ("B", 0.0), ("C", 0.0), ("D", 0.0)]),
    "very long labels": _mk([("A" * 90, 5.0), ("B" * 70, 3.0), ("C" * 50, 1.0)]),
    "empty labels": _mk([("", 5.0), ("", 3.0), ("", 1.0)]),
    "unicode labels": _mk([("日本語ラベル", 5.0), ("Ünïcödé—ø", 3.0), ("🙂🙃", 1.0)]),
    "twenty items": _mk([(f"L{k}", float(k + 1)) for k in range(20)]),
    "a decade": _mk([(str(2010 + k), 10.0 + k) for k in range(12)]),
    "a projection": _mk([(str(2010 + k), 10.0 + k) for k in range(8)]
                        + [("2045", 90.0)]),
    "percentages summing to 100": _mk([("A", 50.0), ("B", 30.0), ("C", 20.0)],
                                      unit="percent"),
    "percentages that are rates": _mk([("A", 37.0), ("B", 21.0), ("C", 18.0)],
                                      unit="percent"),
    "with a baseline": _mk([("A", 11.3), ("B", 9.7)], baseline=("avg", 5.9)),
    "baseline of zero": _mk([("A", 11.3), ("B", 9.7)], baseline=("avg", 0.0)),
    "a NaN": _mk([("A", float("nan")), ("B", 3.0), ("C", 1.0)]),
    "an infinity": _mk([("A", float("inf")), ("B", 3.0), ("C", 1.0)]),
    "no unit": _mk([("A", 5.0), ("B", 3.0), ("C", 1.0)], unit=""),
    "an awkward unit": _mk([("A", 5.0), ("B", 3.0)],
                           unit="per 100,000 people-years"),
}


def _refused(kind, ins):
    """What the dispatch decides before a draw function is ever called."""
    safe = vs.drawable_insight(ins)
    if safe is None:
        return True
    if kind not in vs._SIGN_SAFE and any(
            float(getattr(q, "value", 0) or 0) < 0 for q in safe.items):
        return True
    return False


class NoMachineEverRaises(unittest.TestCase):
    def test_the_whole_matrix(self):
        fails = []
        for kind, fn in sorted(vs._MACHINE_DRAW.items()):
            for cname, ins in CASES.items():
                safe = vs.drawable_insight(ins)
                if _refused(kind, ins):
                    continue
                for rv in REVEALS:
                    canvas = Image.new("RGBA", (1080, 1920), (18, 20, 28, 255))
                    d = ImageDraw.Draw(canvas)
                    try:
                        fn(d, canvas, BOX, safe, charts.HIGHLIGHT, rv, safe.unit)
                    except Exception as e:  # noqa: BLE001
                        fails.append(f"{kind} / {cname} / reveal={rv}: "
                                     f"{type(e).__name__}: {str(e)[:80]}")
        self.assertEqual(fails[:12], [], f"{len(fails)} machine crashes")


class TheChokePointsHold(unittest.TestCase):
    def test_a_NaN_is_stripped_and_the_rest_kept(self):
        out = vs.drawable_insight(CASES["a NaN"])
        self.assertEqual([p.label for p in out.items], ["B", "C"])

    def test_an_infinity_is_stripped(self):
        out = vs.drawable_insight(CASES["an infinity"])
        self.assertEqual([p.label for p in out.items], ["B", "C"])

    def test_a_clean_insight_is_returned_UNCOPIED(self):
        """The normal path must cost a scan and nothing else."""
        ins = CASES["two items"]
        self.assertIs(vs.drawable_insight(ins), ins)

    def test_nothing_drawable_left_means_no_scene(self):
        self.assertIsNone(vs.drawable_insight(
            _mk([("A", float("nan")), ("B", float("inf"))])))

    def test_an_undrawable_baseline_is_dropped_not_kept(self):
        ins = _mk([("A", 5.0), ("B", 3.0)], baseline=("avg", float("nan")))
        self.assertIsNone(vs.drawable_insight(ins).baseline)

    def test_the_sign_safe_set_is_the_position_encoders(self):
        """A machine encoding SIZE cannot draw a negative. Held as a list so
        the next machine has to make the choice deliberately."""
        import inspect
        for kind in sorted(vs._MACHINE_DRAW):
            src = inspect.getsource(vs._MACHINE_DRAW[kind])
            if kind in vs._SIGN_SAFE:
                continue
            self.assertNotIn("v / vmax) * (bot - top)", src, kind)

    def test_the_dispatch_refuses_negatives_for_a_size_encoder(self):
        self.assertTrue(_refused("skyline", CASES["mixed sign"]))
        self.assertTrue(_refused("centre", CASES["mixed sign"]))
        self.assertFalse(_refused("coaster", CASES["mixed sign"]))

    def test_the_guard_returns_None_rather_than_raising(self):
        def boom(*a, **k):
            raise ZeroDivisionError("nope")
        self.assertIsNone(vs._guarded("test-machine", boom))

    def test_the_guard_reports_once_and_does_not_swallow_silently(self):
        import inspect
        src = inspect.getsource(vs._guarded)
        self.assertIn("print(", src, "a swallowed exception nobody sees")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class EveryMachineHasAMeasuredSample(unittest.TestCase):
    """The motion test can only measure what it has data for.

    Its case list grew batch by batch, so a machine was measured only if
    somebody remembered to add it. On 2026-09-07 a sweep of all forty-two
    found four that had never been measured and were failing the cadence gate
    at production frame size — darts, funnel, pipes and road. The list is not
    the problem; the fact that nothing noticed the gap is.
    """

    def test_the_motion_test_covers_every_machine_in_the_table(self):
        import tests.test_data_has_physics as phys
        import inspect
        src = inspect.getsource(phys.MotionMustBeVISIBLE)
        missing = sorted(k for k in vs._MACHINE_DRAW
                         if f'("{k}"' not in src)
        self.assertEqual(
            missing, [],
            "machines with no measured motion sample — a machine nobody "
            f"measures is one that ships frozen: {missing}")
