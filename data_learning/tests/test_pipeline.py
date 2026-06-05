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
