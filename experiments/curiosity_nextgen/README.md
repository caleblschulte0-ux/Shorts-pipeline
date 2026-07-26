# Curiosity Next-Generation Prototypes

This directory contains **real but dormant code** for Claude to inspect, test, refine, and selectively integrate later.

## Isolation contract

Nothing in the active pipeline imports this package. This directory does not modify workflows, configuration, scheduling, publishing, rendering, story data, or CI. All modules use the Python standard library only.

## Autonomy contract

The system is designed to improve and schedule **up to 50 arbitrary videos**, not optimize named videos through bespoke logic.

- Story IDs are opaque identifiers, never dispatch keys for special-case behavior.
- Repair tasks must be derived from reusable defect codes, story metadata, evidence, and policy thresholds.
- No production-shaped module may contain a named-video blueprint or hard-coded story slug.
- Any new creative rule must generalize across multiple topics, formats, lengths, and media mixes.
- Story-specific observations may be used as retrospective evidence, but they must be converted into reusable contracts before entering the system.

## Current reference-surface status

- **63 dormant prototype modules**
- **289 authored contract tests** across eight test files
- **27 required structural domains** in the strict completeness rubric
- **100% authored structural reference coverage** when `complete_reference_evidence()` is assessed
- **three dormant creative-quality layers** covering story shape, viewer experience, retention risk, comprehension, captioning, continuity, frame readability, humor, emotion, and portfolio-scale edit planning
- **0% verified execution coverage claimed** until the isolated tests are actually run
- **0 production imports, workflow changes, or publishing changes**

`structural_completeness.py` deliberately separates two scores:

1. `reference_coverage_percent` — whether every required structural domain has isolated reference code and positive/negative test references;
2. `verified_execution_percent` — whether those contracts were actually executed successfully.

The dormant structure reaches 100% on the first measure only. It cannot report 100% verified execution unless every domain is explicitly marked verified. Creative-quality modules are additional reference implementations and do not change that structural denominator.

## Included prototypes

### Artifact and release integrity

- `artifact_manifest.py` — SHA-256 package manifests and report binding.
- `package_readiness.py` — fail-closed aggregation of manifest, facts, judge, fallback, performance, catalog, technical, and channel gates.
- `approval_token.py` — one-time HMAC-signed approvals bound to one manifest, one channel, one expiry window, and one upload.
- `freeze_controller.py` — fail-closed release state machine with automatic freezing and mandatory post-canary refreeze.
- `lineage_graph.py` — artifact/report dependency graphs, missing-parent and cycle checks, manifest continuity, stale-descendant detection, and impact analysis.
- `audit_chain.py` — tamper-evident, hash-chained operational audit records.

### Schema evolution and deterministic recovery

- `schema_registry.py` — versioned payload schemas, strict validation, sensitive-field reporting, and backward/forward/full compatibility checks.
- `migration_planner.py` — complete migration-path discovery, lossy-change blocking, reversibility warnings, and manual-review holds.
- `replay_engine.py` — canonical run envelopes, stage digests, deterministic replay comparison, dependency/version drift, order drift, and duration regressions.
- `checkpoint_store.py` — idempotent stage checkpoints, bounded retries, stale-input detection, quarantine handling, and resume plans.
- `environment_lock.py` — platform, dependency, tool-version, and environment-variable reproducibility contracts.

### Editorial quality and repair

- `quality.py` — weighted quality decisions with mandatory hard floors.
- `repair_planner.py` — defect-specific repair selection, priority ordering, two-round limits, and human re-author escalation.
- `repetition_ledger.py` — cross-video hook, closing, transition, character-action, visual-family, and asset-reuse controls.
- `portfolio_optimizer.py` — transparent cost, readiness, diversity, novelty, and exploration-aware story portfolio selection.
- `generalization_suite.py` — multi-archetype, multi-topic, mixed-media, positive/negative story-fixture coverage.

### Direct creative-quality improvement

