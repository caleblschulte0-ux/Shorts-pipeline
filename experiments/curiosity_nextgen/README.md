# Curiosity Next-Generation Prototypes

This directory contains **real but dormant code** for Claude to inspect, test, refine, and selectively integrate later.

## Isolation contract

Nothing in the active pipeline imports this package. This directory does not modify workflows, configuration, scheduling, publishing, rendering, story data, or CI. All modules use the Python standard library only.

## Autonomy contract

The system is designed to improve, schedule, and control **up to 50 arbitrary videos**, not optimize named videos through bespoke logic.

- Story IDs are opaque identifiers, never dispatch keys for special-case behavior.
- Repair tasks are derived from reusable defect codes, story metadata, evidence, and policy thresholds.
- No production-shaped module may contain a named-video blueprint or hard-coded story slug.
- New rules must generalize across multiple topics, formats, lengths, audiences, factual risks, and media mixes.
- Story-specific observations may be used as retrospective evidence only after they are translated into reusable contracts.
- Every autonomous loop is bounded by retry, repair, re-author, cost, concurrency, evidence, and quarantine policies.

## Current reference-surface status

- **69 dormant prototype modules**
- **361 authored contract tests** across ten test files
- **27 required structural domains** in the strict completeness rubric
- **100% authored structural reference coverage** when `complete_reference_evidence()` is assessed
- **four dormant system layers**: control-plane structure, direct creative quality, viewer/retention quality, and autonomous 50-story operations
- **0% verified execution coverage claimed** until the isolated tests are actually run
- **0 production imports, workflow changes, renderer changes, or publishing changes**

`structural_completeness.py` deliberately separates:

1. `reference_coverage_percent` — whether every required structural domain has isolated reference code and positive/negative test references;
2. `verified_execution_percent` — whether those contracts were actually executed successfully.

The dormant structure reaches 100% on the first measure only. It cannot report passing execution until the suite is run successfully.

## Autonomous 50-story operating layer

- `story_intake_contract.py` — validates heterogeneous story briefs, enforces the 50-story ceiling, rejects unsupported duration/format/media combinations, requires claim contracts for high-risk stories, and reports topic/format concentration.
- `production_stage_graph.py` — defines a deterministic, hash-stable DAG from intake through research, claims, script, storyboard, media, draft render, independent reviews, gate aggregation, repair, final render, packaging, approval, and publish.
- `autonomous_decision_engine.py` — converts generic stage outcomes into advance, retry, wait, research-more, re-author, repair, or quarantine decisions with bounded recovery.
- `autonomous_batch_controller.py` — admits a diverse active wave, enforces topic/format concurrency, claims stage work under capacity, tracks attempts and spend, rewinds failed stories, holds incomplete evidence, and quarantines exhausted runs.
- `batch_acceptance.py` — evaluates the whole program on completion, quarantine, quality floors, hash binding, factual evidence, independent judge passes, hard blockers, and hook/visual diversity.
- `autonomous_program.py` — compiles accepted story briefs into one deterministic program, registers the batch, admits the initial wave, claims initial work, and coordinates repeatable outcome/assignment cycles.

This layer does not call providers, render videos, publish, or mutate the live catalog. It is an isolated control reference for later selective integration.

## Creative and viewer-quality layers

- `hook_lab.py`, `beat_dynamics.py`, `chapter_style_planner.py`, `personality_arc.py`, and `payoff_contract.py` assess story shape, opening strength, pacing, visual variety, character movement, and payoff closure.
- `creative_uplift.py` converts arbitrary creative signals into story-agnostic repair tasks and prioritizes high-leverage work under an effort budget.
- `curiosity_curve.py`, `narration_rhythm.py`, `visual_grammar.py`, `scene_choreography.py`, `audio_dynamics.py`, `promise_packaging.py`, and `viewer_experience.py` assess the full viewer experience.
- `retention_risk.py`, `cognitive_load.py`, `caption_readability.py`, `continuity_editor.py`, `visual_readability.py`, `humor_personality.py`, `emotional_resonance.py`, and `edit_blueprint.py` convert moment-level defects into generic per-story and portfolio-scale edit plans.

## Structural control plane

The remaining modules cover artifact hashing, provenance, factual claims, media ranking, independent judges, human review, package readiness, approval tokens, release freezes, policy snapshots, audit chains, schema migration, lineage, replay, checkpoints, environment locks, caching, render budgets, scheduling, resource governance, security scanning, fault injection, lifecycle controls, drift, observability, experiments, and strict structural completeness.

## Tests

- `tests/test_prototypes.py` — foundational prototype contracts.
- `tests/test_decision_intelligence.py` — decision-layer contracts.
- `tests/test_structural_hardening.py` — factual, judge, catalog, scheduling, approval, freeze, observability, and integration negative controls.
- `tests/test_resilience_controls.py` — schema, migration, lineage, replay, checkpoints, dependency, workload, leak, fault, and resilience controls.
- `tests/test_completeness_closure.py` — policy, adapters, audit, human review, recovery, rollout, reproducibility, drift, portfolio, generalization, and strict completeness.
- `tests/test_creative_quality.py` — 41 generic hook, rhythm, variety, personality, payoff, signal-conversion, dependency, and uplift contracts.
- `tests/test_viewer_quality.py` — 52 curiosity, narration, visual-grammar, choreography, audio, packaging, and unified viewer-experience contracts.
- `tests/test_retention_quality.py` — 38 generic retention, comprehension, caption, continuity, readability, humor, emotion, edit, and portfolio contracts.
- `tests/test_autonomous_core.py` — 38 intake, production-DAG, evidence, bounded-recovery, and story-ID-independence contracts.
- `tests/test_autonomous_program.py` — 34 controller, 50-story capacity, concurrency, budget, rewind, quarantine, batch-acceptance, and program-cycle contracts.

## Run locally

```bash
python -m unittest discover experiments/curiosity_nextgen/tests
```

The tests are intentionally not connected to active CI. This keeps the experiment package from affecting current checks or releases.

## Adoption rule

Do not import this package into production wholesale. Validate it against a heterogeneous 50-story catalog, run every isolated contract, fix defects, connect only generic adapters, and integrate one capability per focused PR. Reject any change where a story slug or named video selects bespoke behavior.
