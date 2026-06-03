"""Offline adapter — reads bundled JSON datasets in ``data/``.

This is the zero-dependency, zero-network, zero-key path. It lets the whole
add-on run end-to-end in CI or on a fresh checkout, and doubles as a cache
format: a live adapter (FRED/BLS) can snapshot its pull into this shape for
reproducible re-renders.
"""
from __future__ import annotations

import json
from pathlib import Path

from .base import DataPoint, Dataset, DataSource, Source

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def dataset_from_dict(d: dict) -> Dataset:
    """Build a :class:`Dataset` from the bundled JSON shape. Shared so a
    live adapter can emit the same on-disk cache format."""
    src = d["source"]
    points = [
        DataPoint(
            label=p["label"],
            value=float(p["value"]),
            unit=p.get("unit", d.get("unit", "")),
            period=p.get("period"),
        )
        for p in d["points"]
    ]
    # Carry an optional baseline through as a labelled point flagged in notes;
    # the insight layer reads ds.by_label(baseline_label).
    return Dataset(
        key=d["key"],
        title=d["title"],
        unit=d.get("unit", ""),
        geography=d.get("geography", ""),
        time_coverage=d.get("time_coverage", ""),
        points=points,
        source=Source(
            name=src["name"],
            publisher=src["publisher"],
            url=src["url"],
            officiality=src.get("officiality", "official"),
            access_date=src.get("access_date"),
        ),
        notes=d.get("notes"),
    )


class OfflineSource(DataSource):
    name = "offline"

    def fetch(self, key: str, params: dict | None = None) -> Dataset:
        params = params or {}
        # `file` param wins; otherwise look for <key>.json then any file
        # whose embedded "key" matches.
        fname = params.get("file")
        candidates: list[Path] = []
        if fname:
            candidates.append(DATA_DIR / fname)
        candidates.append(DATA_DIR / f"{key}.json")
        for c in candidates:
            if c.exists():
                return dataset_from_dict(json.loads(c.read_text()))
        # Fall back to scanning for a matching embedded key.
        for p in sorted(DATA_DIR.glob("*.json")):
            try:
                d = json.loads(p.read_text())
            except json.JSONDecodeError:
                continue
            if d.get("key") == key:
                return dataset_from_dict(d)
        raise FileNotFoundError(
            f"no bundled dataset for key={key!r} (looked in {DATA_DIR})"
        )

    def baseline(self, key: str, params: dict | None = None) -> dict | None:
        """Expose the optional baseline block for the insight layer."""
        params = params or {}
        fname = params.get("file") or f"{key}.json"
        p = DATA_DIR / fname
        if p.exists():
            return json.loads(p.read_text()).get("baseline")
        return None