- `hook_lab.py` — compares hook candidates on clarity, curiosity, stakes, specificity, surprise, first-image strength, payoff promise, duration, and opening delay.
- `beat_dynamics.py` — detects flat energy, repetitive visual-family runs, dense explanation clusters, missing character action, dormant curiosity gaps, and weak beat turns.
- `chapter_style_planner.py` — assigns diverse chapter-transition families while penalizing dominance, consecutive reuse, and topic/tone mismatch.
- `personality_arc.py` — evaluates emotional progression, purposeful action variety, obstacles, consequences, and setup/payoff callbacks.
- `payoff_contract.py` — binds opening questions and promises to explicit answers, visual proof, consequences, callback closure, and timing.
- `creative_uplift.py` — converts arbitrary creative-quality signals into story-agnostic repair tasks, validates dependencies, filters weak signals, and prioritizes high-leverage work under an effort budget.
- `curiosity_curve.py` — tracks open questions, promised answer timing, revelation droughts, loop overload, stakes movement, and visual proof of major answers.
- `narration_rhythm.py` — measures words per minute, sentence-length variation, opening density, emphasis, breathless runs, and pause budget.
- `visual_grammar.py` — assigns scene families by intent and requirements while controlling repeated families, text-card share, and visual dominance.
- `scene_choreography.py` — checks purposeful subject action, camera vocabulary, focal progression, screen direction, and visible cause/effect.
- `audio_dynamics.py` — evaluates narration masking, music-energy arcs, effect density, silence, and hook/payoff emphasis.
- `promise_packaging.py` — ranks title/thumbnail combinations for specificity, credibility, focal clarity, curiosity, and honest payoff alignment.
- `viewer_experience.py` — combines creative areas into a weighted pass/revise/reject decision with hard floors and prioritized repairs.

### Retention, comprehension, and edit quality

- `retention_risk.py` — heuristic moment-level retention-risk scoring, early/payoff weighting, weak-interest, overload, sensory-stasis, proof, static-hold, repetition, jargon, and loop-overload defects. It explicitly does not claim to predict real analytics.
- `cognitive_load.py` — measures simultaneous narration, reading, concepts, numbers, entities, visual elements, jargon, context dependency, examples, and recovery pauses.
- `caption_readability.py` — audits reading speed, line count and length, contrast, mobile safe areas, focal overlap, semantic line breaks, and emphasis hierarchy.
- `continuity_editor.py` — detects geography, era, wardrobe, prop, time-of-day, lighting, screen-direction, and factual-context continuity breaks while allowing explained intentional transitions.
- `visual_readability.py` — checks focal hierarchy, object clutter, tiny evidence, contrast, focal separation, competing motion, caption zones, evidence legibility, and decorative noise.
- `humor_personality.py` — evaluates setup, surprise, relevance, tone, character specificity, punchline speed, repeated devices, factual interruption, callback closure, and harmful targeting.
- `emotional_resonance.py` — measures human specificity, visible consequences, emotional change, relevance, authenticity, emotional range, earned stakes, and setup/payoff closure.
- `edit_blueprint.py` — builds dependency-aware per-story edit plans and an autonomous portfolio program for up to 50 stories with per-story and total effort budgets, topic/format caps, quarantine, and deferral.

### Facts and media

- `claim_registry.py` — factual-mode enforcement, claim-signal detection, source requirements, and beat-level coverage.
- `semantic_claims.py` — sentence-level factual assertions, confidence scoring, type compatibility, duplicate IDs, and overbroad mapping detection.
- `media_ranker.py` — auditable candidate ranking and hard rejection rules.

### Visual-judge and human-review control plane

- `judge_contract.py` — hash-bound verdict validation and multi-judge consensus.
- `judge_evidence.py` — blind judge evidence-package completeness, hash binding, duration, media-type, and information-leak checks.
- `judge_orchestrator.py` — independent technical/editorial/tiebreaker assignment across distinct provider and model families.
- `review_queue.py` — separation-of-duties review assignment, SLA expiry, escalation, approval, and rejection state.
- `adapter_contracts.py` — provider capability negotiation, schema compatibility, determinism, idempotency, and judge independence.

