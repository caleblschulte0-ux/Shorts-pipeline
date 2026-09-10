"""Insight selection.

Given a :class:`Dataset` and a requested insight type, build a structured
:class:`Insight` — the bounded, fact-checked unit the packager turns into a
video. Numbers come *only* from source values and whitelisted transforms,
so every claim is traceable (the QA layer enforces this).

Insight strength order (when "auto"): outlier > comparison > rank > trend.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import transforms as T
from .sources.base import DataPoint, Dataset, Source


@dataclass
class Fact:
    """One traceable claim: a value + how it was derived."""

    fact_id: str
    claim: str
    value: float
    unit: str
    calculation: str | None = None   # e.g. "difference_from_baseline(2.2, 4.3)"


@dataclass
class Insight:
    kind: str                        # rank | comparison | trend | outlier
    topic: str
    main_insight: str
    items: list[DataPoint]           # ordered strongest-first
    source: Source
    unit: str
    facts: list[Fact] = field(default_factory=list)
    baseline: DataPoint | None = None
    highlight_label: str | None = None  # which item to color as the star


def _fmt(v: float, unit: str) -> str:
    """One-decimal for rates/per-game, integer for counts, keep sign sense."""
    if unit in ("percent", "%", "rate"):
        return f"{v:.1f}"
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    if float(v).is_integer():
        return f"{v:.0f}"
    return f"{v:.1f}"


def build(dataset: Dataset, insight_type: str = "auto",
          baseline: dict | None = None,
          ascending: bool = False) -> Insight:
    """Construct the strongest insight of the requested type.

    ``ascending`` flips rank semantics (lowest = best), e.g. unemployment.
    ``baseline`` is an optional {label, value} comparison anchor.
    """
    pts = list(dataset.points)
    base_pt = None
    if baseline:
        base_pt = DataPoint(label=baseline["label"], value=float(baseline["value"]),
                            unit=dataset.unit)

    if insight_type == "auto":
        insight_type = _auto_pick(pts, dataset)

    if insight_type == "trend":
        return _trend(dataset, pts)
    if insight_type == "share":
        return _share(dataset, pts)
    if insight_type == "comparison":
        return _comparison(dataset, pts, base_pt)
    if insight_type == "outlier":
        return _outlier(dataset, pts, base_pt, ascending)
    return _rank(dataset, pts, base_pt, ascending)


def _auto_pick(pts: list[DataPoint], ds: Dataset) -> str:
    if pts and pts[0].period:          # has time keys -> trend
        return "trend"
    # THE LABEL IS THE PERIOD WHEN IT IS A YEAR.
    #
    # `draw_timeline` learned this on 2026-09-07 and said why in its own
    # comment: requiring a separate `period` field is an accident of the data
    # shape, and the cost is the whole point of the picture. The ROUTER never
    # learned it, so a year series with no `period` falls past this test and
    # lands somewhere that is not a time series at all:
    #
    #   3 points  -> "comparison", and `_comparison` keeps only the first and
    #                last of the sorted list. `self-checkout-cashier-jobs`
    #                (2000: 6%, 2012: 33%, 2023: 92%) lost 2023 — the year the
    #                narration is about — and the reviewer read the result off
    #                the screen: "bars labeled '2000 VS 2012' with 33% on the
    #                right ... directly contradicting the narration 'was over
    #                92%' printed on the same frame" (2026-09-09).
    #   4+ points -> "rank", which makes YEARS COMPETITORS. That is the
    #                "2019 TOPS THE LIST" failure `_superlative` in charts.py
    #                already documents; the subtitle was fixed there, the
    #                routing that caused it was not.
    #
    # 20 of the 1,115 configured datasets are in this shape — 7 losing their
    # middle, 13 ranked as if the years were rivals.
    #
    # Two dated points stay a COMPARISON on purpose: a before-and-after is
    # exactly what `_story_versus` draws well, and `_comparison` orders that
    # pair chronologically.
    #
    # And DATED IS NOT ENOUGH — the series has to be IN TIME ORDER. A ranking
    # whose items happen to be years is stored in VALUE order, and there is
    # one on disk: `wildfire_worst_years` reads 2015, 2020, 2017, 2006, 2012.
    # Those years are the competitors, which is the one case where the thing
    # `charts._superlative` warns about ("years are not competitors") is
    # actually true. Requiring monotonic time separates the two without
    # asking anybody to label their data differently.
    _ys = [_leading_year(p.label) for p in pts]
    if len(pts) >= 3 and all(y is not None for y in _ys) \
            and (_ys == sorted(_ys) or _ys == sorted(_ys, reverse=True)):
        return "trend"
    if len(pts) >= 4:
        vals = [p.value for p in pts]
        top = T.sort_desc(pts)[0]
        if abs(T.z_score(top.value, vals)) >= 1.8:
            return "outlier"
        return "rank"
    return "comparison"


def _rank(ds: Dataset, pts: list[DataPoint], base: DataPoint | None,
          ascending: bool) -> Insight:
    ordered = T.rank(pts, ascending=ascending)
    # Keep up to 5: the vertical photo-ranking rows look best with 4-5 real
    # things, and authored scenes reference item:3/item:4. Renderers that want
    # fewer slice their own cap.
    top = ordered[:5]
    star = top[0]
    facts = [
        Fact(f"F{i+1}", f"{p.label} {_fmt(p.value, ds.unit)} {ds.unit}",
             p.value, ds.unit)
        for i, p in enumerate(top)
    ]
    sup = "lowest" if ascending else "highest"
    main = (f"The {sup} {ds.title.lower()} is {star.label} at "
            f"{_fmt(star.value, ds.unit)} {ds.unit}.")
    if base:
        diff = T.difference_from_baseline(star.value, base.value)
        facts.append(Fact(f"F{len(facts)+1}",
                          f"{base.label} baseline {_fmt(base.value, ds.unit)} {ds.unit}",
                          base.value, ds.unit,
                          calculation=f"difference_from_baseline({star.value}, {base.value})={diff:.1f}"))
    return Insight("rank", ds.title, main, top, ds.source, ds.unit,
                   facts, base, star.label)


def _share(ds: Dataset, pts: list[DataPoint]) -> Insight:
    """Composition: parts of a whole, rendered as a donut/pie."""
    ordered = T.sort_desc(pts)
    star = ordered[0]
    facts = [
        Fact(f"F{i+1}", f"{p.label} {_fmt(p.value, ds.unit)} {ds.unit}",
             p.value, ds.unit)
        for i, p in enumerate(ordered[:4])
    ]
    main = (f"{star.label} is the largest share of {ds.title.lower()} at "
            f"{_fmt(star.value, ds.unit)} {ds.unit}.")
    return Insight("share", ds.title, main, ordered, ds.source, ds.unit,
                   facts, None, star.label)


def _leading_year(label) -> int | None:
    """The calendar year a label starts with, or None.

    Tolerant of what the label says after it — "1963 (all-time low)" and
    "2019 (two-dose era)" are both dates, and a strict `len <= 7` test reads
    them as names.
    """
    t = str(label or "").strip()
    if len(t) < 4 or not t[:4].isdigit():
        return None
    y = int(t[:4])
    return y if 1500 <= y <= 2200 else None


def _comparison(ds: Dataset, pts: list[DataPoint], base: DataPoint | None) -> Insight:
    ordered = T.sort_desc(pts)
    hi, lo = ordered[0], ordered[-1]
    items = [hi, lo]
    # BEFORE AND AFTER ARE NOT BIG AND SMALL.
    #
    # Two PLACES may be ordered by size; two DATES may not. `_story_versus`
    # draws `items[0]` on the left, so sorting a then-and-now by magnitude puts
    # the later year first and the chart runs backwards in time.
    #
    # `bald-eagle-population-rebound`, 2026-09-09, on the closing beat:
    #
    #     "the closing chart runs 2020 -> 1963 left-to-right, so the line
    #      falls steeply as the narration says 'one of the biggest wildlife
    #      comebacks' — the picture contradicts the words at the punchline"
    #
    # 417 pairs in 1963 and 71,467 in 2020 is the biggest recovery story the
    # channel has, and it was drawn as a collapse.
    _ya, _yb = _leading_year(hi.label), _leading_year(lo.label)
    if _ya is not None and _yb is not None and _ya != _yb:
        items = [hi, lo] if _ya < _yb else [lo, hi]
    facts = [
        Fact("F1", f"{hi.label} {_fmt(hi.value, ds.unit)} {ds.unit}", hi.value, ds.unit),
        Fact("F2", f"{lo.label} {_fmt(lo.value, ds.unit)} {ds.unit}", lo.value, ds.unit),
    ]
    gap = T.absolute_change(lo.value, hi.value)
    facts.append(Fact("F3", f"gap {_fmt(gap, ds.unit)} {ds.unit}", gap, ds.unit,
                      calculation=f"absolute_change({lo.value}, {hi.value})={gap:.1f}"))
    main = (f"{hi.label} leads {ds.title.lower()} at {_fmt(hi.value, ds.unit)} "
            f"{ds.unit}, far above {lo.label} at {_fmt(lo.value, ds.unit)}.")
    return Insight("comparison", ds.title, main, items, ds.source, ds.unit,
                   facts, base, hi.label)


def _outlier(ds: Dataset, pts: list[DataPoint], base: DataPoint | None,
             ascending: bool) -> Insight:
    ordered = T.rank(pts, ascending=ascending)
    star = ordered[0]
    rest = [p.value for p in ordered[1:]]
    pack = sum(rest) / len(rest) if rest else star.value
    z = T.z_score(star.value, [p.value for p in pts])
    items = ordered[:4]
    facts = [
        Fact("F1", f"{star.label} {_fmt(star.value, ds.unit)} {ds.unit}",
             star.value, ds.unit),
        Fact("F2", f"pack average {_fmt(pack, ds.unit)} {ds.unit}", pack, ds.unit,
             calculation="mean(rest)"),
        Fact("F3", f"z-score {z:.1f}", z, "sd", calculation="z_score(star, all)"),
    ]
    main = (f"{star.label} is a true outlier in {ds.title.lower()} at "
            f"{_fmt(star.value, ds.unit)} {ds.unit}, far from the pack.")
    return Insight("outlier", ds.title, main, items, ds.source, ds.unit,
                   facts, base, star.label)


def _trend(ds: Dataset, pts: list[DataPoint]) -> Insight:
    # TIME RUNS LEFT TO RIGHT. `_trend` kept the input order, so a series
    # stored newest-first drew the line backwards — and a rise then reads as a
    # collapse under narration about a rise. That is the bald-eagle punchline
    # (`insights._comparison`) one shape up, and the fix is the same: when
    # every label carries a year, the order is the CALENDAR's, not the file's.
    _ys = [_leading_year(p.label) for p in pts]
    if len(pts) >= 2 and all(y is not None for y in _ys):
        pts = [p for _y, p in sorted(zip(_ys, pts), key=lambda t: t[0])]
    first, last = pts[0], pts[-1]
    delta = T.absolute_change(first.value, last.value)
    try:
        pct = T.pct_change(first.value, last.value)
        pct_txt = f"{pct:+.0f} percent"
        pct_calc = f"pct_change({first.value}, {last.value})={pct:.1f}"
    except ZeroDivisionError:
        pct_txt = "from near zero"
        pct_calc = None
    facts = [
        Fact("F1", f"{first.label} {_fmt(first.value, ds.unit)} {ds.unit}",
             first.value, ds.unit),
        Fact("F2", f"{last.label} {_fmt(last.value, ds.unit)} {ds.unit}",
             last.value, ds.unit),
        Fact("F3", f"change {_fmt(delta, ds.unit)} {ds.unit} ({pct_txt})",
             delta, ds.unit, calculation=pct_calc),
    ]
    direction = "climbed" if delta > 0 else "fell"
    main = (f"{ds.title} {direction} from {_fmt(first.value, ds.unit)} in "
            f"{first.label} to {_fmt(last.value, ds.unit)} in {last.label}.")
    return Insight("trend", ds.title, main, pts, ds.source, ds.unit,
                   facts, None, last.label)
