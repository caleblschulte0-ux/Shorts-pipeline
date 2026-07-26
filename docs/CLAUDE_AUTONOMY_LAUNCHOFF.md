# Claude Autonomy Launch-Off — Curiosity 50-Video System

This is the primary continuation document for turning the dormant reference package into a verified, integrated, and safely launched autonomous system.

It supersedes any older instruction that optimizes a named video or treats a handful of stories as proof of autonomy.

## Current truth

- PR #172 is the recovered production-path branch and remains the required integration base.
- PR #173 is a dormant reference surface only. It contains no production imports, renderer changes, workflow changes, scheduling changes, or publishing changes.
- The dormant package has **100% authored autonomy reference coverage** across the finite 24-domain rubric in `autonomy_completeness.py`.
- Authored reference closure is not execution proof, integration proof, or launch proof.
- The isolated suite must be run and fixed before any production adapter is connected.
- Publishing must remain disabled by default throughout development, testing, shadow operation, and canary preparation.

## Product requirement

Build a system that can autonomously select, research, author, render, judge, repair, package, and manage a heterogeneous portfolio of up to 50 arbitrary videos.

The unit of optimization is the reusable system and the portfolio, never a named story.

### Hard invariants

1. Story IDs are opaque tracking identifiers and may not select behavior.
2. No story slug, title, topic, or existing scene may activate bespoke repair logic.
3. All decisions must derive from reusable contracts, evidence, metadata, policy, resource state, and stage state.
4. Retry, repair, re-author, spend, concurrency, provider fallback, evidence, and learning loops must be bounded.
5. Missing evidence, stale artifacts, judge disagreement, provider exhaustion, factual gaps, and policy violations must hold or quarantine rather than silently pass.
6. Technical and editorial review must be independent by provider and model family.
7. Every approval must bind to exact content hashes, not timestamps or filenames.
8. Learning may propose bounded policy changes only from controlled multi-story experiments; it may not self-activate an untested change.
9. No dormant module may be imported wholesale into production.
10. Every production change must be a focused PR with a rollback path.

## Stop adding architecture

The 24-domain autonomy reference rubric is closed.

Do not add another dormant module unless `assess_autonomy_completeness()` demonstrates a genuinely missing domain. New work should now fall into one of four categories:

1. execute and fix the isolated suite;
2. validate against heterogeneous fixtures;
3. integrate one generic capability through a focused adapter PR;
4. collect shadow, canary, or live evidence required by `launch_readiness.py`.

## Phase 0 — Establish a clean integration base

1. Reconcile PR #172 with current `main`.
2. Resolve conflicts without restoring rejected or unrelated work.
3. Run all existing production checks on the exact proposed merge SHA.
4. Prove publishing remains disabled under defaults, scheduled invocation, `--force`, retries, and ordinary environment configuration.
5. Merge only after the exact merge SHA is green.
6. Create all autonomy integration PRs from the resulting current `main`.

Do not merge PR #173 wholesale into production. Treat it as reference code and test material.

## Phase 1 — Execute and repair the dormant package

Run:

```bash
python -m compileall experiments/curiosity_nextgen
python -m unittest discover experiments/curiosity_nextgen/tests
```

Required result before integration:

- every module imports;
- every contract passes;
- `assess_autonomy_completeness(complete_autonomy_reference_evidence())` reports 100% reference coverage;
- verified execution coverage is updated only from real successful test evidence;
- no path outside `docs/` and `experiments/` is modified by the dormant validation PR;
- no test is deleted or weakened merely to obtain green status.

When a contract fails, decide whether the implementation or the contract is wrong. Preserve fail-closed behavior and document the reasoning.

## Phase 2 — Build the heterogeneous 50-story validation catalog

Create a catalog containing exactly 50 opaque story IDs with varied:

- topic families;
- formats;
- durations;
- target audiences;
- factual-risk levels;
- emotional tones;
- visual modes;
- media availability;
- estimated production costs;
- exploration versus exploitation roles.

The fixture set must include positive and negative cases:

- strong evidence and weak evidence;
- visual abundance and visual scarcity;
- low-risk and high-risk factual material;
- provider outages and quota exhaustion;
- transient failures and fatal failures;
- repairable and non-repairable quality defects;
- stale or tampered artifacts;
- missing judge evidence;
- repeated hook, format, and visual families;
- cost and concurrency pressure.

No fixture may require its ID to trigger the expected behavior.

## Phase 3 — Integrate in focused PRs

Use this order. Do not combine the steps into one giant PR.

### PR A — Hash-bound stage artifacts

Port the minimum useful pieces from:

- `artifact_manifest.py`;
- `stage_artifact_contract.py`;
- `lineage_graph.py`.

Acceptance:

- all stage outputs bind to exact input hashes;
- changed video, story, claims, captions, thumbnail, media, or verdict quarantines;
- mtime is not final identity;
- rollback removes the adapter without changing generated content formats unexpectedly.

### PR B — Mandatory factual contracts

Port the minimum useful pieces from:

- `claim_registry.py`;
- `semantic_claims.py`;
- factual rewind behavior in `autonomous_batch_controller.py`.

Acceptance:

- every story declares a factual mode;
- high-risk stories require structured claims and source coverage;
- nonnumeric semantic claims are covered;
- missing or stale factual evidence rewinds or quarantines generically.

