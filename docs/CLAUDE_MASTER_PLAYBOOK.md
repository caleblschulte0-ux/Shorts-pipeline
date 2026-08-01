# Claude Master Playbook — Curiosity Pipeline

## Read this first

This is the canonical handoff for the Curiosity video system. It consolidates the production recovery in PR #172, the dormant autonomous reference surface in PR #173, the known evidence, the unresolved risks, the exact work order, the acceptance rules, and the first prompt Claude should execute.

Where older documents conflict with this file, this file wins.

In particular:

- `docs/CLAUDE_CONTINUATION_PLAYBOOK.md` remains useful for historical recovery detail and defect examples, but its named-video and three-story proof sections are superseded.
- `docs/CLAUDE_AUTONOMY_LAUNCHOFF.md` remains the detailed adapter sequence, but this file is the entry point and source of truth.
- `docs/CLAUDE_EXECUTION_CHECKLIST.md` is the compact checklist derived from this playbook.
- `docs/CLAUDE_HANDOFF_MANIFEST.json` is the machine-readable snapshot.

Do not respond to this playbook with another plan. Execute the next uncompleted phase, preserve evidence, and report exact results.

---

# 1. Executive truth

There are two separate bodies of work.

## PR #172 — recovered production path

Branch: `feature/curiosity-pro-integration`

Known recovery head: `f6419ad574e140bcdd0a052f89b89304b3503e44`

Purpose:

- recover the disconnected professional Curiosity renderer onto a normal branch based on `main`;
- establish one canonical producer and fail-closed route;
- preserve publishing as disabled by default;
- prove one complete render path with tests, gates, facts, performance data, visual review, and a held dry-run package.

PR #172 contains active production-shaped code. It is not merged merely because it exists. Reconcile it with the current `main`, run checks on the exact proposed merge SHA, and preserve the publishing freeze.

## PR #173 — dormant autonomous reference surface

Branch: `agent/curiosity-continuation-handoff`

Base: PR #172 recovery branch

Purpose:

- define a complete, generic reference architecture for selecting, researching, authoring, rendering, judging, repairing, packaging, scheduling, and learning from a heterogeneous portfolio of up to 50 arbitrary videos;
- provide standard-library-only prototype modules and isolated contract tests;
- give production integration a reusable reference without silently changing production.

PR #173 is intentionally dormant. Nothing in the active pipeline imports `experiments.curiosity_nextgen`. Do not merge or import it wholesale.

## Current finite reference numbers

- 77 dormant prototype modules;
- 425 authored contract tests;
- 12 isolated test files;
- 27 required structural reference domains;
- 24 required autonomy reference domains;
- 100% authored structural reference coverage;
- 100% authored autonomy reference coverage;
- 0% verified dormant-suite execution claimed until the suite actually runs successfully;
- 0% production integration claimed for the dormant modules;
- 0 live autonomous launch evidence claimed.

The word **100%** applies only to the finite authored reference rubrics. It does not mean tested, integrated, autonomous, launched, or creatively perfect.

---

# 2. Product requirement

Build a Curiosity channel system that can autonomously manage up to 50 heterogeneous videos at once while preserving factual integrity, creative quality, bounded spending, independent review, recoverability, and publishing safety.

The reusable system and the portfolio are the units of optimization. A named story is only a fixture or piece of evidence.

## Hard invariants

1. Story IDs are opaque tracking identifiers. IDs, slugs, titles, topics, or existing scene names may not select bespoke behavior.
2. Decisions must derive from generic contracts, evidence, metadata, policies, stage state, provider state, and resource state.
3. Missing, stale, contradictory, or tampered evidence must hold or quarantine.
4. Retry, repair, re-author, spend, concurrency, provider fallback, canary, and learning loops must be bounded.
5. Technical and editorial review must be independent by provider family and model family.
6. Every approval must bind to exact content hashes, not file names or modification times.
7. Factual stories require declared factual modes and structured claim coverage.
8. Learning may propose bounded changes only from controlled multi-story evidence. It may not self-activate untested policy.
9. Publishing remains disabled by default through development, integration, shadow operation, and canary preparation.
10. Every production capability is integrated through a focused PR with tests, negative controls, evidence, and rollback.
11. Do not weaken a quality, facts, integrity, safety, or publishing gate merely to make a candidate pass.
12. Do not commit rendered MP4s or other large generated artifacts to Git.

