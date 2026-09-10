"""THE CHART SHOWED 2000 VS 2012 WHILE THE VOICE SAID 92% BY 2023.

    "seg1:mid / seg1:end: bars labeled '2000 VS 2012' with 33% on the right
     and no value on the 2000 bar, directly contradicting the narration 'was
     over 92%' printed on the same frame"
                                 self-checkout-cashier-jobs, 2026-09-09

The dataset is three years — 2000: 6%, 2012: 33%, 2023: 92% — and the beat is
about the last of them. The picture dropped it.

`_auto_pick` recognises a time series only by an explicit `period` field:

    if pts and pts[0].period:
        return "trend"

`draw_timeline` learned better on 2026-09-07 and said why in its own comment —
"requiring a separate `period` field is an accident of the data shape, and the
cost of it is the whole point of this machine". The ROUTER never learned it,
so a year series with no `period` falls past that test and lands somewhere
that is not a time series at all:

    3 points  -> "comparison", and `_comparison` keeps only the FIRST and LAST
                 of the sorted list. 2023 is thrown away.
    4+ points -> "rank", which makes YEARS COMPETITORS — the "2019 TOPS THE
                 LIST" failure `charts._superlative` already documents. The
                 subtitle was fixed there; the routing that caused it was not.

20 of the 1,115 configured datasets are in this shape: 7 losing their middle,
13 ranked as if the years were rivals.

Two dated points stay a comparison on purpose — a before-and-after is exactly
what `_story_versus` draws well, and `_comparison` orders that pair
chronologically.

Runs standalone:  python3 tests/test_a_year_series_is_a_trend.py
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from data_learning import insights                              # noqa: E402
from data_learning.insights import _auto_pick, _leading_year    # noqa: E402
from data_learning.sources.base import DataPoint, Dataset, Source  # noqa: E402

SRC = Source(name="NRF", publisher="National Retail Federation",
             url="https://x", access_date="2026-09-08")

SELF_CHECKOUT = [("2000", 6.0), ("2012", 33.0), ("2023", 92.0)]


class _DS:
    title = "t"
    unit = "percent"


def _pts(pairs):
    return [DataPoint(label=a, value=float(b)) for a, b in pairs]


def _dataset(pairs, unit="percent"):
    return Dataset(key="k", title="Self-checkout adoption", unit=unit,
                   geography="US", time_coverage="", points=_pts(pairs),
                   source=SRC, notes="")


class TheNamedBeat(unittest.TestCase):
    def test_three_years_route_to_a_trend(self):
        self.assertEqual(_auto_pick(_pts(SELF_CHECKOUT), _DS()), "trend")

    def test_the_year_the_narration_is_about_survives(self):
        ins = insights.build(_dataset(SELF_CHECKOUT))
        self.assertEqual([p.label for p in ins.items], ["2000", "2012", "2023"])
        self.assertIn(92.0, [p.value for p in ins.items])

    def test_and_it_keeps_them_in_time_order(self):
        ins = insights.build(_dataset(list(reversed(SELF_CHECKOUT))))
        years = [_leading_year(p.label) for p in ins.items]
        self.assertEqual(years, sorted(years), years)


class YearsAreNotCompetitors(unittest.TestCase):
    """4+ dated points used to become a RANK, which is the "2019 TOPS THE
    LIST" failure one level up from the subtitle that was blamed for it."""

    def test_eight_years_route_to_a_trend(self):
        pairs = [(str(1960 + 10 * k), 300.0 + k * 8) for k in range(8)]
        self.assertEqual(_auto_pick(_pts(pairs), _DS()), "trend")

    def test_decade_labels_count_as_dates(self):
        pairs = [("1980s", 16.0), ("1990s", 10.0), ("2000s", 7.0),
                 ("2010s", 10.0)]
        self.assertEqual(_auto_pick(_pts(pairs), _DS()), "trend")


