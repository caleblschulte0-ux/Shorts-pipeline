# Curiosity Next-Generation Prototypes

This directory contains **real but dormant code** for Claude to inspect, test, refine, and selectively integrate later.

## Isolation contract

Nothing in the active pipeline imports this package. This directory does not modify workflows, configuration, scheduling, publishing, rendering, story data, or CI. All modules use the Python standard library only.

## Included prototypes

### Artifact and release integrity

- `artifact_manifest.py` — SHA-256 package manifests and report binding.
- `package_readiness.py` — fail-closed aggregation of manifest, facts, judge, fallback, performance, catalog, technical, and channel gates.
- `approval_token.py` — one-time HMAC-signed approvals bound to one manifest, one channel, one expiry window, and one upload.
- `freeze_controller.py` — fail-closed release state machine with automatic freezing and mandatory post-canary refreeze.

### Editorial quality and repair

- `quality.py` — weighted quality decisions with mandatory hard floors.
- `repair_planner.py` — defect-specific repair selection, priority ordering, two-round limits, and human re-author escalation.
- `repetition_ledger.py` — cross-video hook, closing, transition, character-action, visual-family, and asset-reuse controls.

### Facts and media

- `claim_registry.py` — factual-mode enforcement, claim-signal detection, source requirements, and beat-level coverage.
- `semantic_claims.py` — sentence-level factual assertions, confidence scoring, type compatibility, duplicate IDs, and overbroad mapping detection.
- `media_ranker.py` — auditable candidate ranking and hard rejection rules.

### Visual-judge control plane

- `judge_contract.py` — hash-bound verdict validation and multi-judge consensus.
- `judge_evidence.py` — blind judge evidence-package completeness, hash binding, duration, media-type, and information-leak checks.
- `judge_orchestrator.py` — independent technical/editorial/tiebreaker assignment across distinct provider and model families.

### Performance and catalog control

- `shot_cache.py` — deterministic cache keys and selective repair planning.
- `render_budget.py` — draft, review, and production render estimates with time, memory, and cache-reuse budgets.
- `render_scheduler.py` — value-per-cost queue planning with time, slot, readiness, profile, and topic-family constraints.
- `story_catalog.py` — explicit story lifecycle and scheduler eligibility.
- `catalog_triage.py` — story readiness scoring, deterministic next actions, blocker severity, and repair-budget handling.

### Orchestration and operations

- `integration_lab.py` — isolated end-to-end simulation from claims and evidence through gates, package readiness, and release freeze decisions.
- `observability.py` — append-only event ledger, duplicate detection, run summaries, pass/hold/quarantine rates, p95 duration, and reason aggregation.
- `pipeline_status.py` — weighted implementation, evidence, readiness, blocker, and priority scoring.

### Learning

- `experiment_attribution.py` — controlled rate experiments with sample-size, statistical, effect-size, and guardrail decisions.

### Tests

- `tests/test_prototypes.py` — foundational prototype contracts.
- `tests/test_decision_intelligence.py` — decision-layer contracts.
- `tests/test_structural_hardening.py` — factual, evidence, judge independence, catalog, scheduling, approval, freeze, observability, and integration negative controls.

## Run locally

```bash
python -m unittest discover experiments/curiosity_nextgen/tests
```

The tests are intentionally not connected to the repository's active CI. This keeps the experiment package from affecting current production checks. A future integration PR should run the selected module's tests in an isolated job before any production import is added.

## Adoption rule

Claude should not import these modules into production wholesale. Review each contract, adapt it to the real renderer and artifacts, add production-specific tests and negative controls, and integrate one capability per focused PR.