---

# 3. What PR #172 recovered

## Canonical route

```text
scripts/post_curiosity.py:main
  -> _render_story                       # pro renderer is the default
  -> scripts/produce.py:produce          # canonical producer
  -> scripts/no_dull_beats.py:run        # render -> gates -> repair, at most two rounds
  -> data_learning/pro_render.py
  -> planner / shots / media / package / fallback and performance reports
  -> blind visual evidence package
  -> scripts/facts_gate.py
  -> scripts/produce.py:evaluate          # five gates, PASS or QUARANTINE
  -> post_curiosity finished-video gates
  -> CURIOSITY_PUBLISH_ENABLED gate
  -> upload or HOLD
```

Legacy rendering is explicit emergency mode only. A missing pro story fails closed rather than silently importing legacy.

## Recovered capabilities

- professional renderer, planner, scene and expression systems;
- media, stock, footage, continuity, contrast, and fallback systems;
- producer, director loop, render gates, quality gates, hook and interest judges;
- factual checks and structured facts for the flagship fixture;
- performance instrumentation and leak accounting;
- expression verification and visual-difference tests;
- layered CI and reproducible evidence packages;
- seven recovered pro story definitions;
- doctrine and visual-standard documents.

## Verified recovery tests and evidence

The recovery report records:

- compile/import/JSON closure: exit 0;
- routing: 4/4;
- verdict contract: 14/14;
- producer decisions: 8/8;
- facts gate: 12/12;
- performance instrumentation: pass;
- expression gates: pass;
- expression scenes: 6/6 and visibly different;
- producer smoke: pass, with an all-card fixture correctly rejected;
- full flagship canary: director clean, then PASS after blind judgment;
- render gates: 4/4 PASS;
- live facts: 7/7 claims and 16/16 numeric beats covered;
- dry-run publication simulation: publish eligible with no blockers, correctly HELD;
- recorded GitHub CI runs: successful on the documented recovery SHAs.

These recovery results belong to PR #172 and its recorded artifacts. Re-run required checks after reconciling with current `main`.

## Measured performance

For the documented 242-second, 50-shot render:

- full wall time: 1,906 seconds, about 31.8 minutes;
- median shot time: 8.7 seconds;
- slowest shot: 52.9 seconds;
- RSS: 57 MB start, 60 MB end, 121 MB peak;
- remaining child processes: zero;
- no progressive slowdown was measured.

The old perceived late-render slowdown was diagnosed as workload composition and session contention, not a growing leak.

## Visual truth

The documented blind verdict was PASS, but not elite:

- overall approximately 6/10;
- personality 3/5;
- hook 7/10 after previously scoring 8/10 before a resize;
- repeated dark-starfield chapter-card family;
- one wrong-context Japanese gas-station image;
- one desired photo action degraded to a statement card;
- three real-media beats in a row;
- insufficient character emotional progression.

Those observations were converted into generic creative modules and repair contracts in PR #173. Do not add story-ID branches to fix them.

## Recovery limitations still relevant

- artifact freshness still relies partly on mtime until cryptographic binding is integrated;
- provenance is opt-in and semantic nonnumeric claim coverage is incomplete in production;
- blind visual verdict creation is not fully headless in production;
- full renders are expensive and selective rerender is not integrated;
- only one full production-path fixture has passed end to end;
- cross-video repetition, controlled learning, and autonomous portfolio operation are not live;
- no public canary or scheduled autonomous publication has been authorized.

---

# 4. What PR #173 built

Everything below is dormant reference code under `experiments/curiosity_nextgen/`.

## A. Policy, governance, and integrity

Relevant modules include:

