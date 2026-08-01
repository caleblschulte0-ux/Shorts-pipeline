#!/usr/bin/env python3
"""BATCH PRODUCER — the nextgen autonomy layer wired to the REAL pipeline.

Adapters for the merged reference surface (experiments/curiosity_nextgen):
portfolio admission, idea funnel, bounded batch execution, and batch
acceptance — all operating on the actual story catalog
(data_learning/pro_stories/*.beats.json) and the actual canonical producer
(scripts/produce.py). Story slugs are OPAQUE identifiers throughout: nothing
here selects behavior by story identity.

Modes:
  --plan            admission plan over the real catalog (no rendering)
  --ideas FILE      score a raw-ideas JSON through the idea funnel
  --status          batch-acceptance report over EXISTING produce reports
  --run             bounded real batch: render+gate each admitted story via
                    produce.produce, decide per-story via the decision engine,
                    stop on budget/count, then evaluate acceptance
Publishing is UNTOUCHED: this layer renders and gates only; upload still
requires post_curiosity + CURIOSITY_PUBLISH_ENABLED + approval + kill switch.

Every mode writes a machine-readable report under output/.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts", REPO / "experiments"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from curiosity_nextgen.autonomous_decision_engine import (   # noqa: E402
    NextAction, StageName, StageOutcome, StageVerdict, StoryDecisionState,
    decide_next_action)
from curiosity_nextgen.batch_acceptance import (             # noqa: E402
    BatchAcceptancePolicy, StoryAcceptance, evaluate_batch_acceptance)
from curiosity_nextgen.idea_funnel import (                  # noqa: E402
    IdeaCandidate, IdeaFunnelPolicy, run_idea_funnel)
from curiosity_nextgen.portfolio_optimizer import (          # noqa: E402
    PortfolioPolicy, StoryCandidate, build_portfolio)

PRO_STORIES = REPO / "data_learning" / "pro_stories"
OUTPUT = REPO / "output"


# ---------------------------------------------------------------- real catalog
def load_catalog(include_controls: bool = False) -> dict[str, dict]:
    """Every real pro story on disk, slug -> story dict. Fixtures and the
    negative-control stories are excluded from production batches by default
    (controls exist to be quarantined, not produced)."""
    out: dict[str, dict] = {}
    for p in sorted(PRO_STORIES.glob("*.beats.json")):
        try:
            story = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        slug = story.get("slug") or p.stem.replace(".beats", "")
        if not include_controls and (slug.endswith("-weak")
                                     or slug.startswith("zz-")):
            continue
        story["_path"] = str(p)
        out[slug] = story
    return out


def _mechanical_readiness(story: dict) -> tuple[float, bool, list[str]]:
    """Readiness from MECHANICAL facts only (never taste, never identity):
    beats present and well-formed, provenance registry present when required,
    media context declared, narration on every beat. Returns
    (score 0-100, blocked, notes)."""
    notes: list[str] = []
    beats = story.get("beats", [])
    score, blocked = 100.0, False
    if not beats:
        return 0.0, True, ["no beats"]
    missing_narr = sum(1 for b in beats if not (b.get("narration") or b.get("line")))
    if missing_narr:
        score -= 25
        notes.append(f"{missing_narr} beat(s) without narration")
    if story.get("require_provenance"):
        reg = Path(story["_path"]).with_name(
            Path(story["_path"]).name.replace(".beats.json", ".facts.json"))
        if not reg.exists():
            blocked = True
            notes.append("require_provenance without a facts registry (blocked)")
    if not story.get("media_context"):
        score -= 10
        notes.append("no media_context declared")
    if not 5 <= len(beats) <= 40:
        score -= 15
        notes.append(f"beat count {len(beats)} outside 5-40")
    return max(score, 0.0), blocked, notes


def plan(max_stories: int = 50) -> dict:
    catalog = load_catalog()
    cands = []
    for slug, story in catalog.items():
        readiness, blocked, notes = _mechanical_readiness(story)
        cands.append(StoryCandidate(
            slug=slug,
            topic_family=str(story.get("pillar") or story.get("topic_family")
                             or "general"),
            emotional_tone=str(story.get("tone") or "curious"),
            visual_family=str(story.get("visual_family") or "mixed"),
            factual_complexity=3 if story.get("require_provenance") else 1,
            estimated_cost=1.0,
            readiness_score=readiness,
            novelty_score=0.5,
            audience_value=0.5,
            blocked=blocked,
        ))
    sel = build_portfolio(tuple(cands), PortfolioPolicy(
        maximum_stories=min(max_stories, max(1, len(cands))),
        maximum_total_cost=float(max_stories),
        maximum_per_topic_family=max(1, max_stories // 2),
        maximum_per_visual_family=max(1, max_stories // 2)))
    report = {
        "mode": "plan",
        "admitted": [c.slug for c in sel.selected],
        "deferred": [{"slug": s, "reason": r} for s, r in sel.deferred],
        "valid": sel.valid,
        "blockers": list(sel.blockers),
    }
    _write(report, "batch_plan.json")
    return report


# ----------------------------------------------------------------- idea funnel
def ideas(path: Path) -> dict:
    raw = json.loads(path.read_text())
    cands = [IdeaCandidate(**item) for item in raw.get("ideas", raw)]
    res = run_idea_funnel(cands, IdeaFunnelPolicy(
        minimum_exploration_slots=0,
        minimum_sources=raw.get("minimum_sources", 1)
        if isinstance(raw, dict) else 1))
    report = {
        "mode": "ideas",
        "selected": [c.candidate_id for c in res.selected],
        "rejected": [{"id": i, "reason": r} for i, r in res.rejected],
        "valid": res.valid,
    }
    _write(report, "idea_funnel_report.json")
    return report


# ------------------------------------------------------------- acceptance view
def acceptance_from_disk(slugs: list[str] | None = None) -> dict:
    """Map the REAL on-disk evidence (produce_report, verdict, manifest,
    facts-report) into the batch-acceptance contract. No rendering."""
    import artifact_identity as ai
    catalog = load_catalog(include_controls=True)
    rows = []
    for slug, story in catalog.items():
        if slugs and slug not in slugs:
            continue
        out = OUTPUT / f"curiosity_{slug}.mp4"
        pkg = OUTPUT / f"curiosity_{slug}_pkg"
        rep = _read(pkg / "produce_report.json") or {}
        verdict = _read(pkg / "verdict.json") or {}
        facts = _read(out.with_suffix(".facts-report.json")) or {}
        manifest_ok, _ = ai.verify_manifest(out, story_path=Path(story["_path"]))
        status = rep.get("status")
        if status is None:
            continue                       # never produced — not part of a batch
        rows.append(StoryAcceptance(
            story_id=slug,
            topic_family=str(story.get("pillar") or "general"),
            format_family=str(story.get("visual_family") or "mixed"),
            completed=status == "pass",
            quarantined=status != "pass",
            quality_score=(float(verdict["overall_10"])
                           if verdict.get("overall_10") is not None else None),
            artifact_hash_bound=manifest_ok,
            factual_evidence_complete=bool(facts.get("pass", True)),
            technical_pass=status == "pass",
            editorial_pass=bool(verdict.get("pass")),
            hard_blockers=tuple(rep.get("reasons", []))[:4],
        ))
    if not rows:
        report = {"mode": "status", "note": "no produced stories on disk yet",
                  "decision": "empty"}
        _write(report, "batch_acceptance.json")
        return report
    # Current-scale policy: the strict 50-story launch defaults (0.8
    # completion, 4 topic families, quality>=7.5) describe the TARGET batch;
    # today's catalog is a handful of stories, so the status view reports
    # against a reachable floor and the strict launch policy side by side.
    n = len(rows)
    lenient = BatchAcceptancePolicy(
        minimum_completion_rate=0.0, maximum_quarantine_rate=1.0,
        minimum_quality_score=0.0, minimum_topic_families=1,
        minimum_format_families=1, maximum_hook_family_share=1.0,
        maximum_visual_family_share=1.0, require_hash_binding=False,
        require_factual_evidence=False)
    res = evaluate_batch_acceptance(rows, lenient)
    strict = evaluate_batch_acceptance(rows, BatchAcceptancePolicy())
    report = {
        "mode": "status",
        "decision": res.decision.value,
        "stories": {r.story_id: ("pass" if r.completed else "quarantine")
                    for r in rows},
        "blockers": list(res.blockers),
        "warnings": list(res.warnings)[:8],
        "launch_policy_decision": strict.decision.value,
        "launch_policy_blockers": list(strict.blockers)[:8],
        "completed": sum(r.completed for r in rows),
        "quarantined": sum(r.quarantined for r in rows),
    }
    _write(report, "batch_acceptance.json")
    return report


# --------------------------------------------------------------- bounded batch
def run_batch(slugs: list[str] | None, max_stories: int,
              budget_seconds: float, fresh: bool = False) -> dict:
    """Render+gate each admitted story through the CANONICAL producer, one at a
    time (single-worker), bounded by story count and wall-clock budget. Each
    result feeds the decision engine; PASS advances, anything else quarantines
    (produce already embeds the bounded retry/repair rounds internally)."""
    import produce
    import run_ledger
    admitted = slugs or plan(max_stories)["admitted"]
    admitted = admitted[:max_stories]
    started = time.monotonic()
    results, decisions = {}, {}
    run_ledger.append("batch_started", "batch",
                      {"admitted": admitted, "budget_s": budget_seconds})
    for slug in admitted:
        elapsed = time.monotonic() - started
        if elapsed > budget_seconds:
            run_ledger.append("batch_budget_exhausted", "batch",
                              {"elapsed_s": round(elapsed, 1)})
            decisions[slug] = "deferred:budget_exhausted"
            continue
        res = produce.produce(slug, OUTPUT / f"curiosity_{slug}.mp4",
                              fresh=fresh)
        results[slug] = res["status"]
        outcome = StageOutcome(
            story_id=slug, stage=StageName.FINAL_RENDER,
            verdict=(StageVerdict.PASS if res["status"] == "pass"
                     else StageVerdict.FAIL),
            severity=0.0 if res["status"] == "pass" else 5.0,
            confidence=9.0, repairable=False,
            evidence_complete=True, artifact_hash_bound=True)
        d = decide_next_action(outcome, StoryDecisionState())
        decisions[slug] = d.action.value
        run_ledger.append("batch_story_done", slug,
                          {"status": res["status"], "decision": d.action.value})
    report = {"mode": "run", "results": results, "decisions": decisions,
              "elapsed_s": round(time.monotonic() - started, 1)}
    _write(report, "batch_run_report.json")
    acceptance_from_disk(list(results))
    # Refresh the run-health + capability view from the ledger this batch just
    # extended, so every batch leaves a current status artifact behind.
    try:
        import pipeline_health
        h = pipeline_health.status()["health"]
        print(f"[batch] health: {h['runs']} runs, pass={h['pass_rate']}% "
              f"quarantine={h['quarantine_rate']}%")
    except Exception as e:  # noqa: BLE001 — reporting must not fail a batch
        print(f"[batch] health report skipped ({str(e)[:70]})")
    return report


# ------------------------------------------------------------------- plumbing
def _read(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _write(report: dict, name: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(json.dumps(report, indent=2) + "\n")
    print(f"[batch] {report.get('mode')} -> output/{name}")


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--ideas", type=Path)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--slugs", nargs="*")
    ap.add_argument("--max-stories", type=int, default=50)
    ap.add_argument("--budget-seconds", type=float, default=6 * 3600)
    ap.add_argument("--fresh", action="store_true")
    a = ap.parse_args(argv)
    if a.ideas:
        r = ideas(a.ideas)
    elif a.run:
        r = run_batch(a.slugs, a.max_stories, a.budget_seconds, fresh=a.fresh)
    elif a.status:
        r = acceptance_from_disk(a.slugs)
    else:
        r = plan(a.max_stories)
    print(json.dumps(r, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
