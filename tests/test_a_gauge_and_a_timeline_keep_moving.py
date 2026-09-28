"""The full-frame gauge and timeline keep MOVING until the cut.

`coldest-place-in-the-universe-is-human-made` was blocked by the temporal
gate fifteen times between 2026-09-07 and 2026-09-28 (duplicate_ratio
0.51-0.54 against the 0.45 ceiling), and the judge called four more
explainers "dead air" over the same three days. Rendered offline, the held
stretches were full-frame renderers, not scene machines: the GAUGE
(`fill_vessel`) sat five seconds with no block moving, and the TIMELINE
alone measured 0.50 held with a 68-frame still run. Both rolled a private
ease-out and then held the finished picture.

`MotionMustBeVISIBLE` (tests/test_data_has_physics.py) measures every scene
machine with the gate's own detector. It never measured these, because they
are `charts.FULLFRAME_RENDERERS`, not `_MACHINE_DRAW`. This test is that
measurement for them, at the same pace and against the same ceilings, and it
refuses a new full-frame renderer that nobody measures.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# The gate's own numbers, as in MotionMustBeVISIBLE: 192 frames is an
# 8-second beat sampled at 24fps; a 45-frame run and a 0.45 ratio are the
# phase-1 `max_dup_run_frames` / `max_duplicate_ratio`.
FRAMES = 192
CEILING = 45
DUP_CEILING = 0.45

#: Full-frame renderers measured somewhere else, or that cannot be given an
#: offline sample — each with the reason. Anything not named here is
#: measured below or this test fails.
MEASURED_ELSEWHERE = {
    "scene": "every machine it draws: MotionMustBeVISIBLE",
    "mechanic": "refused at render time by viz_scene.mechanic_motion_ok",
    "race": "needs a real photo per contender (network); returns None offline",
    "scale_stack": "needs a generated cut-out (network); returns None offline",
    "diorama": "needs generated scene art (network); returns None offline",
}


def _insight(kind, pairs, unit="count", topic="t", dated=False):
    from data_learning.insights import Insight
    from data_learning.sources.base import DataPoint, Source
    src = Source(name="X", publisher="Y", url="https://x",
                 access_date="2026-09-28")
    return Insight(kind=kind, topic=topic, main_insight="m",
                   items=[DataPoint(label=str(a), value=float(b),
                                    period=str(a) if dated else None)
                          for a, b in pairs],
                   source=src, unit=unit, highlight_label=str(pairs[0][0]))


CASES = (
    # a share, a sliver, a raw magnitude and a fall: the four arcs a gauge
    # draws. The sliver is the hard one — a 3% arc is ~40px long.
    ("gauge_share", "fill_vessel",
     lambda: _insight("fill_vessel", [("Recycled", 22.3)], "percent",
                      "e-waste formally recycled")),
    ("gauge_sliver", "fill_vessel",
     lambda: _insight("fill_vessel", [("Share", 3.0)], "percent")),
    ("gauge_raw", "fill_vessel",
     lambda: _insight("fill_vessel", [("Boomerang Nebula", 1.0),
                                      ("Cold Atom Lab", 1e-10)], "K",
                      "how cold it gets")),
    ("gauge_fall", "fill_vessel",
     lambda: _insight("fill_vessel", [("Change", -12.0)], "percent")),
    ("timeline_dated", "timeline",
     lambda: _insight("timeline", [(str(2016 + k), 40 + 9 * k)
                                   for k in range(8)],
                      "count", "ships by year", dated=True)),
    ("timeline_number_line", "timeline",
     lambda: _insight("timeline", [("Deep space", 2.7)], "K", "how cold")),
    ("orbit", "orbit",
     lambda: _insight("orbit", [("Earth", 1.0), ("Mars", 1.5),
                                ("Jupiter", 5.2)], "AU",
                      "distance from the Sun")),
)


def _measure(job):
    """(longest still run, held ratio) by the gate's block detector, or
    None when the renderer declines. Module level so a worker can run it."""
    import numpy as np
    from PIL import Image
    from data_learning import charts
    from shared.fsutil import frames_in_order
    name, kind, idx = job
    ins = CASES[idx][2]()
    with tempfile.TemporaryDirectory() as td:
        if charts.FULLFRAME_RENDERERS[kind](ins, Path(td), name, FRAMES) is None:
            return None
        fs = frames_in_order(Path(td).glob(name + "*.png"))
        arr = [np.asarray(Image.open(f).convert("L").resize((192, 192)),
                          dtype=np.float32) for f in fs]

    def _block_max(a, b):
        return max(np.abs(a[r * 16:(r + 1) * 16, c * 16:(c + 1) * 16]
                          - b[r * 16:(r + 1) * 16, c * 16:(c + 1) * 16]).mean()
                   for r in range(12) for c in range(12))
    run = best = dup = 0
    for k in range(len(arr) - 1):
        if _block_max(arr[k], arr[k + 1]) < 6.0:
            run += 1
            dup += 1
            best = max(best, run)
        else:
            run = 0
    return best, dup / max(1, len(arr) - 1)


class AFullFrameChartKeepsMoving(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            import numpy  # noqa: F401
            import PIL  # noqa: F401
        except ImportError:  # noqa: BLE001
            raise unittest.SkipTest("numpy / PIL not installed")
        import os
        jobs = [(name, kind, i) for i, (name, kind, _) in enumerate(CASES)]
        with ProcessPoolExecutor(
                max_workers=max(1, min(4, os.cpu_count() or 1))) as ex:
            cls.runs = dict(zip((j[0] for j in jobs), ex.map(_measure, jobs)))

    def test_every_case_actually_drew(self):
        """A renderer that declines is not a renderer that moves."""
        self.assertEqual([n for n, r in self.runs.items() if r is None], [])

    def test_no_still_run_the_gate_would_call_frozen(self):
        worst = {n: r[0] for n, r in self.runs.items()
                 if r is not None and r[0] > CEILING}
        self.assertEqual(worst, {}, f"full-frame charts that hold still: {worst}")

    def test_not_mostly_held(self):
        held = {n: round(r[1], 2) for n, r in self.runs.items()
                if r is not None and r[1] > DUP_CEILING}
        self.assertEqual(held, {}, f"full-frame charts mostly held: {held}")

    def test_every_full_frame_renderer_is_measured_or_excused(self):
        """The machine test measured only what somebody remembered to list,
        and these two were never listed. A new full-frame kind is measured
        here or excused by name, with a reason, above."""
        from data_learning import charts
        from data_learning import viz_scene  # noqa: F401 — registers scene kinds
        measured = {kind for _, kind, _ in CASES}
        unmeasured = sorted(set(charts.FULLFRAME_RENDERERS)
                            - measured - set(MEASURED_ELSEWHERE))
        self.assertEqual(unmeasured, [])


class TheFinishedGaugeStillSaysTheValue(unittest.TestCase):
    """The flow is decoration ON the value; it must not change what is said.
    The last frame is the true number and the true arc, and the number has
    arrived with a fifth of the span to spare so it can be read."""

    def test_the_number_is_final_from_arrival_to_the_cut(self):
        """Every frame from FLOW_ARRIVE on shows the same, final number:
        nothing flows inside the gauge, only along its arc."""
        import numpy as np
        from PIL import Image
        from data_learning import charts
        from shared.fsutil import frames_in_order
        ins = _insight("fill_vessel", [("Recycled", 22.3)], "percent")
        n = 60
        with tempfile.TemporaryDirectory() as td:
            charts.FULLFRAME_RENDERERS["fill_vessel"](ins, Path(td), "g", n)
            fs = frames_in_order(Path(td).glob("g*.png"))
            # the number's box, well inside the arc (R=300 about 540,940)
            box = (340, 800, 740, 980)
            crops = [np.asarray(Image.open(f).crop(box)) for f in fs]
        first = int(np.ceil(charts.FLOW_ARRIVE * n))
        for k in range(first, n):
            self.assertTrue(np.array_equal(crops[k], crops[-1]),
                            f"frame {k + 1} of {n} differs from the final number")
        self.assertFalse(np.array_equal(crops[0], crops[-1]),
                         "the number never counted — the crop missed it")


if __name__ == "__main__":
    unittest.main()