- `policy_snapshot.py`;
- `approval_token.py`;
- `freeze_controller.py`;
- `audit_chain.py`;
- `security_scanner.py`;
- `environment_lock.py`;
- `package_readiness.py`;
- `pipeline_status.py`;
- `lifecycle_controls.py`;
- `launch_readiness.py`;
- `structural_completeness.py`;
- `autonomy_completeness.py`.

Purpose:

- snapshot policy versions;
- bind approvals to evidence;
- fail closed during release freezes;
- maintain tamper-evident audit history;
- scan risky package content;
- verify environment identity;
- distinguish authored reference closure from execution, integration, and live readiness.

## B. Artifact identity, schemas, and lineage

Relevant modules include:

- `artifact_manifest.py`;
- `stage_artifact_contract.py`;
- `lineage_graph.py`;
- `schema_registry.py`;
- `migration_planner.py`;
- `checkpoint_store.py`;
- `replay_engine.py`.

Purpose:

- bind each output to exact input hashes;
- validate stage-specific artifact types and schema versions;
- prevent cross-story contamination;
- support safe schema migration;
- recover deterministic state after interruption;
- prove which source, story, claim, media, renderer, judge, and approval produced a package.

## C. Facts and semantic claims

Relevant modules include:

- `claim_registry.py`;
- `semantic_claims.py`;
- factual evidence hooks in the intake, decision, controller, and acceptance modules.

Purpose:

- declare factual modes;
- tie claims to beat IDs;
- cover numbers, dates, superlatives, comparisons, causal claims, geography, science, health, history, named institutions, and attributed claims;
- require assumptions and uncertainty for modeled values;
- rewind, hold, or quarantine missing and stale evidence.

## D. Provider routing and independent judging

Relevant modules include:

- `provider_pool.py`;
- `adapter_contracts.py`;
- `judge_evidence.py`;
- `judge_contract.py`;
- `judge_orchestrator.py`;
- `review_queue.py`.

Purpose:

- route by capability, health, quota, price, latency, determinism, and error rate;
- preserve independent fallback families;
- force technical and editorial judges onto independent provider and model families;
- blind judges from implementation intent, previous verdicts, and repair justification;
- bind verdicts to exact manifests and media.

## E. Durable orchestration and resilience

Relevant modules include:

- `execution_ledger.py`;
- `checkpoint_store.py`;
- `replay_engine.py`;
- `circuit_breaker.py`;
- `fault_injection.py`;
- `resilience_lab.py`;
- `resource_governor.py`;
- `render_budget.py`;
- `render_scheduler.py`;
- `observability.py`.

Purpose:

- append-only hash-chained execution events;
- idempotent callbacks;
- expiring leases;
- safe worker-loss recovery;
- deterministic replay;
- bounded provider and subsystem failures;
- cost and concurrency limits;
- resource accounting and incident visibility.

## F. Portfolio intake and autonomous operation

Relevant modules include:

- `idea_funnel.py`;
- `story_intake_contract.py`;
- `story_catalog.py`;
- `catalog_triage.py`;
- `portfolio_optimizer.py`;
- `repetition_ledger.py`;
- `production_stage_graph.py`;
- `autonomous_decision_engine.py`;
- `autonomous_batch_controller.py`;
- `autonomous_program.py`;
- `autonomous_simulator.py`;
- `batch_acceptance.py`.

Purpose:

- score and deduplicate ideas;
- require evidence and visual feasibility;
- reserve exploration capacity;
- control topic, format, hook, and visual concentration;
- register exactly up to 50 stories;
- admit a bounded diverse wave;
- advance, retry, wait, research, re-author, repair, or quarantine generically;
- prevent one failed story from stalling the portfolio;
- simulate heterogeneous batches with injected faults;
- accept or reject the entire batch under explicit thresholds.

## G. Creative quality and direct repair

Relevant modules include:

- `quality.py`;
- `hook_lab.py`;
- `beat_dynamics.py`;
- `chapter_style_planner.py`;
- `personality_arc.py`;
- `payoff_contract.py`;
- `creative_uplift.py`;
- `repair_planner.py`;
- `media_ranker.py`.

