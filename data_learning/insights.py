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
    top = ordered[:3]
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


def _comparison(ds: Dataset, pts: list[DataPoint], base: DataPoint | None) -> Insight:
    ordered = T.sort_desc(pts)
    hi, lo = ordered[0], ordered[-1]
    items = [hi, lo]
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
