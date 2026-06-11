"""Tests for the data_learning add-on.

Runnable two ways:
    python -m data_learning.tests.test_pipeline      # plain, no pytest
    pytest data_learning/tests/test_pipeline.py

The key guarantee under test is the *contract with the base renderer*:
every shot/punch phrase must be a verbatim substring of the script, and
every spoken metric must trace to the fact table.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from data_learning import insights, packager, qa            # noqa: E402
from data_learning.sources import get_source                 # noqa: E402
from data_learning.sources.offline import OfflineSource      # noqa: E402
from data_learning import transforms as T                    # noqa: E402


def _pkg(key, file, insight_type, ascending=False, use_baseline=False,
         topic=None):
    src = get_source("offline")
    ds = src.fetch(key, {"file": file})
    baseline = src.baseline(key, {"file": file}) if use_baseline else None
    ins = insights.build(ds, insight_type=insight_type, baseline=baseline,
                         ascending=ascending)
    if topic:
        ins.topic = topic
    return packager.build_package(ins, slug=key, chart_path=None,
                                  hashtags=["x", "y"])


def test_rank_package_passes_qa():
    pkg = _pkg("state_unemployment", "state_unemployment_2026_04.json",
               "rank", ascending=True, use_baseline=True, topic="unemployment rate")
    errors = qa.validate(pkg)
    assert errors == [], errors
    # The leader (lowest) should be South Dakota and titled "Lowest".
    assert "South Dakota" in pkg["title"]
    assert "Lowest" in pkg["title"]


def test_comparison_package_passes_qa():
    pkg = _pkg("cpi_components", "cpi_components_2026_04.json",
               "comparison", use_baseline=True, topic="inflation by category")
    assert qa.validate(pkg) == []


def test_trend_package_passes_qa():
    pkg = _pkg("fed_funds_rate", "fed_funds_rate.json", "trend",
               topic="interest rates")
    assert qa.validate(pkg) == []


def test_phrases_are_verbatim_substrings():
    """The single hardest contract with the base renderer."""
    for key, f, it, asc, bl in [
        ("state_unemployment", "state_unemployment_2026_04.json", "rank", True, True),
        ("cpi_components", "cpi_components_2026_04.json", "comparison", False, True),
        ("fed_funds_rate", "fed_funds_rate.json", "trend", False, False),
    ]:
        pkg = _pkg(key, f, it, ascending=asc, use_baseline=bl)
        script = pkg["script"].lower()
        for s in pkg["shots"]:
            assert s["phrase"].lower() in script, (key, s["phrase"])
        for p in pkg["punches"]:
            assert p["phrase"].lower() in script, (key, p["phrase"])


def test_qa_catches_unsourced_number():
    pkg = _pkg("state_unemployment", "state_unemployment_2026_04.json",
               "rank", ascending=True, use_baseline=True)
    # Inject a hallucinated metric into the script.
    pkg["script"] += " The mystery figure is 99.9 percent."
    errors = qa.validate(pkg)
    assert any("99.9" in e for e in errors), errors


def test_qa_catches_non_substring_phrase():
    pkg = _pkg("cpi_components", "cpi_components_2026_04.json",
               "comparison", use_baseline=True)
    pkg["shots"].append({"phrase": "this text is definitely not present",
                         "query": "x"})
    errors = qa.validate(pkg)
    assert any("not in script" in e for e in errors), errors


def test_transforms():
    assert T.pct_change(100, 150) == 50.0
    assert T.difference_from_baseline(2.2, 4.3) == -2.1 or \
        abs(T.difference_from_baseline(2.2, 4.3) + 2.1) < 1e-9
    assert T.rolling_average([1, 2, 3, 4], 2) == [1.0, 1.5, 2.5, 3.5]
    try:
        T.ratio(1, 0)
        assert False, "expected ZeroDivisionError"
    except ZeroDivisionError:
        pass


def test_offline_source_roundtrip():
    src = OfflineSource()
    ds = src.fetch("cpi_components", {"file": "cpi_components_2026_04.json"})
    assert ds.unit == "percent"
    assert ds.by_label("Gasoline").value == 28.4
    assert "Bureau of Labor Statistics" in ds.source.publisher


def test_refresh_snapshot_roundtrip():
    """A live pull, once normalised, must be valid offline-format that loads
    back cleanly — this is the data-integrity path (real numbers replacing
    'Illustrative' ones)."""
    from data_learning.sources.base import Dataset, DataPoint, Source
    from data_learning.sources.offline import dataset_from_dict
    from scripts.refresh_data import snapshot_from_dataset

    ds = Dataset(
        key="savings_rate", title="x", unit="percent", geography="US",
        time_coverage="",
        points=[DataPoint("2020-01", 7.5, "percent", "2020-01-01"),
                DataPoint("2024-01", 4.1, "percent", "2024-01-01")],
        source=Source(name="FRED series PSAVERT",
                      publisher="Federal Reserve Bank of St. Louis (FRED)",
                      url="https://fred.stlouisfed.org/series/PSAVERT"))
    existing = {"key": "savings_rate", "title": "Personal Saving Rate (%)",
                "unit": "percent", "geography": "United States"}
    m = {"adapter": "fred", "series": "PSAVERT", "frequency": "a",
         "unit": "percent", "label": "year"}
    snap = snapshot_from_dataset(ds, existing, m)
    assert [p["label"] for p in snap["points"]] == ["2020", "2024"]  # year norm
    assert not snap["notes"].lower().startswith("illustrative")      # honest
    assert snap["title"] == "Personal Saving Rate (%)"              # framing kept
    d2 = dataset_from_dict(snap)                                     # loads back
    assert d2.by_label("2020").value == 7.5


def test_refresh_rejects_thin_pull():
    """A live pull with <2 usable points must refuse to overwrite, not ship
    a degenerate chart."""
    from data_learning.sources.base import Dataset, DataPoint, Source
    from scripts.refresh_data import snapshot_from_dataset
    ds = Dataset(key="x", title="x", unit="percent", geography="US",
                 time_coverage="",
                 points=[DataPoint("2024", 4.1, "percent", "2024-01-01")],
                 source=Source(name="n", publisher="p", url="u"))
    try:
        snapshot_from_dataset(ds, {"key": "x"}, {"adapter": "fred", "series": "X"})
        assert False, "expected ValueError on a thin pull"
    except ValueError:
        pass


def test_thumbnail_headline_number():
    """The thumbnail accent must be the biggest-magnitude on-chart number."""
    from data_learning import studio_render as sr

    class _Seg:
        def __init__(self, punches):
            self.punches = punches

    class _St:
        segments = [_Seg([{"text": "12%"}, {"text": "1,370"}]),
                    _Seg([{"text": "449"}])]
    assert sr._headline_number(_St()) == "1,370"
    assert sr._num_magnitude("$1,920") == 1920.0
    assert sr._num_magnitude("200%") == 200.0


def _main() -> int:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