Purpose:

- evaluate hook clarity, specificity, surprise, stakes, visual promise, and payoff promise;
- detect flat energy, repeated visual families, dense explanation runs, weak turns, and dormant curiosity gaps;
- diversify chapter transitions;
- require character attempts, obstacles, reactions, adaptation, consequences, and resolved callbacks;
- bind opening questions to specific, visually proven payoffs;
- prioritize high-leverage creative repairs under bounded effort;
- rank media for relevance, geography, era, action, signage, licensing, and continuity.

## H. Viewer experience, retention, and edit planning

Relevant modules include:

- `curiosity_curve.py`;
- `narration_rhythm.py`;
- `visual_grammar.py`;
- `scene_choreography.py`;
- `audio_dynamics.py`;
- `promise_packaging.py`;
- `viewer_experience.py`;
- `retention_risk.py`;
- `cognitive_load.py`;
- `caption_readability.py`;
- `continuity_editor.py`;
- `visual_readability.py`;
- `humor_personality.py`;
- `emotional_resonance.py`;
- `edit_blueprint.py`.

Purpose:

- evaluate curiosity tension, narration pace, scene grammar, motion, audio, packaging, captions, comprehension, continuity, visual legibility, humor, emotion, and likely retention risk;
- convert moment-level defects into generic edit plans;
- plan repair across a portfolio without relying on story names.

## I. Caching, experimentation, learning, and drift

Relevant modules include:

- `shot_cache.py`;
- `experiment_attribution.py`;
- `controlled_learning_loop.py`;
- `drift_monitor.py`;
- `generalization_suite.py`;
- `integration_lab.py`.

Purpose:

- reuse unchanged shots under deterministic cache keys;
- attribute controlled variants to actual outcomes;
- require multi-story samples, effect floors, guardrails, canaries, and rollback before policy activation;
- detect quality and provider drift;
- prove rules generalize across topics, durations, formats, risk levels, and media mixes;
- test adapters before production adoption.

---

# 5. Dormant test inventory

The 425 authored contract tests are spread across 12 files:

1. `test_prototypes.py` — foundational prototype contracts.
2. `test_decision_intelligence.py` — decision and prioritization contracts.
3. `test_structural_hardening.py` — facts, judges, catalogs, scheduling, approvals, freezes, observability, and negative controls.
4. `test_resilience_controls.py` — schemas, migrations, lineage, replay, checkpoints, workload, leaks, faults, and resilience.
5. `test_completeness_closure.py` — policy, adapters, audit, human review, recovery, rollout, reproducibility, drift, portfolio, and structural closure.
6. `test_creative_quality.py` — hook, pacing, variety, personality, payoff, and creative-repair contracts.
7. `test_viewer_quality.py` — curiosity, narration, visual grammar, choreography, audio, packaging, and viewer-experience contracts.
8. `test_retention_quality.py` — retention, comprehension, captions, continuity, readability, humor, emotion, and edit contracts.
9. `test_autonomous_core.py` — intake, production DAG, evidence, bounded recovery, and story-ID independence.
10. `test_autonomous_program.py` — controller, 50-story capacity, concurrency, budget, rewind, quarantine, acceptance, and program cycles.
11. `test_autonomy_closure.py` — idea funnel, providers, artifacts, ledger, leases, idempotency, and deterministic simulation.
12. `test_autonomy_launch.py` — controlled learning, launch phases, isolation, and strict autonomy completeness.

These tests are authored but not claimed passing. The first legitimate next action is to run them in a normal checkout and fix all failures without weakening the contracts.

---

# 6. Precedence and document map

Read in this order:

