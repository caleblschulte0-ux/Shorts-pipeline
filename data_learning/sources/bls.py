"""BLS adapter (U.S. Bureau of Labor Statistics).

The Public Data API v1 is open with no key (25 queries/day, 10 yrs/series);
v2 adds capacity with a free registration key (env ``BLS_API_KEY``). BLS
material is public domain — cite BLS and the retrieval date.

A pull returns the latest ``params['observations']`` periods of one or more
series ids. When multiple series ids are supplied (comma-separated ``key``
or ``params['series']``), the latest value of each becomes one point — a
cross-series comparison/rank. A single series id returns a trend.
"""
from __future__ import annotations

import os

from .base import DataPoint, Dataset, DataSource, Source

BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"


class BlsSource(DataSource):
    name = "bls"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("BLS_API_KEY", "")

    def fetch(self, key: str, params: dict | None = None) -> Dataset:
        import json as _json

        import requests

        params = params or {}
        series_ids = params.get("series") or [s.strip() for s in key.split(",")]
        labels = params.get("labels") or {}
        n = int(params.get("observations", 6))

        from datetime import date
        end_year = int(params.get("end_year", date.today().year))
        start_year = int(params.get("start_year", end_year - 2))

        payload = {
            "seriesid": series_ids,
            "startyear": str(start_year),
            "endyear": str(end_year),
        }
        if self.api_key:
            payload["registrationkey"] = self.api_key

        r = requests.post(
            BLS_URL, data=_json.dumps(payload),
            headers={"Content-Type": "application/json"}, timeout=30,
        )
        r.raise_for_status()
        body = r.json()
        if body.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(f"BLS API error: {body.get('message')}")

        series_results = body["Results"]["series"]
        points: list[DataPoint] = []
        multi = len(series_results) > 1

        for sr in series_results:
            sid = sr["seriesID"]
            data = sr.get("data", [])
            # data is newest-first; take the latest non-empty value.
            if multi:
                if data:
                    d0 = data[0]
                    points.append(DataPoint(
                        label=labels.get(sid, sid),
                        value=float(d0["value"]),
                        period=f"{d0['year']}-{d0['period']}",
                    ))
            else:
                for d in reversed(data[:n]):
                    points.append(DataPoint(
                        label=f"{d['year']}-{d['period']}",
                        value=float(d["value"]),
                        period=f"{d['year']}-{d['period']}",
                    ))

        return Dataset(
            key=key,
            title=params.get("title", "BLS series"),
            unit=params.get("unit", ""),
            geography=params.get("geography", "United States"),
            time_coverage=params.get("time_coverage", f"{start_year}-{end_year}"),
            points=points,
            source=Source(
                name=params.get("source_name", "BLS Public Data API"),
                publisher="U.S. Bureau of Labor Statistics",
                url=params.get(
                    "source_url", "https://www.bls.gov/developers/"),
            ),
            notes="BLS public-domain data; cite BLS and retrieval date.",
        )
