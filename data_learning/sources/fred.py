"""FRED adapter (Federal Reserve Bank of St. Louis).

Free with an API key (env ``FRED_API_KEY``). Excellent for macro time
series — rates, inflation, GDP, unemployment. Attribution required; some
series carry third-party restrictions, so cite the series explicitly.

Returns the same :class:`Dataset` as every other adapter. A trend pull
returns the last ``params['observations']`` points (default 6).
"""
from __future__ import annotations

import os

from .base import DataPoint, Dataset, DataSource, Source

FRED_OBS_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_META_URL = "https://api.stlouisfed.org/fred/series"


class FredSource(DataSource):
    name = "fred"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("FRED_API_KEY", "")

    def fetch(self, key: str, params: dict | None = None) -> Dataset:
        if not self.api_key:
            raise RuntimeError(
                "FRED_API_KEY not set. Get a free key at "
                "https://fred.stlouisfed.org/docs/api/api_key.html or use "
                "the 'offline' source for a cached snapshot."
            )
        import requests  # local import keeps offline path dependency-free

        params = params or {}
        n = int(params.get("observations", 6))
        freq = params.get("frequency", "a")  # a=annual, m=monthly, q=quarterly

        q = {
            "series_id": key,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": n,
            "frequency": freq,
        }
        r = requests.get(FRED_OBS_URL, params=q, timeout=30)
        r.raise_for_status()
        obs = list(reversed(r.json().get("observations", [])))
        points = [
            DataPoint(label=o["date"][:7], value=float(o["value"]), period=o["date"])
            for o in obs
            if o.get("value") not in (".", "", None)
        ]

        # Pull a friendly title + unit from series metadata (best effort).
        title, unit = key, params.get("unit", "")
        try:
            m = requests.get(
                FRED_META_URL,
                params={"series_id": key, "api_key": self.api_key,
                        "file_type": "json"},
                timeout=30,
            )
            m.raise_for_status()
            series = m.json().get("seriess", [{}])[0]
            title = series.get("title", key)
            unit = unit or series.get("units_short", "")
        except Exception:  # noqa: BLE001 — metadata is non-critical
            pass

        return Dataset(
            key=key,
            title=title,
            unit=unit,
            geography=params.get("geography", "United States"),
            time_coverage=f"{points[0].period} to {points[-1].period}"
            if points else "",
            points=points,
            source=Source(
                name=f"FRED series {key}",
                publisher="Federal Reserve Bank of St. Louis (FRED)",
                url=f"https://fred.stlouisfed.org/series/{key}",
            ),
            notes="FRED data — attribution required; verify series rights.",
        )
