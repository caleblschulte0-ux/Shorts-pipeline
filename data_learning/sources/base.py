"""Source-agnostic data model.

A :class:`Dataset` is a flat list of labelled numeric points plus the
provenance needed for on-screen citation and QA. Every adapter normalizes
into this shape so the insight/packaging layers never care where the
numbers came from.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Source:
    """Provenance for a dataset — drives the on-screen source footer and
    the QA source-allowlist check."""

    name: str                 # e.g. "BLS State Unemployment Rates"
    publisher: str            # e.g. "U.S. Bureau of Labor Statistics"
    url: str                  # canonical source URL
    officiality: str = "official"   # official | primary | secondary
    access_date: str = field(default_factory=lambda: date.today().isoformat())

    def footer(self) -> str:
        """Exact source-footer text for the on-screen card / description."""
        return f"Source: {self.publisher} ({self.name}), accessed {self.access_date}"


@dataclass
class DataPoint:
    """One labelled value (a state, a category, a point in a time series)."""

    label: str
    value: float
    unit: str = ""
    # Optional time key for trend series ("2020", "2026-04", ...).
    period: str | None = None


@dataclass
class Dataset:
    """Normalized output of any :class:`DataSource`."""

    key: str                      # the query key from niche.config (series id)
    title: str                    # human title for the metric
    unit: str                     # default unit for the points
    geography: str                # "United States by state", "NBA", ...
    time_coverage: str            # "April 2026", "2015-2026", ...
    points: list[DataPoint]
    source: Source
    notes: str | None = None

    def values(self) -> list[float]:
        return [p.value for p in self.points]

    def by_label(self, label: str) -> DataPoint | None:
        for p in self.points:
            if p.label == label:
                return p
        return None


class DataSource:
    """Adapter interface. Implementations turn (key, params) into a
    :class:`Dataset`. Keep adapters thin and side-effect free beyond the
    network fetch."""

    #: short id used in niche.config.json -> "source"
    name: str = "base"

    def fetch(self, key: str, params: dict | None = None) -> Dataset:
        raise NotImplementedError
