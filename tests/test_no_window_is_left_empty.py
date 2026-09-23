"""A PICTURE THAT FAILS TO RENDER NEVER LEAVES ITS WINDOW EMPTY.

Every span is laid at its own t0 and enabled only for its own window, so a
picture that failed to render left its window with nothing in it: "seg3:end
(t=32.92s) is a completely empty gradient frame with only the caption 'that
should worry'. The whole picture drops out while the narration is at its key
line" (teen-ai-companion-boom, three verdicts, 2026-09-22/23).
`studio_render.cover_every_window` tries a spare candidate for the same
window, then re-draws a neighbour across both windows. Held here with a fake
renderer, and by checking the render loop routes through it.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from data_learning import studio_render as SR  # noqa: E402

W = [(10.0, 16.0), (16.0, 22.0)]


def _drawer(broken):
    calls = []

    def draw(kind, t0, t1, tag, first):
        calls.append((kind, t0, t1))
        if kind in broken:
            return None
        return {"kind": kind, "path": f"{kind}_{tag}", "t0": t0, "t1": t1}
    return draw, calls


def _covered(spans, a, b):
    t = a
    for sp in sorted(spans, key=lambda x: x["t0"]):
        if sp["t0"] > t + 1e-6:
            return False
        t = max(t, sp["t1"])
    return t >= b - 1e-6


class NoWindowIsLeftEmpty(unittest.TestCase):
    def test_all_render(self):
        draw, _ = _drawer(set())
        out = SR.cover_every_window(["bars", "balance_scene"], W, draw, [], 10.0,
                                    log=lambda m: None)
        self.assertEqual([s["kind"] for s in out], ["bars", "balance_scene"])

    def test_a_failed_window_takes_a_spare(self):
        draw, calls = _drawer({"stack"})
        out = SR.cover_every_window(["bars", "stack"], W, draw, ["hurdle_scene"],
                                    10.0, log=lambda m: None)
        self.assertEqual([s["kind"] for s in out], ["bars", "hurdle_scene"])
        self.assertIn(("hurdle_scene", 16.0, 22.0), calls)
        self.assertTrue(_covered(out, 10.0, 22.0))

    def test_no_spare_widens_the_previous_picture(self):
        draw, calls = _drawer({"stack", "hurdle_scene"})
        out = SR.cover_every_window(["bars", "stack"], W, draw, ["hurdle_scene"],
                                    10.0, log=lambda m: None)
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0]["kind"], out[0]["t0"], out[0]["t1"]),
                         ("bars", 10.0, 22.0))
        self.assertTrue(_covered(out, 10.0, 22.0))

    def test_a_failed_first_window_widens_the_next(self):
        draw, _ = _drawer({"stack"})
        out = SR.cover_every_window(["stack", "bars"], W, draw, [], 10.0,
                                    log=lambda m: None)
        self.assertEqual((out[0]["kind"], out[0]["t0"], out[0]["t1"]),
                         ("bars", 10.0, 22.0))

    def test_the_render_loop_uses_it(self):
        src = (ROOT / "data_learning" / "studio_render.py").read_text()
        body = src[src.index("def render("):]
        self.assertIn("seg.spans = cover_every_window(", body)


if __name__ == "__main__":
    unittest.main()


class ABubbleHidesWhatIsBehindIt(unittest.TestCase):
    """At alpha 0.96 a gridline showed through a bubble as a bar across its
    number ("the '$4.4' ... has a horizontal stroke through it")."""

    def test_the_bubble_is_opaque(self):
        import re
        src = (ROOT / "data_learning" / "charts.py").read_text()
        body = src[src.index("def _story_bubbles("):]
        body = body[:body.index("\ndef ", 10)]
        alphas = re.findall(r"Circle\([^)]*\)[^)]*?alpha=([0-9.]+)", body, re.S)
        self.assertTrue(alphas)
        self.assertTrue(all(float(a) == 1.0 for a in alphas), alphas)
