#!/usr/bin/env python3
"""Unit tests for the facts gate (Phase 9). Each blocking rule is exercised in
isolation on synthetic claims — no story files, no network."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import facts_gate  # noqa: E402

TODAY = date(2026, 7, 25)


def _claim(**over) -> dict:
    base = {
        "id": "claim-x-01", "claim": "X is about 40%.",
        "source_title": "Annual Survey of X", "publisher": "Bureau of X",
        "source_type": "official", "publication_date": "2023-06-01",
        "accessed_date": "2026-07-25", "geography": "United States",
        "population": "adults", "calculation": "",
        "assumptions": ["national average"],
        "uncertainty": "±5pp", "confidence": "medium",
    }
    base.update(over)
    return base


def check(name, claim, want_substr):
    errs = facts_gate._check_claim(claim, TODAY)
    if want_substr is None:
        assert not errs, f"{name}: expected clean, got {errs}"
    else:
        assert any(want_substr in e for e in errs), \
            f"{name}: expected error containing {want_substr!r}, got {errs}"
    print(f"ok  {name}")


def main():
    check("valid claim passes", _claim(), None)
    check("missing source blocks", _claim(source_title=""), "source_title")
    check("missing geography blocks", _claim(geography=""), "geography")
    check("hidden assumptions block", _claim(assumptions=[]), "assumptions")
    check("vague source blocks",
          _claim(source_title="the internet", publisher=""), "vague")
    check("bad source type blocks",
          _claim(source_type="vibes"), "source_type")
    check("stale time-sensitive source blocks",
          _claim(publication_date="2015-01-01"), "stale")
    check("derived without calculation blocks",
          _claim(source_type="derived", calculation=""), "calculation")
    check("modeled-as-universal blocks",
          _claim(presentation="universal_fact",
                 calculation="a*b"), "universal fact")
    check("derived WITH calculation passes",
          _claim(source_type="derived", publication_date="2026-07-01",
                 calculation="2M - 500k - 500k = 1M"), None)

    # Coverage semantics on a synthetic story: a numeric beat with no claim
    # blocks; echo_beats cover restatement beats.
    story = {"require_provenance": True, "beats": [
        {"narration": "It costs two million dollars."},
        {"narration": "No numbers here, purely a mood beat."},
        {"narration": "That two million again — gone."},
    ]}
    registry = {"claims": [_claim(beat_index=0, echo_beats=[2])]}
    real_load = facts_gate._load
    facts_gate._load = lambda slug: (story, registry)
    try:
        rep = facts_gate.evaluate("synthetic", today=TODAY)
        assert rep["pass"], rep
        assert rep["coverage"] == {"numeric_beats": 2, "covered": 2,
                                   "uncovered": []}, rep["coverage"]
        print("ok  echo_beats cover restatement beats")
        registry2 = {"claims": [_claim(beat_index=0)]}
        facts_gate._load = lambda slug: (story, registry2)
        rep2 = facts_gate.evaluate("synthetic", today=TODAY)
        assert not rep2["pass"] and rep2["coverage"]["uncovered"] == [2], rep2
        print("ok  uncovered numeric beat blocks")
    finally:
        facts_gate._load = real_load
    print("facts gate: 12/12 tests pass")


if __name__ == "__main__":
    main()
