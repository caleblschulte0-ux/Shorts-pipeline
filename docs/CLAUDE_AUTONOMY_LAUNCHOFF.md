# Claude Autonomy Launch-Off — Curiosity 50-Video System

## Canonical source

Read `docs/00_CLAUDE_START_HERE.md`, then `docs/CLAUDE_MASTER_PLAYBOOK.md` and `docs/CLAUDE_HANDOFF_MANIFEST.json` before changing code.

The master playbook is the source of truth. This file is the compact launch sequence.

It supersedes older instructions that optimize a named video, use a story slug as a behavior selector, or treat a handful of stories as proof of portfolio autonomy.

## Current truth

- PR #172 contains the recovered production path and must be reconciled with current `main` before new production adapters are built.
- PR #173 is a dormant reference surface only.
- PR #173 contains 77 prototype modules and 425 authored contracts across 12 test files.
- The finite authored rubrics report 100% structural and 100% autonomy reference coverage.
- The final dormant suite is not claimed executed successfully yet.
- The dormant modules are not integrated into production.
- No autonomous public rollout is authorized.
- Publishing must remain disabled by default.

## Stop adding architecture

Do not create another dormant subsystem unless `assess_autonomy_completeness()` proves a real missing domain.

Allowed next work:

1. execute and fix the isolated suite;
2. validate heterogeneous fixtures;
3. integrate one generic capability in one focused PR;
4. collect deterministic simulation, shadow, canary, and live evidence.

## Immediate action

```bash
git fetch origin
gh pr checkout 173
git rev-parse HEAD
python -m compileall experiments/curiosity_nextgen
python -m unittest discover -v experiments/curiosity_nextgen/tests
```

Required result before production integration:

- all 77 modules import;
- all 425 contracts pass;
- no test is weakened, deleted, or skipped merely to obtain green status;
- no production path is modified during dormant repair;
- exact commands, exit codes, counts, duration, commits, changed files, and head SHA are reported.

## Clean production base

After the dormant suite is understood:

1. reconcile PR #172 with current `main`;
2. rerun the recovery checks on the exact proposed merge SHA;
3. prove defaults, scheduled invocation, retries, `--force`, and ordinary configuration cannot publish;
4. preserve the canonical pro producer and explicit-only legacy path;
5. merge only through owner-approved repository procedure;
6. create integration PRs from the resulting current `main`.

Do not merge PR #173 wholesale.

## Heterogeneous validation catalog

Build exactly 50 opaque story fixtures spanning topics, formats, durations, audiences, factual risks, tones, visual grammars, media availability, costs, provider requirements, and exploration roles.

Include positive and negative cases for evidence gaps, visual scarcity, provider outage, quota exhaustion, transient and fatal failures, repairable and non-repairable quality defects, tampered artifacts, missing or disagreeing judges, repetition, budget pressure, worker loss, and duplicate callbacks.

Shuffle story IDs and prove decisions do not change.

## Focused integration order

### PR A — Cryptographic stage and package identity

Reference: `artifact_manifest.py`, `stage_artifact_contract.py`, `lineage_graph.py`.

Every report and approval must bind to the exact video, story, claims, captions, thumbnail, media, renderer, and manifest hashes. Tampering must quarantine. mtime is not final identity.

### PR B — Mandatory factual modes and semantic claims

Reference: `claim_registry.py`, `semantic_claims.py`, controller factual rewind behavior.

Require declared factual mode, beat-linked claims, structured sources, nonnumeric semantic coverage, modeled assumptions, and generic rewind or quarantine for missing evidence.

### PR C — Provider routing and independent headless review

Reference: `provider_pool.py`, `adapter_contracts.py`, `judge_evidence.py`, `judge_contract.py`, `judge_orchestrator.py`.

Route by capability, health, quota, cost, latency, determinism, and errors. Technical and editorial judges must use independent provider and model families. Verdicts bind to package hashes.

### PR D — Durable execution state

Reference: `execution_ledger.py`, `checkpoint_store.py`, `replay_engine.py`.

Require append-only hash-chained events, idempotent callbacks, expiring leases, worker-loss recovery, deterministic replay, and duplicate-outcome protection.

### PR E — Bounded autonomous batch controller

Reference: `production_stage_graph.py`, `autonomous_decision_engine.py`, `autonomous_batch_controller.py`, `autonomous_program.py`, `resource_governor.py`, `render_scheduler.py`.

Register up to 50 stories, run a bounded diverse wave, enforce attempts and budgets, hold incomplete evidence, quarantine exhausted paths, and prevent one failure from stalling the portfolio.

### PR F — Idea funnel and portfolio admission

Reference: `idea_funnel.py`, `story_intake_contract.py`, `portfolio_optimizer.py`, `repetition_ledger.py`.

Score value, novelty, evidence, visuals, cost, and risk; reject duplicates; control concentration; reserve exploration; keep selection auditable and independent of identity.

### PR G — Deterministic fault-injected 50-story simulation

Reference: `autonomous_simulator.py`, `fault_injection.py`, `batch_acceptance.py`, `observability.py`, `launch_readiness.py`.

The same seed must produce the same trace. Inject provider, worker, factual, artifact, judge, quality, and budget faults and enforce expected recovery, hold, rewind, quarantine, and acceptance behavior.

### PR H — Controlled learning after stable shadow operation

Reference: `controlled_learning_loop.py`, `experiment_attribution.py`, `policy_snapshot.py`, `drift_monitor.py`.

Require controlled multi-story evidence, samples, effect floors, guardrails, bounded deltas, evidence hashes, canaries, and tested rollback. One result cannot rewrite doctrine.

## Shadow and canary requirements

Before autonomous public publication:

- complete at least three heterogeneous shadow batches with publishing disabled;
- preserve hash-bound packages, independent verdicts, durable ledgers, fallback evidence, budget evidence, and zero unresolved hard blockers;
- prove one failed story does not stall the portfolio.

Then, only with owner approval:

1. verify the exact manifest-bound candidate;
2. verify expected-channel guard, kill switch, and rollback;
3. publish one canary;
4. verify remote identity and metadata;
5. freeze publishing again;
6. repeat until at least three autonomous canaries pass.

One canary does not authorize scheduling.

## Formal launch gate

Use `assess_launch_readiness()`.

Launch requires:

- 100% authored autonomy reference coverage;
- 100% verified isolated execution;
- 100% required adapter integration;
- one successful deterministic 50-story simulation;
- three heterogeneous shadow batches;
- three autonomous canaries;
- active artifact hashes, factual contracts, independent judges, durable state, provider fallbacks, bounded recovery, budgets, and monitoring;
- tested rollback and kill switch;
- active expected-channel guard;
- publishing disabled by default;
- zero unresolved hard blockers.

Anything less is not launch-ready.

## Evidence required in every PR

Report exact base and head SHAs, files changed, commands, exit codes, counts, negative controls, workflow runs, artifacts, before/after behavior, quality impact, cost and resource impact, rollback, remaining risks, and definition of done.

## Final instruction

Do not return only a plan. Execute the first uncompleted phase and prove the result.