### Performance and catalog control

- `shot_cache.py` — deterministic cache keys and selective repair planning.
- `render_budget.py` — draft, review, and production render estimates with time, memory, and cache-reuse budgets.
- `render_scheduler.py` — value-per-cost queue planning with time, slot, readiness, profile, and topic-family constraints.
- `resource_governor.py` — workload admission, provider-call quotas, memory/time limits, low-cache backpressure, and dependency-aware deferral.
- `story_catalog.py` — explicit story lifecycle and scheduler eligibility.
- `catalog_triage.py` — story readiness scoring, deterministic next actions, blocker severity, and repair-budget handling.

### Resilience, lifecycle, and security

- `circuit_breaker.py` — closed/open/half-open dependency protection with bounded recovery probes.
- `security_scanner.py` — recursive credential, private-key, bearer-token, PII, internal-instruction, and unapproved-host detection plus redaction.
- `fault_injection.py` — critical-fault campaign coverage and expected fail-safe outcome validation.
- `resilience_lab.py` — integrated dormant preflight across schema, security, lineage, checkpoints, dependency health, and resource admission.
- `lifecycle_controls.py` — retention, legal hold, purge planning, RPO/RTO recovery assessment, rollback planning, and staged rollout controls.
- `policy_snapshot.py` — canonical immutable policy snapshots, parent linkage, hash binding, and controlled runtime overrides.
- `drift_monitor.py` — quality/performance baseline drift, watch/hold/freeze severity, and missing-observation holds.

### Orchestration and operations

- `integration_lab.py` — isolated end-to-end simulation from claims and evidence through gates, package readiness, and release freeze decisions.
- `observability.py` — append-only event ledger, duplicate detection, run summaries, pass/hold/quarantine rates, p95 duration, and reason aggregation.
- `pipeline_status.py` — weighted implementation, evidence, readiness, blocker, and priority scoring.
- `structural_completeness.py` — strict 27-domain meta-audit that refuses 100% for any missing, invalid, untested, or non-isolated reference domain.

### Learning

- `experiment_attribution.py` — controlled rate experiments with sample-size, statistical, effect-size, and guardrail decisions.

### Tests

- `tests/test_prototypes.py` — foundational prototype contracts.
- `tests/test_decision_intelligence.py` — decision-layer contracts.
- `tests/test_structural_hardening.py` — factual, evidence, judge independence, catalog, scheduling, approval, freeze, observability, and integration negative controls.
- `tests/test_resilience_controls.py` — schema evolution, migration, lineage, deterministic replay, checkpoints, circuit breakers, workload governance, leak scanning, fault campaigns, and integrated resilience negative controls.
- `tests/test_completeness_closure.py` — policy, adapters, audit integrity, human review, retention, disaster recovery, rollback, rollout, reproducibility, drift, portfolio diversity, generalization, and strict 100% completeness scoring.
- `tests/test_creative_quality.py` — 41 generic hook, beat-rhythm, chapter-variety, personality, payoff, signal-conversion, dependency, and uplift-planning contracts.
- `tests/test_viewer_quality.py` — 52 curiosity, narration, visual-grammar, choreography, audio, packaging, and unified viewer-experience contracts.
- `tests/test_retention_quality.py` — 38 generic retention, comprehension, caption, continuity, readability, humor, emotion, per-story edit, and 50-story portfolio-planning contracts.

## Run locally

```bash
python -m unittest discover experiments/curiosity_nextgen/tests
```

The tests are intentionally not connected to the repository's active CI. This keeps the experiment package from affecting current production checks. A future integration PR should run the selected module's tests in an isolated job before any production import is added.

## Adoption rule

Claude should not import these modules into production wholesale. Validate them against a heterogeneous catalog containing multiple topic families, formats, durations, media modes, and difficulty levels. Derive generic defects for each candidate, build a portfolio edit program for up to 50 stories, quarantine hard blockers, repair admitted stories, render varied fixtures, and compare blind viewer-experience evidence. No story slug may select bespoke repair logic.
