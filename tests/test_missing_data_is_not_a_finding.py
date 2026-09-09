"""ALGERIA DOES NOT RUN ON 0% FOSSIL FUELS.

On 2026-09-09 this channel authored, rendered and TITLED a video
`oil-rich-algeria-runs-on-0-fossil-fuels-at-home`. Its hook: *"You'd bet an
oil giant burns the most fossil fuel — Algeria's share of it is zero percent."*
The dataset under it was a "Top 5 countries" ranking that read:

    Kosovo 86.1, Albania 0.0, Algeria 0.0, Angola 0.0, Antigua 0.0

Those are the first four countries **alphabetically**, which is what a tie
among ABSENT values sorts to. The World Bank has no 2024 row for any of them.
The showrunner caught it on the screen — "Albania, Algeria, Angola and Antigua
all render as '0', presenting missing World Bank rows as a factual zero — the
same frame that carries the closing claim" — but by then the render was spent
and the false claim was the title of the video.

Two things let it through, and both are fixed here.

**The forge HUNTED for it.** `fetch_rank`'s guard refuses a flat ranking:

    if top[0][1] <= 0 or top[0][1] / max(abs(top[-1][1]), 1e-9) < 2.0

The `max(..., 1e-9)` is a divide-by-zero fallback, and it INVERTS the guard it
sits inside. With the tail at 0.0 the ratio comes out at 8.6e10 — so the
flattest possible data scored as the most spectacular finding in the
catalogue, and the forge prefers spread. It did not merely allow this shape;
it went looking for it, and picked the same story twice in one evening.

**And the gate never looked at the numbers.** `data_provenance` checks that a
source is real, dated and official. This dataset had a perfect World Bank
citation. Nothing anywhere read the values.

The forge fix stops one producer. `data_is_a_finding` is the half that holds,
because the forge is not the only producer — a ChatGPT takeover authors
datasets, and 1,116 of these files already sit on disk.

Runs standalone:  python3 tests/test_missing_data_is_not_a_finding.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_spec = importlib.util.spec_from_file_location(
    "editorial_gate", _REPO / "scripts" / "editorial_gate.py")
eg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eg)


_TMP = Path(tempfile.mkdtemp())
eg.DATA_DIR = _TMP          # datasets always resolve inside DATA_DIR


def _sc(points, itype="rank", **extra):
    """A one-segment script whose dataset lives in a temp DATA_DIR."""
    d = {"key": "t", "title": "T", "unit": "% of total",
         "insight_type": itype, "points": points,
         "source": {"name": "n", "publisher": "World Bank",
                    "url": "https://x", "officiality": "official",
                    "access_date": "2026-09-09"}}
    d.update(extra)
    (_TMP / "t.json").write_text(json.dumps(d))
    return {"segments": [{"key": "t"}]}


class TheVerdictThatNamedIt(unittest.TestCase):
    def test_the_algeria_ranking_is_refused(self):
        sc = _sc([{"label": "Kosovo", "value": 86.1},
                  {"label": "Albania", "value": 0.0},
                  {"label": "Algeria", "value": 0.0},
                  {"label": "Angola", "value": 0.0},
                  {"label": "Antigua and Barbuda", "value": 0.0}])
        v = eg.data_is_a_finding(sc)
        self.assertFalse(v["ok"])
        self.assertIn("Algeria", v["reasons"][0])

    def test_it_reaches_the_pre_render_verdict(self):
        """A check nobody calls is not a check."""
        sc = _sc([{"label": "Kosovo", "value": 86.1},
                  {"label": "Algeria", "value": 0.0}])
        sc.update(title="Oil-Rich Algeria Runs On 0% Fossil Fuels At Home",
                  hook="Algeria's share of it is zero percent.")
        v = eg.pre_render_verdict(sc, use_llm=False)
        self.assertFalse(v["ok"])
        self.assertFalse(v["data_ok"])
        self.assertTrue(any("missing data, not a result" in r
                            for r in v["reasons"]), v["reasons"])

    def test_a_ranking_of_nothing_but_zeros_is_refused_too(self):
        sc = _sc([{"label": "A", "value": 0.0}, {"label": "B", "value": 0.0}])
        v = eg.data_is_a_finding(sc)
        self.assertFalse(v["ok"])
        self.assertIn("no finding here", v["reasons"][0])


class ItIsDeliberatelyNARROW(unittest.TestCase):
    """A rule that refuses honest zeros would cost more videos than it saves.
    It fires only on a RANKING, because a ranking is ordered by value — a 0
    inside the top five means fewer than five entities have one."""

    def test_a_real_ranking_passes(self):
        sc = _sc([{"label": "Kosovo", "value": 86.1},
                  {"label": "Poland", "value": 79.4},
                  {"label": "India", "value": 73.2}])
        self.assertTrue(eg.data_is_a_finding(sc)["ok"])

    def test_a_TREND_may_reach_zero(self):
        """"Moon landings since 1972: zero" is a real beat this channel has
        run. Nothing here touches it."""
        sc = _sc([{"label": "1969-1972", "value": 12.0},
                  {"label": "1973-2024", "value": 0.0}], itype="trend")
        self.assertTrue(eg.data_is_a_finding(sc)["ok"])

    def test_a_COMPARISON_may_reach_zero(self):
        sc = _sc([{"label": "Before", "value": 4000.0},
                  {"label": "After", "value": 0.0}], itype="comparison")
        self.assertTrue(eg.data_is_a_finding(sc)["ok"])

    def test_a_missing_or_unreadable_dataset_is_not_accused(self):
        """`data_provenance` reports that; two rules blaming one fault reads
        as two faults."""
        self.assertTrue(
            eg.data_is_a_finding({"segments": [{"key": "nope"}]})["ok"])
        self.assertTrue(eg.data_is_a_finding({})["ok"])

    def test_a_ranking_with_a_null_is_not_treated_as_a_zero(self):
        """A null is honest absence and is dropped before the check; only an
        explicit 0.0 is the lie."""
        sc = _sc([{"label": "Kosovo", "value": 86.1},
                  {"label": "Nowhere", "value": None},
                  {"label": "Poland", "value": 40.0}])
        self.assertTrue(eg.data_is_a_finding(sc)["ok"])


class TheForgeNoLongerHUNTSForIt(unittest.TestCase):
    def test_the_spread_guard_is_not_inverted_by_its_own_fallback(self):
        import ast
        import inspect
        import importlib.util as _iu
        sp = _iu.spec_from_file_location("story_forge",
                                         _REPO / "scripts" / "story_forge.py")
        # parse rather than import: story_forge pulls the network layer in
        src = (_REPO / "scripts" / "story_forge.py").read_text()
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "fetch_rank")
        for node in ast.walk(fn):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                node.value = ""
        code = ast.unparse(fn)
        self.assertNotIn("1e-09", code.replace("1e-9", "1e-09"),
                         "the divide-by-zero fallback still stands in for a "
                         "spread")
        self.assertIn("tail <= 0", code)

    DATA = _REPO / "data_learning" / "data"

    def test_no_ranking_on_disk_has_a_zero_in_its_top_n(self):
        """The one that did is deleted; this stops another arriving."""
        bad = {}
        for f in sorted(self.DATA.glob("*.json")):
            try:
                d = json.loads(f.read_text())
            except Exception:  # noqa: BLE001
                continue
            if str(d.get("insight_type", "")).lower() != "rank":
                continue
            # Only datasets that could actually publish. An `illustrative`
            # file is already refused by `data_provenance`, and two rules
            # blaming one fault reads as two faults.
            if str((d.get("source") or {}).get("officiality", "")).lower() \
                    not in eg.REAL_OFFICIALITY:
                continue
            vals = [x.get("value") for x in (d.get("points") or [])
                    if isinstance(x, dict)]
            vals = [float(v) for v in vals if v is not None]
            if vals and max(vals) != 0.0 and any(v == 0.0 for v in vals):
                bad[f.name] = vals
        self.assertEqual(bad, {}, f"rankings with an absent tail: {bad}")

    def test_the_fabricated_story_is_out_of_the_queue(self):
        cfg = json.loads(
            (_REPO / "data_learning" / "niche.config.json").read_text())
        slugs = [s.get("slug") for s in cfg.get("stories", [])]
        self.assertNotIn("oil-rich-algeria-runs-on-0-fossil-fuels-at-home",
                         slugs)


if __name__ == "__main__":
    unittest.main()
