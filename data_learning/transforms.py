"""Safe, auditable transforms.

These are the *only* operations the pipeline is allowed to apply to source
numbers — mirroring the ``allowed_transforms`` budget from the prompt spec.
Each is a pure function over :class:`DataPoint` lists so the QA layer can
trace every emitted number back to a source value or a named transform.
"""
from __future__ import annotations

from statistics import mean, pstdev

from .sources.base import DataPoint


def sort_desc(points: list[DataPoint]) -> list[DataPoint]:
    return sorted(points, key=lambda p: p.value, reverse=True)


def sort_asc(points: list[DataPoint]) -> list[DataPoint]:
    return sorted(points, key=lambda p: p.value)


def rank(points: list[DataPoint], *, ascending: bool = False) -> list[DataPoint]:
    """Return points ordered by rank (default best = highest)."""
    return sort_asc(points) if ascending else sort_desc(points)


def pct_change(old: float, new: float) -> float:
    if old == 0:
        raise ZeroDivisionError("pct_change with zero base")
    return (new - old) / abs(old) * 100.0


def absolute_change(old: float, new: float) -> float:
    return new - old


def difference_from_baseline(value: float, baseline: float) -> float:
    """Signed difference of a value from a baseline (same units)."""
    return value - baseline


def ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        raise ZeroDivisionError("ratio with zero denominator")
    return numerator / denominator


def z_score(value: float, population: list[float]) -> float:
    sd = pstdev(population)
    if sd == 0:
        return 0.0
    return (value - mean(population)) / sd


def rolling_average(values: list[float], window: int) -> list[float]:
    if window <= 0:
        raise ValueError("window must be positive")
    out: list[float] = []
    for i in range(len(values)):
        lo = max(0, i - window + 1)
        chunk = values[lo:i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


# Whitelist used by the config validator / QA layer.
ALLOWED = {
    "sort_desc", "sort_asc", "rank", "pct_change", "absolute_change",
    "difference_from_baseline", "ratio", "z_score", "rolling_average",
    "per_capita",  # reserved; computed as ratio(value, population)
}
