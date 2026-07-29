#!/usr/bin/env python3
"""Tests for pipeline health: real-ledger mapping (runs, outcomes, reasons),
chain verification surfacing, empty-state behavior, and the honesty rule
that capability evidence discounts the readiness score."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO / "scripts", REPO / "experiments"):
    sys.path.insert(0, str(p))

import pipeline_health as ph  # noqa: E402
import run_ledger  # noqa: E402


def main():
    with tempfile.TemporaryDirectory() as d:
        lp = Path(d) / "ledger.jsonl"

        # empty ledger: verifies trivially, zero runs
        ledger, meta = ph.load_events(lp)
        assert meta["chain_ok"] and meta["raw_rows"] == 0
        assert not ledger.events
        print("ok  1. empty ledger -> clean empty snapshot")

        # a real produce cycle: started -> render -> evaluated pass
        run_ledger.append("run_started", "s1", {"rounds": 2}, path=lp)
        run_ledger.append("render_completed", "s1", {"director_rc": 0},
                          path=lp)
        run_ledger.append("evaluated", "s1", {"status": "pass"}, path=lp)
        # a quarantine cycle with a reason
        run_ledger.append("run_started", "s2", {}, path=lp)
        run_ledger.append("evaluated", "s2",
                          {"status": "quarantine",
                           "reasons": ["taste REJECT: cards over budget"]},
                          path=lp)
        # a crash cycle
        run_ledger.append("run_started", "s3", {}, path=lp)
        run_ledger.append("render_failed", "s3", {"detail": "boom"}, path=lp)

        ledger, meta = ph.load_events(lp)
        assert meta["chain_ok"]
        from curiosity_nextgen.observability import (
            build_health_snapshot, summarize_run)
        snap = build_health_snapshot(ledger)
        assert snap.run_count == 3, snap
        assert snap.pass_rate == snap.quarantine_rate == \
            snap.failure_rate == round(100 / 3, 1), snap
        print("ok  2. pass / quarantine / failure runs all inferred")

        r2 = summarize_run(ledger.by_run("s2/r1"))
        assert r2.outcome.value == "quarantine"
        assert any("taste REJECT" in x for x in r2.reasons), r2
        print("ok  3. quarantine reasons surface from the real payload")

        # tampering breaks the chain and is SURFACED, not hidden
        lines = lp.read_text().splitlines()
        lines[2] = lines[2].replace("pass", "hack")
        lp.write_text("\n".join(lines) + "\n")
        _, meta = ph.load_events(lp)
        assert not meta["chain_ok"] and meta["chain_error"], meta
        print("ok  4. tampered ledger surfaces a broken chain")

    # capability honesty: same table with everything production_proven must
    # outscore the honest table — evidence level really discounts the score
    from curiosity_nextgen.pipeline_status import (
        CapabilityStatus, EvidenceLevel, summarize_pipeline)
    honest = summarize_pipeline([
        CapabilityStatus(n, w, i, e, b) for n, w, i, e, b in ph.CAPABILITIES])
    inflated = summarize_pipeline([
        CapabilityStatus(n, w, i, EvidenceLevel.PRODUCTION_PROVEN, b)
        for n, w, i, e, b in ph.CAPABILITIES])
    assert honest.weighted_readiness < inflated.weighted_readiness
    assert "real_upload_end_to_end" in honest.next_priorities
    print("ok  5. evidence honesty discounts readiness; upload gap is the "
          "top priority")

    print("pipeline health: 5/5 tests pass")


if __name__ == "__main__":
    main()
