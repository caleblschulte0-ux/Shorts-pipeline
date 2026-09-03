"""The two block reasons left after the anchoring fix, pinned.

2026-08-24 morning: the anchoring/clamp/geo batch shipped, the proving
render scored 95 — and the day's four production stories still blocked at
26-52. The verdicts named two causes the batch had not touched:

  "mascot is a sticker parked on top of the bars"  — the claim-driven act
      selector could hand a BAKED chart anchor a STANDING act (align
      (0.5, 0.04): feet planted on the datum, hovering over the chart).
      Every praised bit was a GRIP act (arms on the tip, hauling the line).

  "three near-identical chart layouts"             — kinds flagged time/
      place/repeatable were exempt from the no-repeat rule, so a story of
      three *_trend segments rendered the identical line card three times.

    python -m unittest tests.test_grip_and_variety -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data_learning import mascot_director as md      # noqa: E402
from data_learning import viz_director as vd         # noqa: E402
from data_learning.insights import (Insight, DataPoint,   # noqa: E402
                                    Source)

SRC = Source(name="WDI", publisher="World Bank", url="u")

# Claims chosen to tempt every STANDING family the selector knows:
# surprise/reveal -> discover, scale -> overwhelmed/compare_scales,
# share -> transform_reveal/stack_tiles, volatility -> balance_beam.
TEMPTING_CLAIMS = [
    "a surprising reveal: the outlier nobody expected",
    "the sheer scale is overwhelming — it dominates everything",
    "the share transformed — reframed, it tells another story",
    "wildly volatile and unstable at a high level",
    "urban growth just hit a 50-year low of 1.36",
    "health spending exceeds $1300 per person",
]


class TestBakedAnchorsGetGripActs(unittest.TestCase):

    def test_every_grip_act_is_real(self):
        for a in md.ANCHOR_GRIP_ACTS:
            self.assertIn(a, md.VERIFIED_PERFORMANCES, a)
            self.assertIn(a, md.ACTION_ALIGN, a)

    def test_no_standing_act_reaches_a_baked_anchor(self):
        """Sweep shapes x tempting claims x seeds: with require_contact the
        selection NEVER leaves the grip set — including the 'surprise'
        claims that used to summon `discover` onto the winning bar."""
        for kind in ("trend", "timeline", "rank", "bars", "pictorial_race",
                     "comparison", "stack", "share"):
            for claim in TEMPTING_CLAIMS:
                for seed in range(4):
                    spec = md.performance_for(kind, claim, "X", seed=seed,
                                              require_contact=True)
                    self.assertIn(spec["action"], md.ANCHOR_GRIP_ACTS,
                                  f"{kind} / {claim!r} -> {spec['action']}")

    def test_without_the_flag_standing_acts_still_exist(self):
        """The standing families are not dead — scene/mechanic beats stage
        their own floor and may use them. Only baked anchors filter."""
        acts = {md.performance_for("trend", c, "X", seed=s)["action"]
                for c in TEMPTING_CLAIMS for s in range(4)}
        self.assertTrue(acts - md.ANCHOR_GRIP_ACTS,
                        "the unfiltered selector never picks a standing act "
                        "— the flag is untestably redundant, check the sets")

    def test_the_three_baked_call_sites_require_contact(self):
        for rel in ("data_learning/charts.py",
                    "data_learning/viz_director.py",
                    "scripts/scene_repair.py"):
            src = (ROOT / rel).read_text()
            self.assertIn("require_contact=True", src, rel)


def _trend_ins(label_stub: str) -> Insight:
    pts = [DataPoint(str(y), float(v), "index", period=str(y))
           for y, v in ((1990, 2.0), (2000, 1.8), (2010, 1.6), (2024, 1.36))]
    return Insight(kind="", topic=label_stub, main_insight=f"{label_stub} fell",
                   items=pts, source=SRC, unit="index")


class TestAStoryIsNotTheSameCardThrice(unittest.TestCase):

    def setUp(self):
        import os
        self._inv = os.environ.get("VIZ_INVENT")
        os.environ["VIZ_INVENT"] = "0"     # deterministic: no LLM invention

    def tearDown(self):
        import os
        if self._inv is None:
            os.environ.pop("VIZ_INVENT", None)
        else:
            os.environ["VIZ_INVENT"] = self._inv

    def test_three_trend_segments_get_three_depictions(self):
        inss = [_trend_ins(s) for s in ("aging", "rural", "urban")]
        vd.assign(inss, seed=0)
        kinds = [i.kind for i in inss]
        self.assertEqual(len(set(kinds)), 3, kinds)

    def test_variety_never_buys_bubbles(self):
        """bubbles is the terminal guarantee, not a variety move — a repeat
        beats a bare dot chart."""
        inss = [_trend_ins(s) for s in ("a", "b", "c")]
        vd.assign(inss, seed=0)
        self.assertNotIn("bubbles", [i.kind for i in inss])

    def test_geo_stories_still_map_every_segment(self):
        """place data always maps (the ruling in _candidates) — variety must
        not break a story whose segments are all geographic."""
        def geo():
            pts = [DataPoint(n, v, "kg") for n, v in
                   (("Slovenia", 3.0), ("Malawi", 2.0), ("Iceland", 1.0))]
            return Insight(kind="", topic="T", main_insight="x leads",
                           items=pts, source=SRC, unit="kg")
        inss = [geo(), geo()]
        vd.assign(inss, seed=0)
        self.assertEqual([i.kind for i in inss], ["geo_world", "geo_world"])

    def test_a_lone_repeat_when_nothing_else_fits_is_still_allowed(self):
        """Four trend segments outrun the three time-shaped kinds — the
        fourth honestly repeats rather than degrading to bubbles."""
        inss = [_trend_ins(s) for s in ("a", "b", "c", "d")]
        vd.assign(inss, seed=0)
        kinds = [i.kind for i in inss]
        self.assertNotIn("bubbles", kinds)
        self.assertGreaterEqual(len(set(kinds)), 3, kinds)


if __name__ == "__main__":
    unittest.main()
