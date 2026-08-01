#!/usr/bin/env python3
"""PIPELINE SIMULATION — the deterministic 50-story batch drill, CI-runnable.

Adapter over experiments/curiosity_nextgen/autonomous_simulator.py: a fully
deterministic synthetic batch (50 opaque stories across 5 topic and 4 format
families) runs the REAL production stage sequence
(production_stage_graph.StageName) under an injected fault campaign —
transient flakes, repairable defects, factual holes, missing evidence, and
outright fatal stage failures — and the batch must land EXACTLY where the
recovery rules say it should:

  - transient faults retry within the attempt cap and still complete;
  - repairable faults consume the repair budget and complete;
  - a factual fault REWINDS the story to research and re-runs it — one
    bad fact costs a re-research, not a publish; persistent factual
    faults exhaust the attempt cap and QUARANTINE;
  - missing evidence is a safe stop: the story HOLDS (never completes,
    never silently drops) and the batch verdict is invalid while any
    held story remains;
  - fatal faults quarantine;
  - the whole run is bit-for-bit deterministic (same result twice).

No renderer, no network, no story content — this drills the DECISION
machinery at a scale the real catalog can't yet, so regressions in retry /
repair / quarantine logic surface in CI before they meet a real render.
Exit 0 = every assertion holds; 1 = drift detected (report printed).

    python3 scripts/simulate_pipeline.py           -> output/simulation_report.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "experiments"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from curiosity_nextgen.autonomous_simulator import (   # noqa: E402
    InjectedFault, SimulatedStory, SimulationPolicy, simulate_batch)
from curiosity_nextgen.production_stage_graph import StageName  # noqa: E402

TOPICS = ("economics", "physics", "biology", "history", "engineering")
FORMATS = ("mechanism", "journey", "comparison", "scale")
STAGES = tuple(s.value for s in StageName if s.value != "publish")
# publish is excluded from the drill on purpose: the simulator must never
# model a path the real pipeline keeps behind explicit owner approval.


def build_batch() -> tuple[list[SimulatedStory], list[InjectedFault]]:
    """50 deterministic stories + a fixed fault campaign. Identity is opaque
    (sim-NN); families rotate so portfolio-style spread exists."""
    stories = [
        SimulatedStory(
            story_id=f"sim-{i:02d}",
            topic_family=TOPICS[i % len(TOPICS)],
            format_family=FORMATS[i % len(FORMATS)],
            factual_risk=("high" if i % 10 == 7 else
                          "medium" if i % 3 == 0 else "low"),
        ) for i in range(50)
    ]
    faults = [
        # transient flakes on media/render stages — must retry and complete
        InjectedFault("sim-03", "media", "transient"),
        InjectedFault("sim-11", "draft_render", "transient", occurrences=2),
        InjectedFault("sim-24", "final_render", "transient"),
        # repairable editorial defects — must consume repairs and complete
        InjectedFault("sim-07", "editorial_review", "repairable"),
        InjectedFault("sim-19", "technical_review", "repairable"),
        # one factual hole — must rewind to research, re-run, complete
        InjectedFault("sim-13", "fact_review", "factual"),
        # a PERSISTENT factual hole — must exhaust attempts and quarantine
        InjectedFault("sim-27", "fact_review", "factual", occurrences=3),
        # missing evidence — must HOLD (safe stop, not silent completion)
        InjectedFault("sim-31", "claims", "missing_evidence"),
        # fatal — must QUARANTINE, never complete
        InjectedFault("sim-42", "package", "fatal"),
    ]
    return stories, faults


def run() -> dict:
    stories, faults = build_batch()
    policy = SimulationPolicy(
        stages=STAGES, maximum_stories=50, maximum_attempts_per_stage=3,
        maximum_repairs_per_story=2, maximum_total_cost=5_000.0,
        minimum_completion_rate=0.90, maximum_quarantine_rate=0.10)
    res1 = simulate_batch(stories, faults, policy)
    res2 = simulate_batch(stories, faults, policy)

    by_id = {r.story_id: r for r in res1.stories}
    failures: list[str] = []

    def expect(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    expect(res1 == res2, "simulation is not deterministic across two runs")
    for sid in ("sim-03", "sim-11", "sim-24"):
        expect(by_id[sid].status == "completed",
               f"{sid}: transient fault should retry to completion, "
               f"got {by_id[sid].status}")
    for sid in ("sim-07", "sim-19"):
        expect(by_id[sid].status == "completed" and by_id[sid].repairs >= 1,
               f"{sid}: repairable fault should repair+complete, got "
               f"{by_id[sid].status} repairs={by_id[sid].repairs}")
    expect(by_id["sim-13"].status == "completed"
           and any(r.startswith("factual_rewind") for r in
                   by_id["sim-13"].reasons),
           f"sim-13: one factual fault should rewind+complete, got "
           f"{by_id['sim-13'].status} {by_id['sim-13'].reasons}")
    expect(by_id["sim-27"].status == "quarantined"
           and "factual_attempts_exhausted:fact_review" in
           by_id["sim-27"].reasons,
           f"sim-27: persistent factual fault must quarantine, got "
           f"{by_id['sim-27'].status} {by_id['sim-27'].reasons}")
    expect(by_id["sim-31"].status == "held"
           and "missing_evidence:claims" in by_id["sim-31"].reasons,
           f"sim-31: missing evidence must HOLD, got {by_id['sim-31'].status}")
    expect(by_id["sim-42"].status == "quarantined"
           and "fatal:package" in by_id["sim-42"].reasons,
           f"sim-42: fatal fault must quarantine, got {by_id['sim-42'].status}")
    expect(res1.completed_count == 47 and res1.quarantined_count == 2
           and res1.held_count == 1,
           f"expected 47 completed / 2 quarantined / 1 held, got "
           f"{res1.completed_count}/{res1.quarantined_count}/{res1.held_count}")
    # the batch verdict must be INVALID while a held story remains — a safe
    # stop is never silently accepted as a finished batch
    expect(not res1.valid and "held_stories_remaining" in res1.blockers,
           f"held story must invalidate the batch, got valid={res1.valid} "
           f"blockers={res1.blockers}")
    clean = [r for r in res1.stories if r.status == "completed"
             and not r.repairs and r.story_id not in
             ("sim-03", "sim-11", "sim-24", "sim-13")]
    expect(all(all(n == 1 for _, n in r.attempts) for r in clean),
           "an un-faulted story took more than one attempt at some stage")

    report = {
        "stories": len(stories),
        "completed": res1.completed_count,
        "quarantined": res1.quarantined_count,
        "held": res1.held_count,
        "total_cost": res1.total_cost,
        "policy_valid": res1.valid,
        "policy_blockers": list(res1.blockers),
        "deterministic": res1 == res2,
        "assertion_failures": failures,
        "quarantined_stories": [
            {"id": r.story_id, "reasons": list(r.reasons)[:2]}
            for r in res1.stories if r.status == "quarantined"],
    }
    dest = REPO / "output" / "simulation_report.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main(argv) -> int:
    report = run()
    ok = not report["assertion_failures"]
    print(f"[simulate] {report['stories']} stories: "
          f"{report['completed']} completed, "
          f"{report['quarantined']} quarantined, deterministic="
          f"{report['deterministic']} -> output/simulation_report.json")
    for f in report["assertion_failures"]:
        print(f"  DRIFT: {f}", file=sys.stderr)
    print("[simulate] " + ("PASS — decision machinery matches the contract"
                           if ok else "FAIL — recovery rules drifted"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
