#!/usr/bin/env python3
"""Tests for the story advisor: mechanical mapping is well-formed (0-10
ranges, non-overlapping moments), the report discriminates between a varied
story and a monotone card reel, the missing-payoff heuristic fires, and the
whole thing runs end-to-end on the real flagship."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO / "scripts", REPO / "experiments"):
    sys.path.insert(0, str(p))

import story_advisor as sa  # noqa: E402


def _beat(narration, kind=None, image=False):
    b = {"narration": narration}
    if kind:
        b["flat"] = {"kind": kind}
    if image:
        b["image"] = {"query": "x"}
    return b


def main():
    varied = [
        _beat("Where does your money actually go?", kind="scene_money"),
        _beat("Rent takes the biggest bite every single month.", image=True),
        _beat("Then groceries, quietly, relentlessly.", kind="flat_meter"),
        _beat("And what is left answers the question we started with: "
              "your money goes to keeping you alive.", kind="scene_money"),
    ]
    moments = sa.beats_to_moments(varied)
    for m in moments:
        for f in ("novelty", "curiosity", "clarity", "visual_change",
                  "cognitive_load"):
            assert 0.0 <= getattr(m, f) <= 10.0, (f, getattr(m, f))
    for a, b in zip(moments, moments[1:]):
        assert b.start_seconds >= a.start_seconds + a.duration_seconds - 0.001
    info = sa.beats_to_information(varied)
    assert len(info) == len(varied)
    print("ok  1. mechanical mapping is in-contract (ranges, no overlap)")

    # a monotone card reel must score WORSE retention risk than varied beats
    from curiosity_nextgen.retention_risk import analyze_retention_risk
    monotone = [_beat("Another statistic on a card.", kind="flat_meter")
                for _ in range(6)]
    risk_varied = analyze_retention_risk(sa.beats_to_moments(varied))
    risk_mono = analyze_retention_risk(sa.beats_to_moments(monotone))
    assert risk_mono.overall_risk_score > risk_varied.overall_risk_score, (
        risk_mono.overall_risk_score, risk_varied.overall_risk_score)
    assert any(any(d.code == "repeated_visual_family" for d in m.defects)
               for m in risk_mono.moment_risks)
    print("ok  2. monotone card reel scores worse; repetition defect fires")

    # payoff heuristic: an ending that never re-touches the hook is flagged
    real_load = sa.advise.__globals__["analyze_cognitive_load"]
    story_dir = sa.REPO / "data_learning" / "pro_stories"
    tmp = story_dir / "zz-advisor-selftest.beats.json"
    tmp.write_text(json.dumps({"beats": [
        _beat("Why do hurricanes spin counterclockwise?"),
        _beat("Warm water rises from the ocean surface."),
        _beat("Air rushes inward to replace it."),
        _beat("The planet's rotation bends every path."),
        _beat("Thanks for watching, subscribe."),
    ]}))
    try:
        rep = sa.advise("zz-advisor-selftest")
        assert rep["payoff_note"], rep
        print("ok  3. unanswered hook is flagged")
    finally:
        tmp.unlink(missing_ok=True)
        out = sa.REPO / "output" / "zz-advisor-selftest.advisor.json"
        out.unlink(missing_ok=True)
    assert real_load is sa.advise.__globals__["analyze_cognitive_load"]

    # end-to-end on the real flagship
    rep = sa.advise("money-goes")
    assert rep["advisory"] is True
    assert rep["cognitive_load"]["decision"]
    assert rep["retention"]["level"]
    assert (sa.REPO / "output" / "money-goes.advisor.json").exists()
    print("ok  4. real flagship advises end-to-end")

    print("story advisor: 4/4 tests pass")


if __name__ == "__main__":
    main()
