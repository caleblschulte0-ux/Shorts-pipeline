# Claude Execution Checklist — Autonomous Curiosity System

Documentation-only handoff. This file changes no runtime behavior.

Primary continuation document: `docs/CLAUDE_AUTONOMY_LAUNCHOFF.md`.

## Current truth

- [x] Dormant structural reference surface authored across 27 finite domains.
- [x] Dormant autonomy reference surface authored across 24 finite domains.
- [x] Authored structural reference coverage: 100%.
- [x] Authored autonomy reference coverage: 100%.
- [x] System design supports a heterogeneous catalog of up to 50 opaque story IDs.
- [x] Named-video dispatch and bespoke story plans are prohibited.
- [ ] Isolated contracts verified passing in a normal checkout.
- [ ] Generic adapters integrated into production.
- [ ] Deterministic 50-story simulation passed with fault injection.
- [ ] Three heterogeneous shadow batches passed.
- [ ] Three autonomous canaries passed.
- [ ] Formal launch-readiness gate cleared.

Authored completion is not execution, integration, or launch completion.

## Immediate work order

### Phase 0 — Production base

- [ ] Reconcile PR #172 with current `main`.
- [ ] Run every existing production check on the exact proposed merge SHA.
- [ ] Prove scheduled runs, defaults, retries, `--force`, and ordinary environment values cannot enable publishing.
- [ ] Preserve explicit-only emergency legacy routing.
- [ ] Merge only after the exact merge SHA is green.

### Phase 1 — Execute the dormant package

- [ ] Check out PR #173 in a normal repository environment.
- [ ] Run `python -m compileall experiments/curiosity_nextgen`.
- [ ] Run `python -m unittest discover experiments/curiosity_nextgen/tests`.
- [ ] Fix every implementation or contract defect without weakening fail-closed behavior.
- [ ] Record exact passing count, runtime, Python version, platform, and head SHA.
- [ ] Confirm the strict structural and autonomy reference rubrics both report 100%.
- [ ] Update verified execution percentages only from real successful runs.

### Phase 2 — Heterogeneous validation catalog

- [ ] Build exactly 50 opaque story fixtures.
- [ ] Cover multiple topics, formats, durations, audiences, factual risks, tones, media modes, costs, and exploration roles.
- [ ] Include positive and negative evidence cases.
- [ ] Include provider outages, quota exhaustion, worker loss, stale artifacts, judge disagreement, factual rewinds, budget pressure, and non-repairable failures.
- [ ] Prove changing a story ID does not change system behavior.
- [ ] Prove no single topic, format, hook, or visual family dominates the portfolio.

## Focused integration PRs

### PR A — Hash-bound stage artifacts

- [ ] Port only the minimum useful pieces from `artifact_manifest.py`, `stage_artifact_contract.py`, and `lineage_graph.py`.
- [ ] Bind every output to exact input hashes and schemas.
- [ ] Quarantine changed video, story, claims, captions, thumbnail, media, or verdict.
- [ ] Remove mtime as final identity.

### PR B — Mandatory factual contracts

- [ ] Require every story to declare a factual mode.
- [ ] Require structured claims and sources for factual stories.
- [ ] Cover nonnumeric semantic claims.
- [ ] Rewind or quarantine missing, stale, or mismatched factual evidence.

### PR C — Provider routing and independent judges

- [ ] Route by capability, health, quota, latency, cost, and determinism.
- [ ] Require independent provider and model families for technical and editorial judges.
- [ ] Exercise provider fallbacks and exhaustion.
- [ ] Bind verdicts to exact artifact hashes.

### PR D — Durable execution state

- [ ] Add idempotent callbacks and expiring stage leases.
- [ ] Preserve append-only tamper-evident history.
- [ ] Resume safely after worker loss.
- [ ] Prove replay reconstructs identical materialized state.
- [ ] Prevent duplicate outcomes from advancing a story twice.

### PR E — Autonomous batch controller