1. `docs/CLAUDE_MASTER_PLAYBOOK.md` — this file; canonical context and doctrine.
2. `docs/CLAUDE_HANDOFF_MANIFEST.json` — machine-readable status and commands.
3. `docs/CURIOSITY_FINAL_REPORT.md` — PR #172 recovery evidence.
4. `docs/CLAUDE_AUTONOMY_LAUNCHOFF.md` — detailed focused adapter sequence.
5. `docs/CLAUDE_EXECUTION_CHECKLIST.md` — compact execution checklist.
6. `experiments/curiosity_nextgen/README.md` — dormant package map and isolation contract.
7. `docs/CLAUDE_CONTINUATION_PLAYBOOK.md` — historical detail only; named-video and three-story targets are superseded.

Never infer current Git state from a static document. Run:

```bash
git fetch origin
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
```

Record the exact SHAs in every report.

---

# 7. Immediate execution sequence

## Phase 0A — Validate PR #173 as dormant reference code

```bash
git fetch origin
gh pr checkout 173
git rev-parse HEAD
python -m compileall experiments/curiosity_nextgen
python -m unittest discover -v experiments/curiosity_nextgen/tests
```

Required result:

- all 77 modules import;
- all 425 contracts pass;
- no test is deleted, skipped, or weakened merely to reach green;
- no production path is modified during dormant-suite repair;
- the exact command, exit code, passing count, failing count, duration, and head SHA are reported.

When a test fails:

1. identify whether the implementation or contract is wrong;
2. preserve fail-closed behavior;
3. add a regression case when the failure reveals a missing edge;
4. do not paper over the issue with story-specific behavior;
5. commit focused fixes with clear messages.

## Phase 0B — Reconcile PR #172 with current `main`

Do this only after the dormant suite is understood.

Required work:

- update PR #172 against current `main`;
- preserve the canonical pro route and explicit-only legacy route;
- preserve default publishing HOLD;
- rerun every recovery check on the exact proposed merge SHA;
- prove scheduled invocation, defaults, retries, `--force`, and ordinary configuration cannot publish;
- inspect workflow permissions and secret scope;
- merge only through owner-approved repository procedure.

Do not build production adapters on the stale recovery base after a current-main integration base exists.

---

# 8. Heterogeneous 50-story validation catalog

Before claiming autonomous generality, create exactly 50 opaque story IDs with varied:

- topic families;
- formats;
- durations;
- audiences;
- factual risk;
- emotional tone;
- visual grammar;
- media availability;
- estimated cost;
- provider requirements;
- exploration versus exploitation roles.

The catalog must include positive and negative cases for:

- strong and weak evidence;
- abundant and scarce visuals;
- low and high factual risk;
- transient, repairable, and fatal failures;
- provider outage and quota exhaustion;
- stale and tampered artifacts;
- missing and disagreeing judges;
- repeated hooks, formats, transitions, and media;
- cost and concurrency pressure;
- worker loss and duplicate callbacks;
- quality defects that can and cannot be repaired.

The expected outcome may not be selected by story ID. Shuffle IDs and prove the same evidence produces the same decision.

---

# 9. Focused production integration order

Each item below is its own focused PR from current `main`, or a clearly documented stacked base. Do not combine the entire dormant package into one implementation PR.

## PR A — Cryptographic stage and package identity

Reference modules:

- `artifact_manifest.py`;
- `stage_artifact_contract.py`;
- `lineage_graph.py`.

Required behavior:

- hash video, story, claims, captions, thumbnail, media inputs, renderer version, and relevant reports;
- bind facts, fallback, technical review, editorial review, performance, approval, and publication records to the exact manifest;
- recalculate hashes during evaluation;
- stop relying on mtime as final identity.

Negative controls:

- replace the video after judgment;
- copy an old verdict;
- modify story or claims after render;
- replace captions or thumbnail;
- swap media or package files;
- reuse an approval on another manifest.

Every case must quarantine.

## PR B — Mandatory factual modes and semantic claims

Reference modules:

- `claim_registry.py`;
- `semantic_claims.py`;
- factual rewind behavior in the controller.

Required factual modes:

- `verified`;
- `illustrative_model`;
- `historical_reconstruction`;
- `fictional`;
- `pure_visualization`.

