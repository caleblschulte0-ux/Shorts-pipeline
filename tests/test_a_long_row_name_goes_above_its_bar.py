"""A ROW NAME TOO LONG FOR THE GUTTER GOES ABOVE ITS BAR.

The pictorial race right-aligned every row name against the bar start, in a
gutter a fifth of the card wide. A long name ran off the left edge of the
frame: "the left edge clips the bar label ('ed one at least once') in every
hook and seg0 frame" (teen-ai-companion-boom, 2026-09-22, runs 461 and 463).
Measured on the rendered frame: no ink in the leftmost columns, and a short
name still sits in the gutter exactly as before.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import numpy as np                                        # noqa: E402
from PIL import Image                                     # noqa: E402

from data_learning import charts                          # noqa: E402
from data_learning.insights import Insight                # noqa: E402
from data_learning.sources.base import DataPoint, Source  # noqa: E402

SRC = Source(name="X", publisher="Y", url="https://x", access_date="2026-09-23")


def _frame(pairs):
    ins = Insight(kind="pictorial_race", topic="how many teens use an AI companion",
                  main_insight="m",
                  items=[DataPoint(label=a, value=float(b)) for a, b in pairs],
                  source=SRC, unit="percent", highlight_label=pairs[0][0])
    out = Path(tempfile.mkdtemp())
    charts.render_story_build(ins, out, "r", frames=4, full_by=1.0)
    f = sorted(out.glob("r*.png"))[-1]
    return np.asarray(Image.open(f).convert("RGBA"))[..., 3] > 8


class ALongNameStaysOnScreen(unittest.TestCase):
    def test_no_ink_at_the_left_edge(self):
        a = _frame([("Have used one at least once", 72),
                    ("Use one regularly (few times/month+)", 52),
                    ("Shared personal info with an AI companion", 24)])
        self.assertEqual(int(a[:, :6].sum()), 0, "a row name runs off the left edge")

    def test_a_short_name_still_sits_in_the_gutter(self):
        a = _frame([("Japan", 72), ("Chile", 52), ("Peru", 24)])
        w = a.shape[1]
        # ink left of the bars (the gutter, 0.05..0.23 of the width)
        self.assertGreater(int(a[:, int(w * 0.05):int(w * 0.23)].sum()), 0)


if __name__ == "__main__":
    unittest.main()
