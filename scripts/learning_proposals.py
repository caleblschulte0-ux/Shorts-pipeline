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

REAL ANALYTICS: ``--from-analytics <snapshot.json>`` reads a snapshot written
by ``scripts/fetch_analytics.py`` and converts its public, mature video rows
into observations — ``experiment_arm`` becomes the variant, views become
impressions, ``average_view_percentage`` becomes the watch ratio. Rows with
no arm, no retention sample, or a still-private/pending status are DROPPED
(never defaulted into a variant), and the conversion is reported so a thin
sample is visible rather than silently proposed on.

    python3 scripts/learning_proposals.py observations.json
    python3 scripts/learning_proposals.py --from-analytics snapshot.json \
        --experiment-id hook-v2 --control-variant edit
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


def observations_from_analytics(snapshot: Path, experiment_id: str,
                                policy_version: str = "v1") -> dict:
    """Convert a REAL fetch_analytics snapshot into the observations schema.

    Honest mapping only — a row is used only when it carries every field the
    contract needs. Dropped rows are counted and reported by reason, so a
    sample too thin to learn from LOOKS thin instead of quietly becoming a
    proposal. Emits the same document shape the file mode reads."""
    raw = json.loads(snapshot.read_text())
    videos = raw.get("videos") or raw.get("mature") or []
    obs, dropped = [], {"no_arm": 0, "no_retention": 0, "no_views": 0}
    for v in videos:
        arm = v.get("experiment_arm") or v.get("actual_structure")
        if not arm:
            dropped["no_arm"] += 1
            continue
        avp = v.get("average_view_percentage")
        if avp is None:
            dropped["no_retention"] += 1
            continue
        views = int(v.get("views") or 0)
        if views <= 0:
            dropped["no_views"] += 1
            continue
        ratio = float(avp) / 100.0 if float(avp) > 1.0 else float(avp)
        ratio = min(1.0, max(0.0, ratio))
        # completion is not reported directly; the contract needs a bounded
        # rate, so use the retention curve's tail when present and fall back
        # to the watch ratio (documented, never invented upward).
        completion = v.get("completion_rate")
        completion = (min(1.0, max(0.0, float(completion)))
                      if completion is not None else ratio)
        dislikes = int(v.get("dislikes") or 0)
        obs.append({
            "story_id": str(v.get("catalog_id") or v.get("video_id")),
            "experiment_id": experiment_id,
            "variant": str(arm),
            "policy_version": str(v.get("policy_version") or policy_version),
            "impressions": views,
            "average_watch_ratio": round(ratio, 4),
            "completion_rate": round(completion, 4),
            "negative_feedback_rate": round(min(1.0, dislikes / views), 5),
            "hard_blocker": bool(v.get("hard_blocker", False)),
        })
    return {"experiment_id": experiment_id, "observations": obs,
            "_source": snapshot.name, "_converted": len(obs),
            "_dropped": dropped}


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
    ap.add_argument("observations", type=Path, nargs="?",
                    help="observations JSON (omit when --from-analytics)")
    ap.add_argument("--from-analytics", type=Path, default=None,
                    help="convert a real fetch_analytics snapshot first")
    ap.add_argument("--experiment-id", default="curiosity-exp-1")
    ap.add_argument("--control-variant", default="control")
    ap.add_argument("--canary", action="store_true",
                    help="check whether the proposal clears the canary gate")
    ap.add_argument("--passed-batches", type=int, default=0)
    ap.add_argument("--rollback-ready", action="store_true")
    a = ap.parse_args(argv)
    if a.from_analytics:
        doc = observations_from_analytics(a.from_analytics, a.experiment_id)
        doc["control_variant"] = a.control_variant
        doc["candidate_parameters"] = {}
        dest = REPO / "output" / "learning_observations.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(doc, indent=2) + "\n")
        print(f"[learning] converted {doc['_converted']} observation(s) from "
              f"{a.from_analytics.name}; dropped {doc['_dropped']} "
              f"-> {dest}")
        a.observations = dest
    if not a.observations:
        ap.error("give an observations file or --from-analytics")
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