### PR C — Provider routing and independent judges

Port the minimum useful pieces from:

- `provider_pool.py`;
- `adapter_contracts.py`;
- `judge_orchestrator.py`;
- `judge_evidence.py`;
- `judge_contract.py`.

Acceptance:

- routing respects capability, health, quota, latency, cost, and determinism;
- technical and editorial judges use independent provider and model families;
- exhausted fallback plans hold or quarantine;
- verdicts bind to exact package hashes.

### PR D — Durable execution state

Port the minimum useful pieces from:

- `execution_ledger.py`;
- `checkpoint_store.py`;
- `replay_engine.py`.

Acceptance:

- callbacks are idempotent;
- stage claims use expiring leases;
- worker loss can resume safely;
- event history is tamper-evident;
- replay produces the same materialized state;
- duplicate outcomes cannot advance a story twice.

### PR E — Autonomous batch controller

Port the minimum useful pieces from:

- `autonomous_decision_engine.py`;
- `autonomous_batch_controller.py`;
- `production_stage_graph.py`;
- `resource_governor.py`;
- `render_scheduler.py`.

Acceptance:

- exactly 50 stories can be registered;
- only a bounded diverse wave runs concurrently;
- retry, repair, re-author, cost, topic, format, and provider limits are enforced;
- failed stories do not block the healthy remainder of the batch;
- incomplete evidence holds;
- exhausted stories quarantine;
- publishing remains disabled.

### PR F — Idea funnel and portfolio admission

Port the minimum useful pieces from:

- `idea_funnel.py`;
- `portfolio_optimizer.py`;
- `repetition_ledger.py`.

Acceptance:

- duplicate premises are rejected;
- evidence and visual feasibility clear minimum floors;
- topic, format, hook, and visual concentration are controlled;
- exploration capacity is reserved;
- selection is auditable and independent of story ID.

### PR G — Full deterministic shadow simulator

Port or adapt:

- `autonomous_simulator.py`;
- `fault_injection.py`;
- `batch_acceptance.py`;
- `observability.py`;
- `launch_readiness.py`.

Acceptance:

- a deterministic 50-story run completes under the agreed policy;
- injected provider, factual, artifact, budget, worker, and judge faults produce expected hold/quarantine/recovery behavior;
- completion, quarantine, cost, quality, factual, hash, judge, hook, and visual-diversity thresholds are enforced;
- the same seed and inputs produce the same outcome trace.

### PR H — Controlled learning, only after stable shadow operation

Port the minimum useful pieces from:

- `controlled_learning_loop.py`;
- `experiment_attribution.py`;
- `policy_snapshot.py`;
- `drift_monitor.py`.

Acceptance:

- proposals require controlled multi-story evidence;
- sample, effect, guardrail, and hard-blocker requirements are enforced;
- parameter changes are bounded;
- every proposal is versioned and evidence-hashed;
- canary batches and tested rollback are mandatory before activation;
- one result cannot rewrite channel doctrine.

## Phase 4 — Shadow operation

Complete at least three heterogeneous shadow batches before any autonomous public upload.

Each shadow batch must:

- include the full 50-story intake or the maximum supported catalog available at that stage;
- run with publishing disabled;
- exercise provider fallback and bounded recovery;
- produce hash-bound artifacts and independent verdicts;
- preserve a complete execution ledger;
- meet batch acceptance thresholds;
- produce no unresolved hard blocker;
- demonstrate that one failed story does not stall the portfolio.

## Phase 5 — Controlled canary

After all launch blockers are clear:

1. Owner explicitly approves the exact manifest-bound candidate.
2. Expected-channel guard is active.
3. Kill switch and rollback have been tested.
4. Publish exactly one canary.
5. Verify the remote upload identity and metadata.
6. Freeze publishing again.
7. Repeat until at least three autonomous canaries pass.

Do not enable scheduled autonomous publishing merely because one canary succeeds.

## Launch gate

Use `assess_launch_readiness()` as the formal evidence checklist.

Launch requires all of the following:

- 100% authored autonomy reference coverage;
- 100% verified isolated test execution;
- 100% required adapter integration;
- successful deterministic 50-story simulation;
- at least three heterogeneous shadow batches;
- at least three autonomous canaries;
- active artifact hash binding;
- active factual evidence contracts;
- active independent judges;
- active durable execution state;
- active provider fallbacks;
- active bounded recovery;
- active budget controls;
- active monitoring;
- tested rollback;
- tested kill switch;
- active expected-channel guard;
- publishing disabled by default;
- zero unresolved hard blockers.

Anything less is not launch-ready.

## Required evidence in every PR

- exact base and head SHAs;
- exact files changed;
- tests and exit codes;
- negative controls;
- workflow run on the exact head SHA;
- fixture or rendered evidence where applicable;
- before/after behavior;
- resource and cost impact;
- rollback procedure;
- remaining risks;
- definition of done.

## Immediate first action for Claude

Do not design another subsystem.

Start by checking out PR #173 in a normal repository environment, run compileall and the complete isolated test suite, fix every failure without weakening the contracts, and publish the exact passing count and head SHA. Then execute Phase 0 and begin PR A from current `main`.