class ARankingOfYEARSIsStillARanking(unittest.TestCase):
    """The one case where "years are not competitors" is false. A ranking
    whose items happen to be years is stored in VALUE order, and there is one
    on disk: `wildfire_worst_years` reads 2015, 2020, 2017, 2006, 2012.
    Requiring monotonic time separates the two shapes without asking anybody
    to relabel their data."""

    WORST = [("2015", 10.1), ("2020", 10.1), ("2017", 10.0),
             ("2006", 9.9), ("2012", 9.3)]

    def test_years_out_of_time_order_are_not_a_trend(self):
        self.assertNotEqual(_auto_pick(_pts(self.WORST), _DS()), "trend")

    def test_the_real_dataset_on_disk_is_not_a_trend(self):
        f = _REPO / "data_learning" / "data" / "wildfire_worst_years.json"
        if not f.exists():
            self.skipTest("dataset not in this checkout")
        d = json.loads(f.read_text())
        pts = _pts([(p["label"], p["value"]) for p in d["points"]
                    if p.get("value") is not None])
        self.assertNotEqual(_auto_pick(pts, _DS()), "trend")


class TimeRunsLeftToRightInATrendToo(unittest.TestCase):
    """`_trend` kept the INPUT order, so a series stored newest-first drew the
    line backwards and a rise read as a collapse — the bald-eagle punchline
    (`_comparison`) one shape up."""

    def test_a_newest_first_series_is_reordered(self):
        ins = insights.build(_dataset(list(reversed(SELF_CHECKOUT))))
        self.assertEqual([p.label for p in ins.items],
                         ["2000", "2012", "2023"])

    def test_the_claim_follows_the_reordering(self):
        """`main_insight` names first and last; reordering must not leave it
        describing a fall."""
        ins = insights.build(_dataset(list(reversed(SELF_CHECKOUT))))
        self.assertIn("climbed", ins.main_insight)
        self.assertIn("2023", ins.main_insight)


class WhatMustNOTChange(unittest.TestCase):
    def test_two_dates_stay_a_comparison(self):
        self.assertEqual(
            _auto_pick(_pts([("1963", 417.0), ("2020", 71467.0)]), _DS()),
            "comparison")

    def test_places_are_still_ranked(self):
        pairs = [("San Jose", 11.3), ("Los Angeles", 9.7), ("Miami", 8.2),
                 ("Seattle", 6.8), ("Denver", 5.4)]
        self.assertIn(_auto_pick(_pts(pairs), _DS()), ("rank", "outlier"))

    def test_three_places_stay_a_comparison(self):
        self.assertEqual(
            _auto_pick(_pts([("A", 5.0), ("B", 3.0), ("C", 1.0)]), _DS()),
            "comparison")

    def test_an_explicit_period_still_wins(self):
        pts = _pts([("Alpha", 1.0), ("Beta", 2.0), ("Gamma", 3.0)])
        for i, p in enumerate(pts):
            p.period = str(2000 + i)
        self.assertEqual(_auto_pick(pts, _DS()), "trend")

    def test_a_mixed_bag_is_not_a_trend(self):
        """One year among names is a coincidence, not a time axis."""
        pairs = [("2019", 5.0), ("Norway", 3.0), ("Chile", 1.0)]
        self.assertNotEqual(_auto_pick(_pts(pairs), _DS()), "trend")


class NoDatedSeriesOnDiskLosesAPoint(unittest.TestCase):
    """The general form, over the real catalogue: if every label is a date and
    there are three or more of them, the picture gets all of them."""

    DATA = _REPO / "data_learning" / "data"

    def test_every_all_dated_dataset_keeps_every_point(self):
        bad = {}
        for f in sorted(self.DATA.glob("*.json")):
            try:
                d = json.loads(f.read_text())
            except Exception:  # noqa: BLE001
                continue
            pts = [p for p in (d.get("points") or []) if isinstance(p, dict)]
            vals = [p for p in pts if p.get("value") is not None]
            if len(vals) < 3:
                continue
            if not all(_leading_year(p.get("label")) is not None for p in vals):
                continue
            ins = insights.build(_dataset(
                [(p["label"], p["value"]) for p in vals],
                unit=d.get("unit", "")))
            if len(ins.items) != len(vals):
                bad[f.name] = f"{len(vals)} -> {len(ins.items)}"
        self.assertEqual(bad, {}, f"dated series losing points: {bad}")


if __name__ == "__main__":
    unittest.main()
