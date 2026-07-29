#!/usr/bin/env python3
"""LEARNING PROPOSALS — the controlled, evidence-gated policy learning loop.

Adapter over experiments/curiosity_nextgen/controlled_learning_loop.py: the
ONLY sanctioned way analytics turn into pipeline-policy changes. No metric
ever edits a threshold directly; the loop is:

  observe -> propose (guardrailed) -> CANARY (N clean batches) -> owner applies

An observations file (real analytics once uploads exist; the schema is
documented below) is summarized per variant and a proposal is emitted ONLY
when every guardrail holds: one experiment, one base policy version, enough
impressions and stories per variant, a real watch-ratio AND completion lift,
no negative-feedback regression, no hard blockers, and every parameter delta
within the bounded step (default 10%). The proposal is sha256-bound to its
exact evidence and still requires the canary check
(``--canary --passed-batches N --rollback-ready``) before anyone applies it.
This tool NEVER writes a policy change itself — it writes a proposal
document to output/ and the ledger; applying it stays a human commit.

Observations JSON:
  {"experiment_id": "...", "control_variant": "control",
   "candidate_parameters": {"param_name": delta, ...},
   "observations": [{"story_id","experiment_id","variant","policy_version",
                     "impressions","average_watch_ratio","completion_rate",
                     "negative_feedback_rate","hard_blocker"?}, ...]}

    python3 scripts/learning_proposals.py observations.json
    python3 scripts/learning_proposals.py observations.json --canary \
        --passed-batches 2 --rollback-ready
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts", REPO / "experiments"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from curiosity_nextgen.controlled_learning_loop import (   # noqa: E402
    LearningPolicy, PerformanceObservation, approve_learning_canary,
    propose_policy_update)


def load_observations(path: Path) -> tuple[list[PerformanceObservation],
                                           str, dict]:
    raw = json.loads(path.read_text())
    obs = [PerformanceObservation(
        story_id=str(o["story_id"]),
        experiment_id=str(o["experiment_id"]),
        variant=str(o["variant"]),
        policy_version=str(o["policy_version"]),
        impressions=int(o["impressions"]),
        average_watch_ratio=float(o["average_watch_ratio"]),
        completion_rate=float(o["completion_rate"]),
        negative_feedback_rate=float(o["negative_feedback_rate"]),
        hard_blocker=bool(o.get("hard_blocker", False)),
    ) for o in raw.get("observations", [])]
    return obs, str(raw.get("control_variant", "control")), \
        dict(raw.get("candidate_parameters", {}))


def propose(path: Path, policy: LearningPolicy | None = None) -> dict:
    obs, control, params = load_observations(path)
    proposal = propose_policy_update(
        obs, control_variant=control, candidate_parameters=params,
        policy=policy or LearningPolicy())
    doc = {
        "source": path.name,
        "experiment_id": proposal.experiment_id,
        "base_policy_version": proposal.base_policy_version,
        "status": proposal.status,               # canary_required | hold
        "winning_variant": proposal.winning_variant,
        "proposed_parameters": [list(x) for x in
                                proposal.proposed_parameters],
        "evidence_digest": proposal.evidence_digest,
        "blockers": list(proposal.blockers),
        "required_canary_batches": proposal.required_canary_batches,
        "note": ("a proposal NEVER applies itself: it must clear "
                 f"{proposal.required_canary_batches} canary batch(es) with "
                 "rollback ready, then an owner commits the change"),
    }
    dest = REPO / "output" / "learning_proposal.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2) + "\n")
    try:
        import run_ledger
        run_ledger.append("learning_proposal", proposal.experiment_id or "-",
                          {"status": proposal.status,
                           "winner": proposal.winning_variant,
                           "digest": (proposal.evidence_digest or "")[:16],
                           "blockers": list(proposal.blockers)[:4]})
    except Exception:  # noqa: BLE001 — ledger trouble must not block review
        pass
    return doc


def canary(path: Path, passed_batches: int, rollback_ready: bool) -> dict:
    obs, control, params = load_observations(path)
    proposal = propose_policy_update(
        obs, control_variant=control, candidate_parameters=params,
        policy=LearningPolicy())
    ok, blockers = approve_learning_canary(
        proposal, passed_batches=passed_batches,
        rollback_ready=rollback_ready)
    return {"approved": ok, "blockers": list(blockers),
            "evidence_digest": proposal.evidence_digest,
            "winning_variant": proposal.winning_variant}


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("observations", type=Path)
    ap.add_argument("--canary", action="store_true",
                    help="check whether the proposal clears the canary gate")
    ap.add_argument("--passed-batches", type=int, default=0)
    ap.add_argument("--rollback-ready", action="store_true")
    a = ap.parse_args(argv)
    if a.canary:
        doc = canary(a.observations, a.passed_batches, a.rollback_ready)
        print(json.dumps(doc, indent=2))
        return 0 if doc["approved"] else 1
    doc = propose(a.observations)
    print(f"[learning] {doc['status']}"
          + (f" winner={doc['winning_variant']}" if doc["winning_variant"]
             else "")
          + (f" blockers={doc['blockers']}" if doc["blockers"] else "")
          + " -> output/learning_proposal.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