Missing mode quarantines. Factual modes require structured claims tied to beat IDs and evidence. Modeled values require inputs, assumptions, calculation, uncertainty, and presentation language.

Negative controls include uncovered superlatives, comparisons, geography, causality, history, science, health, institutions, vague “research says” claims, and unrelated claim reuse.

## PR C — Provider routing and independent headless review

Reference modules:

- `provider_pool.py`;
- `adapter_contracts.py`;
- `judge_evidence.py`;
- `judge_contract.py`;
- `judge_orchestrator.py`.

Required behavior:

- route by capability, health, quota, cost, latency, determinism, and recent errors;
- maintain independent fallback provider families;
- technical and editorial judges must not share provider or model family;
- judges receive evidence only, not implementation intent or prior verdicts;
- borderline disagreement invokes policy or quarantine;
- verdicts bind to exact manifest and video hashes.

## PR D — Durable execution state

Reference modules:

- `execution_ledger.py`;
- `checkpoint_store.py`;
- `replay_engine.py`.

Required behavior:

- append-only hash-chained events;
- idempotency keys for callbacks;
- expiring leases for claimed work;
- worker-loss recovery;
- deterministic replay;
- duplicate outcomes cannot advance a story twice;
- artifact, cost, attempt, and state history remains auditable.

## PR E — Bounded autonomous batch controller

Reference modules:

- `production_stage_graph.py`;
- `autonomous_decision_engine.py`;
- `autonomous_batch_controller.py`;
- `autonomous_program.py`;
- `resource_governor.py`;
- `render_scheduler.py`.

Required behavior:

- register up to 50 stories;
- admit only a bounded diverse active wave;
- enforce topic, format, provider, concurrency, retry, repair, re-author, and budget limits;
- incomplete evidence holds;
- exhausted paths quarantine;
- one failed story does not stall healthy stories;
- publishing stays disabled.

## PR F — Idea funnel and portfolio admission

Reference modules:

- `idea_funnel.py`;
- `story_intake_contract.py`;
- `portfolio_optimizer.py`;
- `repetition_ledger.py`.

Required behavior:

- score audience value, novelty, evidence, visual feasibility, cost, and risk;
- reject duplicate premises;
- control topic, format, hook, and visual concentration;
- reserve exploration capacity;
- produce auditable selection reasons;
- never use story identity as a quality signal.

## PR G — Deterministic fault-injected 50-story simulation

Reference modules:

- `autonomous_simulator.py`;
- `fault_injection.py`;
- `batch_acceptance.py`;
- `observability.py`;
- `launch_readiness.py`.

Required behavior:

- same seed and inputs produce the same trace;
- inject provider, worker, factual, artifact, judge, quality, and budget faults;
- verify expected recovery, hold, rewind, and quarantine outcomes;
- enforce completion, quarantine, cost, quality, factual, integrity, judge, hook, and visual-diversity thresholds;
- preserve the full execution ledger.

## PR H — Controlled learning after stable shadow operation

Reference modules:

- `controlled_learning_loop.py`;
- `experiment_attribution.py`;
- `policy_snapshot.py`;
- `drift_monitor.py`.

Required behavior:

- controlled variants across multiple stories;
- minimum samples and impressions;
- effect floors and guardrail ceilings;
- bounded parameter deltas;
- evidence-hashed proposal;
- canary requirement;
- tested rollback;
- no self-activation from one result.

---

# 10. Creative-quality adoption

The dormant creative modules are useful only when connected to actual story and render data through generic adapters.

When integrating creative quality:

- compare multiple hook candidates before render;
- require a clear opening promise and visual proof path;
- detect repeated transition families and visual runs;
- detect long explanation runs, flat energy, missing character action, and dormant curiosity gaps;
- require character attempt, obstacle, reaction, adaptation, consequence, and closure;
- bind opening questions to specific answers, proof, consequences, and callbacks;
- rank media candidates for relevance, geography, era, signage, currency, visible action, licensing, composition, and duplication;
- cap automated repair at two rounds before re-authoring or quarantine;
- measure before and after with blind evidence.

