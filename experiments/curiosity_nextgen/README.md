# Curiosity Next-Generation Prototypes

> **Claude entrypoint:** read `docs/00_CLAUDE_START_HERE.md`, then `docs/CLAUDE_MASTER_PLAYBOOK.md` and `docs/CLAUDE_HANDOFF_MANIFEST.json` before changing code.

This directory contains **real but dormant code** for Claude to inspect, execute, repair, and selectively integrate later.

## Isolation contract

Nothing in the active pipeline imports this package. This directory does not modify workflows, configuration, scheduling, publishing, rendering, story data, or CI. All modules use the Python standard library only.

## Autonomy contract

The system is designed to select, improve, schedule, control, and learn from **up to 50 arbitrary videos**, not optimize named videos through bespoke logic.

- Story IDs are opaque identifiers, never dispatch keys.
- Decisions derive from reusable contracts, evidence, metadata, graph state, policy, providers, and resource state.
- No production-shaped module may contain a named-video blueprint or hard-coded story slug.
- Rules must generalize across topics, formats, durations, audiences, factual risks, emotional tones, and media mixes.
- Every autonomous loop is bounded by retry, repair, re-author, cost, concurrency, provider, evidence, quarantine, canary, and rollback policy.
- Missing or stale evidence must hold or quarantine rather than silently pass.

## Current reference-surface status

- **77 dormant prototype modules**
- **425 authored contract tests** across twelve test files
- **27 required structural domains** in `structural_completeness.py`
- **24 required autonomy domains** in `autonomy_completeness.py`
- **100% authored structural reference coverage**
- **100% authored autonomy reference coverage**
- **0% verified execution coverage claimed** until the isolated suite actually runs successfully
- **0% production integration claimed**
- **0 live launch evidence claimed**
- **0 production imports, workflow changes, renderer changes, or publishing changes**

The package deliberately separates four measurements:

1. authored reference coverage;
2. verified test execution;
3. production integration;
4. live launch evidence.

Only the first measure is complete.

## Closed autonomous operating surface

### Portfolio front door

- `idea_funnel.py` scores and deduplicates raw ideas, enforces evidence and visual feasibility, reserves exploration, controls family concentration, and admits at most 50 stories.
- `story_intake_contract.py` validates heterogeneous story briefs and factual requirements.
- `portfolio_optimizer.py`, `edit_blueprint.py`, and `repetition_ledger.py` control value, cost, diversity, and repetition.

### Execution graph and state

- `production_stage_graph.py` defines the deterministic production DAG.
- `stage_artifact_contract.py` binds every stage output to exact input hashes and schemas.
- `execution_ledger.py` provides append-only events, hash chaining, idempotency, expiring leases, replay, and materialized story state.
- `checkpoint_store.py` and `replay_engine.py` provide recovery and deterministic comparison.

### Autonomous decisions and scheduling

- `autonomous_decision_engine.py` chooses advance, retry, wait, research-more, re-author, repair, or quarantine.
- `autonomous_batch_controller.py` manages diverse active waves, concurrency, attempts, spend, rewinds, holds, and quarantine.
- `autonomous_program.py` coordinates repeatable batch cycles.
- `resource_governor.py`, `render_scheduler.py`, and `render_budget.py` constrain resource use.

### Providers, evidence, and judges

- `provider_pool.py` routes by capability, health, quota, latency, cost, determinism, fallback diversity, and judge independence.
- `adapter_contracts.py` validates provider capability and compatibility.
- `artifact_manifest.py`, `lineage_graph.py`, and `stage_artifact_contract.py` bind exact artifacts.
- `judge_orchestrator.py`, `judge_evidence.py`, and `judge_contract.py` enforce blind independent review.
- `claim_registry.py` and `semantic_claims.py` enforce factual evidence.

### Quality and repair

The creative layers cover hooks, pacing, curiosity, visual grammar, choreography, captions, continuity, readability, audio, packaging, personality, humor, emotion, payoff, retention risk, cognitive load, generic repair, and portfolio-scale edit planning.

### Simulation, acceptance, and learning

- `autonomous_simulator.py` deterministically simulates up to 50 stories with injected transient, factual, repairable, evidence, and fatal faults.
- `batch_acceptance.py` evaluates completion, quarantine, quality, evidence, hash binding, judge passes, and diversity.
- `controlled_learning_loop.py` converts controlled multi-story evidence into bounded, evidence-hashed policy proposals requiring canaries and rollback.
- `launch_readiness.py` separates reference completion from execution, integration, shadow, canary, and launch readiness.
- `autonomy_completeness.py` refuses 100% authored autonomy coverage for any missing, invalid, untested, duplicate, or non-isolated domain.

## Tests

Existing test files cover structural controls, resilience, creative quality, viewer quality, retention quality, autonomous intake/graph/decisioning, and batch control.

The closure sprint adds:

- `tests/test_autonomy_closure.py` — 32 idea, provider, artifact, ledger, lease, idempotency, and 50-story simulation contracts.
- `tests/test_autonomy_launch.py` — 32 controlled-learning, launch-phase, isolation, and strict autonomy-completeness contracts.

## Run locally

```bash
python -m compileall experiments/curiosity_nextgen
python -m unittest discover -v experiments/curiosity_nextgen/tests
```

The tests are intentionally not connected to active CI. This keeps the dormant package from affecting current production checks and releases.

## Adoption rule

The dormant architecture is closed. Do not add another subsystem unless `assess_autonomy_completeness()` proves a real domain is missing.

Next work must execute and fix the suite, validate a heterogeneous 50-story catalog, and selectively integrate one generic capability per focused PR. `docs/CLAUDE_MASTER_PLAYBOOK.md` is the canonical continuation path; `docs/CLAUDE_AUTONOMY_LAUNCHOFF.md` is the detailed adapter sequence. Reject any change where a story slug or named video selects bespoke behavior.