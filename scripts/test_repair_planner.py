#!/usr/bin/env python3
"""Judge feedback must become REPAIR TASKS, ranked deterministically, with the
escalation ladder visible rather than implicit."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from data_learning import repair_planner as rp  # noqa: E402

FINDINGS = [
    {"defect_code": "CHEAP_TYPOGRAPHY", "severity": "minor", "judge": "taste",
     "target": "beat 3", "complaint": "thin type"},
    {"defect_code": "SAMENESS", "severity": "blocker", "judge": "taste",
     "target": "film", "complaint": "every shot alike",
     "recommended_fix": "vary composition and engine"},
    {"defect_code": "FACTUAL_UNSOURCED", "severity": "blocker", "judge": "factual",
     "target": "beat 9", "complaint": "spoken number with no source"},
    {"defect_code": "STALE_SPAN", "severity": "major", "judge": "pacing_retention",
     "time_range": "88.5-96.0s", "complaint": "nothing new for 7.5s"},
    {"defect_code": "HOOK_WEAK", "severity": "major", "judge": "hook",
     "beat": 0, "complaint": "hook scores 4/10"},
]


def main():
    # 1. every finding becomes a task with a target and a success criterion
    p = rp.plan(FINDINGS, attempt=3)          # structural: widest scope
    codes = [t["defect_code"] for t in p["tasks"]]
    assert len(p["tasks"]) == len(FINDINGS), (len(p["tasks"]), codes)
    for t in p["tasks"]:
        for k in ("target", "defect_code", "severity", "subsystem",
                  "required_change", "success_criterion", "evidence",
                  "dependencies", "effort", "repair_class", "tier"):
            assert t.get(k) not in (None, ""), (k, t)
        assert t["evidence"]["judge"], t
    print(f"ok  1. {len(p['tasks'])} findings -> {len(p['tasks'])} tasks, "
          "each with a target, change and success criterion")

    # 2. the judge's OWN recommended fix is what gets asked for, not a generic
    sam = next(t for t in p["tasks"] if t["defect_code"] == "SAMENESS")
    assert sam["required_change"] == "vary composition and engine"
    print("ok  2. the judge's recommended fix is carried into the task")

    # 3. ranking law: integrity -> premise -> structure -> depiction -> polish
    ranks = [t["tier_rank"] for t in p["tasks"]]
    assert ranks == sorted(ranks), [(t["tier"], t["defect_code"]) for t in p["tasks"]]
    assert p["tasks"][0]["tier"] == "integrity"
    assert p["tasks"][-1]["tier"] == "polish"
    print("ok  3. tasks are ordered integrity -> premise -> structure -> "
          "depiction -> polish")

    # 4. deterministic: same findings in a different order -> same plan
    a = rp.signature(rp.plan(FINDINGS, 3))
    b = rp.signature(rp.plan(list(reversed(FINDINGS)), 3))
    assert a == b, "plan is not deterministic under input order"
    print("ok  4. plans are deterministic (a stall is detectable, not random)")

    # 5. the escalation ladder gates SCOPE: a structural fix is not attempted
    #    on attempt 1, it is deferred with the class that would unlock it
    p1 = rp.plan(FINDINGS, attempt=1)
    assert p1["repair_class"] == "local"
    deferred = {t["defect_code"] for t in p1["deferred"]}
    assert "HOOK_WEAK" in deferred, deferred
    assert all(t["subsystem"] in rp.CLASS_SCOPE["local"] for t in p1["tasks"])
    assert next(t for t in p1["deferred"]
                if t["defect_code"] == "HOOK_WEAK")["unlocks_at_class"]
    print("ok  5. attempt 1 is local-only; broader fixes defer with their class")

    assert rp.repair_class(1) == "local"
    assert rp.repair_class(2) == "scene"
    assert rp.repair_class(3) == "structural"
    print("ok  6. the ladder is local -> scene -> structural")

    # 7. integrity tasks gate everything else in the same plan
    integ = [t["id"] for t in p["tasks"] if t["tier"] == "integrity"]
    assert integ
    for t in p["tasks"]:
        if t["tier"] != "integrity":
            assert t["dependencies"] == integ, t
    print("ok  7. non-integrity tasks depend on the integrity tasks")

    # 8. CONTRADICTION GUARD: two subsystems told to change the same target
    conflict = [
        {"defect_code": "SAMENESS", "severity": "major", "judge": "taste",
         "target": "beat 4"},
        {"defect_code": "CAPTIONS", "severity": "minor", "judge": "captions",
         "target": "beat 4"},
    ]
    pc = rp.plan(conflict, attempt=3)
    tgt4 = [t for t in pc["tasks"] if t["target"] == "beat 4"]
    assert len(tgt4) == 1, tgt4
    assert pc["suppressed"] and pc["suppressed"][0]["suppressed_because"]
    assert tgt4[0]["defect_code"] == "SAMENESS", "the weaker finding won"
    print("ok  8. conflicting instructions on one target: severity wins, "
          "the loser is recorded not dropped")

    # 9. an UNKNOWN judge label is never silently dropped
    pu = rp.plan([{"defect_code": "SOME_NEW_LABEL", "severity": "major",
                   "judge": "taste", "target": "beat 1"}], attempt=3)
    assert pu["n_tasks"] == 1 and pu["tasks"][0]["defect_code"] == "SOME_NEW_LABEL"
    print("ok  9. an unrecognised finding still becomes a task")

    # 10. resolved findings produce no work
    assert rp.plan([{**FINDINGS[0], "resolved": True}], 3)["n_tasks"] == 0
    print("ok 10. resolved findings generate no tasks")

    print("repair planner: 10/10 checks pass")


if __name__ == "__main__":
    main()
