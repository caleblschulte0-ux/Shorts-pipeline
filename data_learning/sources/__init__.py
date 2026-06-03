"""Data-source adapters.

Every adapter returns a :class:`~data_learning.sources.base.Dataset` so the
rest of the pipeline is source-agnostic — swapping niches means swapping
the adapter named in ``niche.config.json``, nothing else.
"""
from __future__ import annotations

from .base import DataPoint, Dataset, DataSource, Source
from .offline import OfflineSource
from .fred import FredSource
from .bls import BlsSource

# Registry keyed by the string used in niche.config.json -> "source".
REGISTRY: dict[str, type[DataSource]] = {
    "offline": OfflineSource,
    "fred": FredSource,
    "bls": BlsSource,
}


def get_source(name: str) -> DataSource:
    """Instantiate a registered adapter by name."""
    try:
        cls = REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"unknown data source {name!r}; known: {sorted(REGISTRY)}"
        ) from None
    return cls()


__all__ = [
    "DataPoint",
    "Dataset",
    "DataSource",
    "Source",
    "OfflineSource",
    "FredSource",
    "BlsSource",
    "REGISTRY",
    "get_source",
]