Known flagship defects are regression fixtures, not code dispatch keys. The system should catch the same classes on any story.

Creative acceptance targets for a production candidate should include:

- blind overall score at least 7.5/10;
- personality at least 4/5 where a character-led format applies;
- no known contextual media error;
- no material degraded fallback in the opening;
- no dominant repeated chapter-card family;
- no unresolved hook promise;
- no judge hard blocker.

Do not treat taste as a perfectly closed numeric domain. Preserve blind review and human escalation for ambiguous cases.

---

# 11. Shadow, canary, and rollout

## Shadow operation

Complete at least three heterogeneous shadow batches before autonomous public publication.

Each batch must:

- use the full 50-story intake, or the maximum integrated capacity at that phase;
- run with publication disabled;
- exercise provider fallback and bounded recovery;
- produce hash-bound artifacts and independent verdicts;
- preserve complete durable execution history;
- meet batch acceptance thresholds;
- have zero unresolved hard blockers;
- prove a failed story does not stall the portfolio.

## Controlled public canaries

After every launch blocker is clear:

1. owner approves the exact manifest-bound candidate;
2. expected-channel guard is active;
3. kill switch and rollback are tested;
4. publish exactly one canary;
5. verify remote identity, metadata, and expected channel;
6. freeze publication again;
7. inspect all evidence and incidents;
8. repeat until at least three autonomous canaries pass.

One successful canary does not authorize scheduled publication.

## Scheduled rollout

Scheduled autonomous publication may be considered only after the formal launch gate passes. Start with the lowest cadence and smallest exposure allowed by policy. Maintain automatic freeze conditions for:

- artifact mismatch;
- wrong channel;
- invalid or disagreeing verdicts;
- facts failure;
- provider or media outage beyond fallback capacity;
- performance or budget violation;
- repeated quarantine;
- upload verification failure;
- unexpected drift;
- missing rollback or kill-switch health.

---

# 12. Formal launch gate

Use `assess_launch_readiness()` as the evidence checklist.

Launch requires all of the following:

- 100% authored autonomy reference coverage;
- 100% verified isolated test execution;
- 100% required adapter integration;
- successful deterministic 50-story simulation;
- at least three heterogeneous shadow batches;
- at least three autonomous canaries;
- active hash-bound artifact identity;
- active factual modes and semantic claim coverage;
- active independent technical and editorial judges;
- active durable execution state;
- active provider fallbacks;
- active bounded recovery;
- active budget and concurrency controls;
- active monitoring and alerting;
- tested rollback;
- tested kill switch;
- active expected-channel guard;
- publishing disabled by default;
- zero unresolved hard blockers.

Anything less is not launch-ready.

---

# 13. Evidence required in every implementation PR

Every PR report must contain:

- problem and root cause;
- exact base SHA and head SHA;
- exact files changed;
- architecture or data-flow impact;
- tests, commands, exit codes, and counts;
- negative controls;
- workflow run on the exact head SHA;
- fixture, render, or package evidence where applicable;
- before/after behavior;
- quality impact;
- performance, resource, and cost impact;
- security and publishing-safety impact;
- rollback procedure;
- remaining risks;
- explicit definition of done.

Do not say “green,” “safe,” “production ready,” “autonomous,” or “100%” without naming the exact measurement and evidence.

---

# 14. Claude working method

## At the beginning of every session

1. Read this file and the handoff manifest.
2. Inspect current Git state and relevant PR metadata.
3. Identify the first uncompleted phase.
4. State the exact scope and files you intend to touch.
5. Preserve publishing freeze and fail-closed rules.
6. Execute; do not merely restate the plan.

## During work

- keep commits focused;
- show concrete defects as soon as found;
- prefer generic fixes over story patches;
- preserve or strengthen negative controls;
- record exact commands and outputs;
- do not silently expand scope;
- do not merge or enable publishing without owner authorization.

## At the end of every session

Report:

