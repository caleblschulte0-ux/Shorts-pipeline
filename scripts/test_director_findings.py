#!/usr/bin/env python3
"""The director's complaints must become REPAIR TASKS, not log text.

The gap this closes: across five consecutive production runs every log ended
with `repair applied NOTHING at the local class`. Not because the ladder blocked
it — because `findings[]` was empty. The taste and factual judges abstain
headlessly, and the DIRECTOR's own diagnosis (a hook verdict, per-beat dullness
with the correct repair kind, seven timecoded stale spans, the card budget) was
`print()` output that no consumer could read. The richest signal in the pipeline
was invisible to the thing built to act on it.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

import no_dull_beats as ndb  # noqa: E402
from data_learning import auto_repair, repair_planner  # noqa: E402

HV_FAIL = {"pass": False, "total": 5, "line_gates": ["NO_GAP_NO_STAKES"],
           "gates": []}
INTEREST = {"dead_fraction": 0.05, "mean_appeal": 0.63}
DULL = [{"beat": 9, "job": "REVEAL", "why": "dead stretch, appeal 0.594",
         "kind": "motion"},
        {"beat": 13, "job": "DEVELOP", "why": "static designed card",
         "kind": "animate"}]


def main():
    ndb._LAST_STALE = [(32.5, 41.0), (111.0, 118.0)]
    f = ndb._collect_findings(HV_FAIL, INTEREST, DULL,
                              excess="data-cards are 46% of the video")
    codes = [x["defect_code"] for x in f]
    assert "HOOK_WEAK" in codes and codes.count("DULL_BEAT") == 2 \
        and codes.count("STALE_SPAN") == 2 and "CARDS_OVER_BUDGET" in codes, codes
    print(f"ok  1. every gate the director failed becomes a finding ({codes})")

    # 2. the stale span keeps its TIMECODE — a repair cannot find an untargeted span
    span = [x for x in f if x["defect_code"] == "STALE_SPAN"][0]
    assert "32.5-41.0s" == span["target"], span
    assert "8.5s" in span["complaint"], span
    print(f"ok  2. a stale span carries its timecode and duration "
          f"({span['target']}, {span['complaint']})")

    # 3. a DESIGNED dull beat asks to be animated, a footage one to be moved —
    #    prescribing footage for a card replaces an explainer the viewer needs
    fixes = {x["target"]: x.get("recommended_fix", "")
             for x in f if x["defect_code"] == "DULL_BEAT"}
    assert "motion" in fixes["beat 9"] and "card" in fixes["beat 13"], fixes
    print("ok  3. a static card asks for animation, a dull footage beat for motion")

    # 4. THE WHOLE POINT: these findings survive the planner and become tasks
    plan = repair_planner.plan(f, attempt=1, escalation="scene")
    assert plan["n_tasks"] > 0, plan
    got = {t["defect_code"] for t in plan["tasks"]}
    assert "DULL_BEAT" in got, got
    print(f"ok  4. the planner turns them into {plan['n_tasks']} real task(s) "
          f"({sorted(got)})")

    # 5. ...and the repairer APPLIES them (the step that idled five times)
    story = {"slug": "x", "beats": [{"kind": "flat_hook"} for _ in range(20)]}
    story["beats"][9] = {"kind": "footage", "subject": "crowd", "image": {}}
    story["beats"][13] = {"kind": "flat_number"}
    _, journal = auto_repair.apply(plan, story, escalation="scene")
    applied = [j for j in journal if j["applied"]]
    assert applied, journal
    print(f"ok  5. the repairer applies {len(applied)} of them — the loop that "
          "idled through five runs now has input")

    # 6. a CLEAN director run must produce NO findings, or the loop would
    #    "repair" a film that already passed. (`_LAST_STALE` is re-set from
    #    novelty_check every round in production, so a clean round clears it.)
    ndb._LAST_STALE = []
    assert ndb._collect_findings({"pass": True, "total": 9}, INTEREST, [],
                                 excess=None) == []
    print("ok  6. a clean run yields no findings (nothing to repair)")

    print("director findings: 6/6 checks pass")


if __name__ == "__main__":
    ndb._LAST_STALE = []
    main()
