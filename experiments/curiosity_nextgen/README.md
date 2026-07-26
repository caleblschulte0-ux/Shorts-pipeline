# Curiosity Next-Generation Prototypes

This directory contains **real but dormant code** for Claude to inspect, test, refine, and selectively integrate later.

## Isolation contract

Nothing in the active pipeline imports this package. This directory does not modify workflows, configuration, scheduling, publishing, rendering, story data, or CI. All modules use the Python standard library only.

## Included prototypes

### Artifact and release integrity

- `artifact_manifest.py` — SHA-256 package manifests and report binding.
- `package_readiness.py` — fail-closed aggregation of manifest, facts, judge, fallback, performance, catalog, technical, and channel gates.
- `judge_contract.py` — hash-bound verdict validation and multi-judge consensus.

### Editorial quality and repair

- `quality.py` — weighted quality decisions with mandatory hard floors.
- `repair_planner.py` — defect-specific repair selection, priority ordering, two-round limits, and human re-author escalation.
- `repetition_ledger.py` — cross-video hook, closing, transition, character-action, visual-family, and asset-reuse controls.

### Facts and media

- `claim_registry.py` — factual-mode enforcement, semantic claim-signal detection, source requirements, and beat-level coverage.
- `media_ranker.py` — auditable candidate ranking and hard rejection rules.

### Performance and catalog control

- `shot_cache.py` — deterministic cache keys and selective repair planning.
- `render_budget.py` — draft, review, and production render estimates with time, memory, and cache-reuse budgets.
- `story_catalog.py` — explicit story lifecycle and scheduler eligibility.

### Learning and management

- `experiment_attribution.py` — controlled rate experiments with sample-size, statistical, effect-size, and guardrail decisions.
- `pipeline_status.py` — weighted implementation, evidence, readiness, blocker, and priority scoring.
- `tests/` — isolated contract tests for all prototypes.

## Run locally

```bash
python -m unittest discover experiments/curiosity_nextgen/tests
```

The tests are intentionally not connected to the repository's active CI. This keeps the experiment package from affecting current production checks. A future integration PR should run the selected module's tests in an isolated job before any production import is added.

## Adoption rule

Claude should not import these modules into production wholesale. Review each contract, adapt it to the real renderer and artifacts, add production-specific tests and negative controls, and integrate one capability per focused PR.