- [ ] Register exactly 50 stories.
- [ ] Run a bounded, diverse active wave.
- [ ] Enforce topic, format, provider, attempt, repair, re-author, cost, and concurrency limits.
- [ ] Hold incomplete evidence.
- [ ] Quarantine exhausted or unsafe stories.
- [ ] Prove one failed story does not stall the portfolio.
- [ ] Keep publishing disabled.

### PR F — Idea funnel and portfolio admission

- [ ] Reject duplicate premises.
- [ ] Enforce audience, evidence, visual, sensitivity, cost, and source floors.
- [ ] Reserve exploration capacity.
- [ ] Control topic, format, hook, and visual concentration.
- [ ] Make every selection auditable and story-ID independent.

### PR G — Deterministic 50-story shadow simulator

- [ ] Run the full 50-story simulator with deterministic inputs.
- [ ] Inject provider, factual, artifact, budget, worker, evidence, and judge faults.
- [ ] Verify bounded retry, rewind, repair, hold, and quarantine behavior.
- [ ] Enforce batch completion, quarantine, cost, quality, factual, hash, judge, and diversity thresholds.
- [ ] Prove identical inputs produce identical outcome traces.

### PR H — Controlled learning

- [ ] Begin only after stable shadow operation.
- [ ] Require controlled multi-story evidence and minimum samples.
- [ ] Enforce effect-size and negative-feedback guardrails.
- [ ] Bound every proposed parameter change.
- [ ] Hash and version every proposal.
- [ ] Require canary batches and tested rollback before activation.
- [ ] Prevent one result from rewriting channel doctrine.

## Shadow and canary evidence

- [ ] Complete three heterogeneous shadow batches with publishing disabled.
- [ ] Preserve hash-bound artifacts, independent verdicts, execution ledgers, fallback evidence, and batch-acceptance reports.
- [ ] Test rollback and kill switch.
- [ ] Activate expected-channel guard.
- [ ] Obtain explicit owner approval for each exact manifest-bound canary.
- [ ] Publish one canary at a time.
- [ ] Verify remote upload identity and metadata.
- [ ] Freeze publishing after every canary.
- [ ] Complete at least three successful autonomous canaries before considering scheduled rollout.

## Required evidence for every implementation PR

- [ ] Exact base and head SHAs.
- [ ] Exact files changed.
- [ ] Tests and exit codes.
- [ ] Negative controls.
- [ ] Workflow run on the exact head SHA.
- [ ] Fixture, package, or rendered evidence where applicable.
- [ ] Before/after behavior.
- [ ] Resource and cost impact.
- [ ] Rollback procedure.
- [ ] Remaining risks.
- [ ] Definition of done.

## Never do

- [ ] Never dispatch behavior from a story slug, title, or opaque ID.
- [ ] Never add a named-video blueprint to production-shaped code.
- [ ] Never import the dormant package wholesale.
- [ ] Never create one giant mixed implementation PR.
- [ ] Never weaken a test or gate merely to make it pass.
- [ ] Never enable scheduled publishing during development or shadow operation.
- [ ] Never silently fall back to legacy or generic cards.
- [ ] Never trust mtime as final artifact identity.
- [ ] Never call one video, three videos, or one topic family proof of autonomous catalog readiness.
- [ ] Never claim executed, integrated, live, or launch readiness from authored reference coverage.

## Formal launch acceptance

- [ ] Authored structural reference coverage is 100%.
- [ ] Authored autonomy reference coverage is 100%.
- [ ] Verified isolated test execution is 100%.
- [ ] Required adapter integration is 100%.
- [ ] Deterministic 50-story simulation passes.
- [ ] Three heterogeneous shadow batches pass.
- [ ] Three autonomous canaries pass.
- [ ] Artifact hash binding is active.
- [ ] Factual evidence contracts are active.
- [ ] Independent judges are active.
- [ ] Durable execution state is active.
- [ ] Provider fallbacks are active.
- [ ] Bounded recovery and budget controls are active.
- [ ] Monitoring is active.
- [ ] Rollback and kill switch are tested.
- [ ] Expected-channel guard is active.
- [ ] Publishing is disabled by default.
- [ ] Zero unresolved hard blockers remain.

Use `assess_launch_readiness()` as the formal gate. Anything less is not launch-ready.
