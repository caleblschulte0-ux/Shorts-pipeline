#!/usr/bin/env python3
"""Tests for the learning-proposal tool: a genuine lift clears the guardrails
into canary_required; thin evidence / regressions / oversized deltas HOLD;
the canary gate refuses until batches pass with rollback ready."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO / "scripts", REPO / "experiments"):
    sys.path.insert(0, str(p))

import learning_proposals as lp  # noqa: E402
import run_ledger  # noqa: E402


def _obs(variant, story, watch, complete, neg=0.002, impressions=2000):
    return {"story_id": story, "experiment_id": "exp-hook-1",
            "variant": variant, "policy_version": "v1",
            "impressions": impressions, "average_watch_ratio": watch,
            "completion_rate": complete, "negative_feedback_rate": neg}


def _write(d, doc):
    f = Path(d) / "obs.json"
    f.write_text(json.dumps(doc))
    return f


def _good_doc():
    return {"experiment_id": "exp-hook-1", "control_variant": "control",
            "candidate_parameters": {"hook_seconds_delta": 0.08},
            "observations":
            [_obs("control", f"s{i}", 0.42, 0.30) for i in range(5)]
            + [_obs("treatment", f"t{i}", 0.47, 0.35) for i in range(5)]}


def main():
    real_ledger = run_ledger.LEDGER_PATH
    with tempfile.TemporaryDirectory() as d:
        run_ledger.LEDGER_PATH = Path(d) / "ledger.jsonl"
        try:
            # 1. genuine lift -> canary_required with evidence digest
            doc = lp.propose(_write(d, _good_doc()))
            assert doc["status"] == "canary_required", doc
            assert doc["winning_variant"] == "treatment"
            assert doc["evidence_digest"] and doc["blockers"] == []
            print("ok  1. genuine lift proposes, sha256-bound to evidence")

            # 2. insufficient impressions HOLDS
            weak = _good_doc()
            for o in weak["observations"]:
                o["impressions"] = 100
            doc = lp.propose(_write(d, weak))
            assert doc["status"] == "hold"
            assert "insufficient_total_impressions" in doc["blockers"], doc
            print("ok  2. thin evidence holds")

            # 3. negative-feedback regression HOLDS
            bad = _good_doc()
            for o in bad["observations"]:
                if o["variant"] == "treatment":
                    o["negative_feedback_rate"] = 0.02
            doc = lp.propose(_write(d, bad))
            assert doc["status"] == "hold", doc
            print("ok  3. negative-feedback regression blocks the winner")

            # 4. oversized parameter delta HOLDS even with a real lift
            big = _good_doc()
            big["candidate_parameters"] = {"hook_seconds_delta": 0.5}
            doc = lp.propose(_write(d, big))
            assert doc["status"] == "hold"
            assert any("parameter_delta_exceeds_limit" in b
                       for b in doc["blockers"]), doc
            print("ok  4. unbounded policy step is refused")

            # 5. canary gate: refuses early, approves only when earned
            f = _write(d, _good_doc())
            c = lp.canary(f, passed_batches=1, rollback_ready=True)
            assert not c["approved"] and \
                "insufficient_canary_batches" in c["blockers"]
            c = lp.canary(f, passed_batches=2, rollback_ready=False)
            assert not c["approved"] and \
                "rollback_not_ready" in c["blockers"]
            c = lp.canary(f, passed_batches=2, rollback_ready=True)
            assert c["approved"] and not c["blockers"], c
            print("ok  5. canary refuses until batches pass AND rollback is "
                  "ready")

            # 6. proposals land in the run ledger (auditable trail)
            events = [json.loads(l) for l in
                      run_ledger.LEDGER_PATH.read_text().splitlines()]
            assert any(e["event_type"] == "learning_proposal"
                       for e in events)
            print("ok  6. every proposal is ledgered")
        finally:
            run_ledger.LEDGER_PATH = real_ledger

    print("learning proposals: 6/6 tests pass")


if __name__ == "__main__":
    main()
