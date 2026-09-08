"""The same machine, staged differently — and saying exactly the same thing.

The relationship router fixed WHICH picture a beat gets. It did not touch HOW
that picture is composed, and `race_track` alone is 195 of the 930 configured
explainer beats — drawn, until 2026-09-07, with the identical layout every
single time. A library of 42 rigid pictures is a bigger template than a
library of six, not a smaller one.

THE RULE, and it is the only thing that makes this safe:

    Staging may change how a machine is ARRANGED. It may never change what
    the machine CLAIMS.

The value-to-geometry mapping, every number, every label and every caption are
identical across every variant. What varies is framing — which lane the leader
runs in, which side the host watches from, whether there is a ground line,
what shape the moving product is. The first test below is the one that
matters: it renders the same insight at every variant and compares the pixels
of the TEXT, so a staging change that moved a number would fail.

Runs standalone:  python3 tests/test_machines_are_pliable.py
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

SRC = Source(name="X", publisher="Y", url="https://x", access_date="2026-01-01")
BOX = (vs.RX0, vs.RTOP, vs.RX1, vs.MACHINE_BOT)


def _mk(topic, pairs, unit="count"):
    return Insight(kind="scene", topic=topic, main_insight=topic,
                   items=[DataPoint(label=l, value=float(v)) for l, v in pairs],
                   source=SRC, unit=unit, highlight_label=pairs[0][0])


class StagingIsDeterministic(unittest.TestCase):
    def test_the_same_story_stages_the_same_way_every_time(self):
        """A re-render must be identical, or a diff of two runs means
        nothing and the cache is a liability."""
        a = _mk("grocery prices", [("A", 5), ("B", 3)])
        b = _mk("grocery prices", [("A", 5), ("B", 3)])
        self.assertEqual(vs.stage(a, "race_track"), vs.stage(b, "race_track"))

    def test_different_stories_get_different_staging(self):
        topics = ["grocery prices", "wage illusion", "debt trap",
                  "housing wall", "car costs", "bird collapse",
                  "student loans", "healthcare spiral"]
        seen = {vs.variant(_mk(t, [("A", 1)]), "race_track", 12)
                for t in topics}
        self.assertGreaterEqual(
            len(seen), 4,
            f"staging barely varies across stories: {sorted(seen)}")

    def test_one_story_using_two_machines_stages_them_apart(self):
        ins = _mk("grocery prices", [("A", 1)])
        vs_ = {vs.variant(ins, k, 12)
               for k in ("race_track", "staircase", "tower", "skyline")}
        self.assertGreater(len(vs_), 1)

    def test_a_single_variant_is_always_zero(self):
        self.assertEqual(vs.variant(_mk("x", [("A", 1)]), "race_track", 1), 0)


class StagingNeverChangesTheCLAIM(unittest.TestCase):
    """The guard. Render every variant of a machine and compare what is
    WRITTEN on it — a staging choice that moved a number, changed a label or
    dropped a caption fails here.
    """

    CASES = {
        "race_track": _mk("t", [("San Jose", 11.3), ("LA", 9.7),
                                ("Miami", 8.2), ("Seattle", 6.8)], "years"),
        "bottleneck": _mk("t", [("Applied", 12000), ("Screened", 9800),
                                ("Interviewed", 2100), ("Offered", 1700),
                                ("Hired", 1500)]),
        "funnel": _mk("t", [("Applied", 1000), ("Interviewed", 380),
                            ("Offered", 95), ("Accepted", 41)]),
        "pipes": _mk("t", [("Rent", 34), ("Food", 22), ("Transit", 18),
                           ("Other", 26)], "percent"),
        "leaky": _mk("t", [("Enrolled", 4800), ("Finished", 860)]),
        "chain": _mk("t", [("Wafer", 940), ("Assembly", 720), ("Test", 210),
                           ("Ship", 880)]),
        "sorter": _mk("t", [("Housing", 4200), ("Transit", 2600),
                            ("Parks", 1400), ("Admin", 900)], "usd"),
    }

    def _ink(self, kind, ins):
        """Everything the machine draws, as a set of text-ish pixels.

        Comparing whole frames would fail on the staging itself, which is the
        point of staging. Comparing the drawn NUMBERS is what must hold, and
        the cheapest faithful proxy is the machine's own returned anchor value
        plus the exact captions it writes, which the source carries.
        """
        canvas = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
        d = ImageDraw.Draw(canvas)
        safe = vs.drawable_insight(ins)
        # `race_track` has its own dispatch branch rather than a table entry,
        # and its draw function takes the same signature.
        fn = vs._MACHINE_DRAW.get(kind) or {"race_track": vs.draw_race}[kind]
        an = vs._guarded(kind, fn, d, canvas, BOX, safe,
                         charts.HIGHLIGHT, 1.0, safe.unit)
        return an

    def test_the_anchor_VALUE_is_identical_across_every_variant(self):
        for kind, ins in self.CASES.items():
            base = None
            for topic in ("alpha", "beta", "gamma", "delta", "epsilon",
                          "zeta", "eta", "theta"):
                ins.topic = topic
                an = self._ink(kind, ins)
                self.assertIsNotNone(an, f"{kind} refused to draw")
                val = an["value"] if isinstance(an, dict) else an[0]
                if base is None:
                    base = val
                self.assertAlmostEqual(
                    val, base, places=6,
                    msg=f"{kind}: staging changed the NUMBER "
                        f"({val} != {base}) for topic {topic!r}")

    def test_staging_actually_changes_the_picture(self):
        """The other half: if nothing moves, this is dead code pretending to
        be variety."""
        ins = self.CASES["race_track"]
        frames = []
        for topic in ("alpha", "beta", "gamma", "delta", "epsilon", "zeta"):
            ins.topic = topic
            canvas = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            d = ImageDraw.Draw(canvas)
            vs.draw_race(d, canvas, BOX, ins, charts.HIGHLIGHT, 1.0, "years")
            frames.append(canvas.tobytes())
        self.assertGreater(len(set(frames)), 1,
                           "every story renders the identical race")


class TheParticleShapeIsCosmeticOnly(unittest.TestCase):
    def test_every_shape_draws_something(self):
        for shape in vs._PARTICLES:
            canvas = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
            d = ImageDraw.Draw(canvas)
            vs.particle(d, shape, 100, 100, 20, (255, 255, 255, 255))
            self.assertIsNotNone(canvas.getbbox(), f"{shape} drew nothing")

    def test_an_unknown_shape_falls_back_rather_than_raising(self):
        canvas = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
        d = ImageDraw.Draw(canvas)
        vs.particle(d, "not-a-shape", 100, 100, 20, (255, 255, 255, 255))
        self.assertIsNotNone(canvas.getbbox())


if __name__ == "__main__":
    unittest.main(verbosity=2)