- exact head SHA;
- commits made;
- files changed;
- tests passed, failed, skipped, and unrun;
- workflow statuses;
- artifacts produced;
- what is now proven;
- what remains unproven;
- the single highest-value next action.

---

# 15. Common failure modes to avoid

- Adding more dormant architecture after the finite rubrics are closed.
- Importing `experiments.curiosity_nextgen` wholesale into production.
- Creating one giant mixed implementation PR.
- Using a story slug, title, or ID to select a repair.
- Calling authored tests “passing” before executing them.
- Treating one fixture, three fixtures, or one canary as portfolio proof.
- Weakening facts, visual, integrity, performance, or publish gates to achieve a pass.
- Using generic cards as the blanket response to missing media.
- Trusting mtime as package identity.
- Letting the same provider or model family author and independently judge the same work where independence is required.
- Allowing duplicate callbacks or expired workers to advance state twice.
- Letting one failed story halt the entire portfolio.
- Activating a learning proposal without controlled multi-story evidence, canaries, and rollback.
- Enabling scheduled publication while integration or shadow work is in progress.
- Committing generated videos to Git.

---

# 16. Current readiness interpretation

These are different measurements and must stay separate.

## Finite authored reference readiness

- structural reference coverage: 100%;
- autonomy reference coverage: 100%;
- Claude handoff coverage: complete after this playbook and manifest.

## Verified dormant implementation

- compile verification: not yet claimed on the final PR #173 head;
- contract execution: 0% claimed until all 425 tests are run successfully;
- CI attachment: none required or claimed for the dormant package yet.

## Production integration

- PR #172 recovery implementation: approximately 90% correct within its recovery scope, based on documented tests and canary evidence;
- safe single-video recovered path: approximately 85%;
- repeatable multi-video live channel: approximately 48%;
- fully autonomous live channel: approximately 30%;
- public autonomous rollout: 0%.

The operational percentages are estimates, not formal rubric outputs. Replace them with measured launch-readiness evidence as integration progresses.

---

# 17. Copy-paste initial Claude prompt

Use this prompt at the beginning of the next Claude Code session:

```text
You are continuing the Curiosity autonomous-video work in caleblschulte0-ux/Shorts-pipeline.

Read these files in order before changing code:
1. docs/CLAUDE_MASTER_PLAYBOOK.md
2. docs/CLAUDE_HANDOFF_MANIFEST.json
3. docs/CURIOSITY_FINAL_REPORT.md
4. docs/CLAUDE_AUTONOMY_LAUNCHOFF.md
5. docs/CLAUDE_EXECUTION_CHECKLIST.md
6. experiments/curiosity_nextgen/README.md

The production recovery is PR #172. The dormant autonomous reference surface is PR #173. Publishing must remain disabled. Do not merge PR #173 wholesale, do not add another dormant subsystem, do not optimize by story slug or title, and do not claim tests passed until you execute them.

Your immediate job is:
- fetch the repository and inspect current SHAs;
- check out PR #173;
- run `python -m compileall experiments/curiosity_nextgen`;
- run `python -m unittest discover -v experiments/curiosity_nextgen/tests`;
- fix every failure without weakening contracts or touching production paths;
- add regression coverage for any newly discovered edge;
- report exact commands, exit codes, test counts, duration, files changed, commits, and final head SHA.

After the dormant suite is fully green, reconcile PR #172 with current main while preserving the publishing freeze, rerun the recovery checks on the exact merge SHA, and then begin focused production integration with PR A: cryptographic stage and package identity.

Do not return only a plan. Execute the first uncompleted phase and provide evidence.
```

---

# 18. Final definition of done

This project is done only when the reusable system can safely manage a heterogeneous 50-video portfolio, recover from realistic faults, satisfy factual and creative quality gates, produce hash-bound independently judged packages, complete three shadow batches and three controlled canaries, preserve a tested rollback and kill switch, and remain unable to publish without explicit policy authorization.

Until then, report progress honestly by phase. The dormant architecture is closed. The work now is execution, integration, evidence, and controlled launch.