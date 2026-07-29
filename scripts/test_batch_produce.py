#!/usr/bin/env python3
"""Tests for the batch adapter: plan admission from the real catalog, bounded
run with the producer stubbed (never renders in tests), budget exhaustion,
and idea-funnel plumbing."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import batch_produce as bp  # noqa: E402


def main():
    catalog = bp.load_catalog()
    assert "money-goes" in catalog and "money-goes-weak" not in catalog
    assert "zz-ci-smoke" not in catalog
    print("ok  1. real catalog loads; controls excluded")

    plan = bp.plan(max_stories=50)
    assert "money-goes" in plan["admitted"], plan
    print(f"ok  2. plan admits {len(plan['admitted'])} real stories")

    # bounded run with the producer stubbed: two stories, one pass one fail.
    # ledger writes go to a TEMP file — the real state ledger is runtime
    # history, and tests must not write into it.
    import run_ledger
    real_ledger_path = run_ledger.LEDGER_PATH
    tmp_ledger = Path(tempfile.mkdtemp()) / "ledger.jsonl"
    run_ledger.LEDGER_PATH = tmp_ledger
    calls = []
    import produce
    real = produce.produce
    produce.produce = lambda slug, out, fresh=False: (
        calls.append(slug) or
        {"status": "pass" if slug == plan["admitted"][0] else "quarantine",
         "reasons": [], "out": str(out)})
    try:
        rep = bp.run_batch(plan["admitted"][:2], max_stories=2,
                           budget_seconds=3600)
    finally:
        produce.produce = real
    assert len(calls) == 2 and len(rep["results"]) == 2
    dvals = set(rep["decisions"].values())
    assert "advance" in dvals and ("quarantine" in dvals or len(set(rep["results"].values())) == 1), rep
    print("ok  3. bounded run drives the real producer interface; decisions recorded")

    # budget exhaustion defers instead of rendering
    calls.clear()
    produce.produce = lambda slug, out, fresh=False: calls.append(slug)
    try:
        rep = bp.run_batch(plan["admitted"][:2], max_stories=2,
                           budget_seconds=-1)
    finally:
        produce.produce = real
        run_ledger.LEDGER_PATH = real_ledger_path
    assert not calls and all("budget" in d for d in rep["decisions"].values())
    assert tmp_ledger.exists()   # events landed in the temp ledger, not state
    print("ok  4. exhausted budget defers every story, renders nothing")

    # idea funnel plumbing
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "ideas.json"
        f.write_text(json.dumps({"ideas": [
            {"candidate_id": "i1", "premise": "why bridges hum",
             "topic_family": "physics", "format_family": "mechanism",
             "duplicate_key": "bridges-hum", "audience_value": 0.8,
             "novelty": 0.8, "evidence_feasibility": 0.9,
             "visual_feasibility": 0.8, "sensitivity_risk": 0.1,
             "estimated_cost": 1.0, "source_count": 3},
            {"candidate_id": "i2", "premise": "shock topic",
             "topic_family": "x", "format_family": "y",
             "duplicate_key": "shock", "audience_value": 0.9,
             "novelty": 0.9, "evidence_feasibility": 0.2,
             "visual_feasibility": 0.8, "sensitivity_risk": 0.9,
             "estimated_cost": 1.0, "source_count": 0},
        ]}))
        rep = bp.ideas(f)
        assert rep["selected"] == ["i1"], rep
        assert any(r["id"] == "i2" for r in rep["rejected"])
        print("ok  5. idea funnel admits the feasible idea, rejects the risky one")

    print("batch adapter: 5/5 tests pass")


if __name__ == "__main__":
    main()
