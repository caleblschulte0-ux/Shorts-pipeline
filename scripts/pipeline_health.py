#!/usr/bin/env python3
"""PIPELINE HEALTH — the nextgen observability cluster over REAL state.

Two views, both from artifacts on disk (never from printed logs):

1. RUN HEALTH (curiosity_nextgen.observability): the hash-chained run ledger
   (state/curiosity_run_ledger.jsonl) is verified, then mapped into
   PipelineEvents — one run per ``run_started`` per slug — and summarized:
   pass/hold/quarantine/failure rates, stage timings, top refusal reasons.

2. CAPABILITY READINESS (curiosity_nextgen.pipeline_status): an honest,
   versioned table of what the pipeline can actually do, weighted by
   importance and DISCOUNTED by evidence level (documented < prototyped <
   tested < production_proven). The publish path is deliberately capped at
   'tested' until a real gated upload has happened — the score cannot claim
   what production has not proven.

    python3 scripts/pipeline_health.py            -> output/pipeline_status.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts", REPO / "experiments"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from curiosity_nextgen.observability import (      # noqa: E402
    EventLedger, EventSeverity, PipelineEvent, build_health_snapshot,
    summarize_run)
from curiosity_nextgen.pipeline_status import (    # noqa: E402
    CapabilityStatus, EvidenceLevel, summarize_pipeline)

# real ledger event -> (observability event_type, severity); "evaluated"
# resolves by its payload status below.
_EVENT_MAP = {
    "run_started": ("run_started", EventSeverity.INFO),
    "resume_hit": ("resume_hit", EventSeverity.INFO),
    "resume_miss": ("resume_miss", EventSeverity.INFO),
    "render_completed": ("render_completed", EventSeverity.INFO),
    "render_failed": ("run_failed", EventSeverity.ERROR),
    "batch_started": ("batch_started", EventSeverity.INFO),
    "batch_budget_exhausted": ("run_held", EventSeverity.WARNING),
    "batch_story_done": ("batch_story_done", EventSeverity.INFO),
}


def _map_event(row: dict, run_id: str) -> PipelineEvent:
    etype, sev = _EVENT_MAP.get(row.get("event_type", ""),
                                (row.get("event_type", "unknown"),
                                 EventSeverity.INFO))
    payload = row.get("payload") or {}
    reason = None
    if row.get("event_type") == "evaluated":
        status = payload.get("status")
        etype = {"pass": "run_passed",
                 "quarantine": "run_quarantined"}.get(status, "evaluated")
        sev = (EventSeverity.WARNING if status == "quarantine"
               else EventSeverity.INFO)
        reasons = payload.get("reasons") or []
        reason = str(reasons[0])[:120] if reasons else None
    elif row.get("event_type") == "render_failed":
        reason = str(payload.get("detail", ""))[:120] or None
    elif row.get("event_type") == "batch_story_done":
        if payload.get("status") != "pass":
            etype, sev = "run_quarantined", EventSeverity.WARNING
        else:
            etype = "run_passed"
    dur = payload.get("elapsed_s")
    return PipelineEvent(
        event_id=f"{row.get('sequence')}-{str(row.get('event_hash'))[:8]}",
        run_id=run_id,
        slug=str(row.get("slug", "")),
        stage=str(row.get("event_type", "unknown")),
        event_type=etype,
        severity=sev,
        timestamp=str(row.get("at")),
        duration_seconds=float(dur) if isinstance(dur, (int, float))
        and dur >= 0 else None,
        reason=reason,
    )


def load_events(path: Path | None = None) -> tuple[EventLedger, dict]:
    """Verify the hash chain, then group ledger rows into runs — a new run_id
    every time a slug sees ``run_started``/``batch_started``."""
    import run_ledger
    path = path or run_ledger.LEDGER_PATH
    chain_ok, chain_err = run_ledger.verify_chain(path)
    rows = [] if not path.exists() else [
        json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    counters: dict[str, int] = {}
    ledger = EventLedger()
    for row in rows:
        slug = str(row.get("slug", ""))
        if row.get("event_type") in ("run_started", "batch_started"):
            counters[slug] = counters.get(slug, 0) + 1
        run_id = f"{slug}/r{counters.get(slug, 0)}"
        try:
            ledger.append(_map_event(row, run_id))
        except ValueError:
            pass                     # duplicate ids counted by the ledger
    return ledger, {"chain_ok": chain_ok, "chain_error": chain_err,
                    "raw_rows": len(rows)}


# The honest capability table. Weights = how much each matters to the goal;
# evidence NEVER exceeds what artifacts on disk actually demonstrate.
CAPABILITIES = (
    ("canonical_producer", 10, 100, EvidenceLevel.PRODUCTION_PROVEN, True),
    ("director_loop_autorepair", 9, 100, EvidenceLevel.PRODUCTION_PROVEN, True),
    ("blind_taste_judge", 9, 100, EvidenceLevel.PRODUCTION_PROVEN, True),
    ("facts_gate_numeric", 7, 100, EvidenceLevel.PRODUCTION_PROVEN, True),
    ("facts_gate_semantic", 6, 100, EvidenceLevel.TESTED, False),
    ("artifact_identity_manifests", 8, 100, EvidenceLevel.TESTED, True),
    ("run_ledger_durability", 6, 100, EvidenceLevel.TESTED, False),
    ("publish_guards_approval_kill", 9, 100, EvidenceLevel.TESTED, True),
    ("publish_security_scan", 6, 100, EvidenceLevel.TESTED, False),
    ("media_context_guard", 6, 100, EvidenceLevel.TESTED, False),
    ("provider_routing", 4, 100, EvidenceLevel.TESTED, False),
    ("batch_autonomy_layer", 6, 100, EvidenceLevel.TESTED, False),
    ("story_advisor", 3, 100, EvidenceLevel.PROTOTYPED, False),
    ("learning_loop_controlled", 4, 60, EvidenceLevel.PROTOTYPED, False),
    ("real_upload_end_to_end", 8, 100, EvidenceLevel.DOCUMENTED, False),
)


def status() -> dict:
    ledger, meta = load_events()
    snap = build_health_snapshot(ledger)
    runs = []
    for rid in sorted({e.run_id for e in ledger.events}):
        r = summarize_run(ledger.by_run(rid))
        runs.append({"run": rid, "slug": r.slug, "outcome": r.outcome.value,
                     "max_severity": r.maximum_severity.value,
                     "events": r.event_count,
                     "reasons": list(r.reasons)[:3]})
    caps = [CapabilityStatus(n, w, impl, ev, blocking)
            for n, w, impl, ev, blocking in CAPABILITIES]
    pipe = summarize_pipeline(caps)
    doc = {
        "ledger": meta,
        "health": {
            "runs": snap.run_count,
            "pass_rate": snap.pass_rate,
            "quarantine_rate": snap.quarantine_rate,
            "failure_rate": snap.failure_rate,
            "hold_rate": snap.hold_rate,
            "top_reasons": [list(x) for x in snap.top_reasons],
            "critical_events": snap.critical_event_count,
        },
        "recent_runs": runs[-12:],
        "capabilities": {
            "implementation_score": pipe.implementation_score,
            "evidence_score": pipe.evidence_score,
            "weighted_readiness": pipe.weighted_readiness,
            "blocking_gaps": list(pipe.blocking_gaps),
            "next_priorities": list(pipe.next_priorities),
            "table": [{"capability": c.capability, "weight": c.target_weight,
                       "evidence": c.evidence.value,
                       "earned": round(c.earned, 2)} for c in caps],
        },
    }
    dest = REPO / "output" / "pipeline_status.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2) + "\n")
    return doc


def main(argv) -> int:
    doc = status()
    h, c = doc["health"], doc["capabilities"]
    print(f"[health] chain_ok={doc['ledger']['chain_ok']} "
          f"runs={h['runs']} pass={h['pass_rate']}% "
          f"quarantine={h['quarantine_rate']}% fail={h['failure_rate']}%")
    print(f"[capabilities] implementation={c['implementation_score']} "
          f"evidence={c['evidence_score']} "
          f"weighted_readiness={c['weighted_readiness']}")
    print(f"[next] {', '.join(c['next_priorities'][:3])} "
          f"-> output/pipeline_status.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
