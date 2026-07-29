#!/usr/bin/env python3
"""WIRING GUARD — every adopted capability must have a REAL production call
site, not just a passing unit test.

This is the regression test for "it exists but nothing calls it". It asserts
the call graph itself: which module is imported by which production consumer,
and — where order is a safety property — that the call happens at the right
point (a leak scan after the publish hold would never run in the only mode
that runs today). Cheap, deterministic, no rendering.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def src(rel: str) -> str:
    return (REPO / rel).read_text()


def line_of(text: str, needle: str, label: str) -> int:
    for i, line in enumerate(text.splitlines()):
        if needle in line:
            return i
    raise AssertionError(f"{label}: never found {needle!r}")


def main():
    produce = src("scripts/produce.py")
    post = src("scripts/post_curiosity.py")
    media = src("data_learning/media.py")
    facts = src("scripts/facts_gate.py")
    batch = src("scripts/batch_produce.py")
    ci = src(".github/workflows/curiosity-ci.yml")
    wf = src(".github/workflows/curiosity.yml")

    # 1. the canonical producer wires identity, ledger, facts, and advisory
    for needle, why in (
            ("import artifact_identity", "package identity/manifest"),
            ("import run_ledger", "durable run ledger"),
            ("import facts_gate", "provenance gate"),
            ("import story_advisor", "advisory craft report")):
        assert needle in produce, f"produce.py does not wire {why}"
    assert "build_manifest" in produce and "advisor.json" in produce
    print("ok  1. producer wires identity + ledger + facts + advisor")

    # 2. the publish path wires kill switch, approval, and the security scan
    for needle, why in (("import approve_publish", "kill switch + approval"),
                        ("import publish_security", "payload leak scan")):
        assert needle in post, f"post_curiosity.py does not wire {why}"
    print("ok  2. publish path wires approval, kill switch, security scan")

    # 3. ORDER: the security scan must run as a GATE, before the publish hold.
    # After the hold it would never execute while publishing is frozen — the
    # exact bug this guard exists to prevent from returning.
    scan_gate = line_of(post, "sec_ok, sec_reasons = publish_security.scan_upload",
                        "security gate")
    hold = line_of(post, "publish_enabled = os.environ.get", "publish hold")
    assert scan_gate < hold, (
        f"security scan (line {scan_gate + 1}) runs AFTER the publish hold "
        f"(line {hold + 1}) — dry runs would never scan the payload")
    # and it must feed the gate, so a leak marks the story publish-ineligible
    assert "gate_reasons.extend(sec_reasons)" in post
    print("ok  3. security scan gates BEFORE the hold and feeds gate_reasons")

    # 4. media acquisition consults the router and the context guard
    assert "from data_learning.provider_routing import maybe_route" in media
    assert "from data_learning.media_context import BREAKER" in media
    print("ok  4. media gateway wires provider routing + breaker")

    # 5. the facts gate carries the semantic layer
    assert "_semantic_audit" in facts and "require_semantic_provenance" in facts
    print("ok  5. facts gate carries the semantic claim layer")

    # 6. the batch layer drives the CANONICAL producer and reports health
    assert "produce.produce(" in batch, "batch must drive the real producer"
    assert "import pipeline_health" in batch
    print("ok  6. batch drives the canonical producer and reports health")

    # 7. the production workflow exposes batch mode and emits status
    assert re.search(r"options:.*batch\]", wf), "curiosity.yml lacks batch mode"
    assert "scripts/batch_produce.py --run" in wf
    assert "scripts/pipeline_health.py" in wf
    assert "output/pipeline_status.json" in wf, "status is never uploaded"
    # batch mode must NOT publish
    batch_arm = wf.split("            batch)")[1].split("            auto)")[0]
    # no INVOCATION of the publisher (prose mentioning it is fine)
    invokes_publisher = [l for l in batch_arm.splitlines()
                         if re.search(r"python\S*\s+\S*post_curiosity", l)]
    assert not invokes_publisher, \
        f"batch mode must never reach the publisher: {invokes_publisher}"
    print("ok  7. workflow exposes batch mode (non-publishing) + status artifact")

    # 8. CI actually runs every adapter suite + the drill
    for suite in ("test_batch_produce", "test_story_advisor",
                  "test_publish_security", "test_provider_routing",
                  "test_pipeline_health", "test_learning_proposals",
                  "simulate_pipeline", "test_production_wiring"):
        assert suite in ci, f"CI does not run {suite}.py"
    print("ok  8. CI runs every adapter suite, the drill, and this guard")

    print("production wiring: 8/8 checks pass")


if __name__ == "__main__":
    sys.exit(main())
