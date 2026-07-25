# Next-Level Review Prototypes

> **NOT WIRED. NOT IMPORTED. NO PIPELINE EFFECT.**

Everything in this directory is an isolated reference implementation for Claude
to review later. No existing file imports these modules. No workflow invokes
them. They use only the Python standard library and write nowhere unless a caller
explicitly instantiates a temporary/local store.

## Files

- `semantic_scene_planner.py`
  - validates story intent against chart and performance capabilities;
  - ranks compatible plans;
  - enforces diversity without allowing semantic mismatch.
- `judge_ensemble.py`
  - combines objective, primary-vision, and adversarial verdicts;
  - preserves disagreement and blocks missing evidence.
- `quality_state_machine.py`
  - calculates phase eligibility from two complete benchmark runs;
  - prevents manual phase inflation and detects regression.
- `exemplar_registry.py`
  - content-addressed exemplar/rejection memory with anti-copy retrieval rules.
- `benchmark_lab.py`
  - plans versioned full-suite runs and calculates consistency/regression reports;
  - deliberately contains no renderer or subprocess integration.
- `test_semantic_scene_planner.py`
- `test_judge_ensemble.py`
- `test_quality_state_machine.py`

## Adoption rule

Claude should not copy these files directly into production. For each concept:

1. Compare the prototype contract with the current live interfaces.
2. Write an integration plan.
3. Add production code in a separate implementation commit.
4. Add unit and integration tests.
5. Run complete benchmark videos.
6. Report before/after evidence.
7. Keep the implementation only if the full system improves without regression.

## Safety invariant

This branch must continue to contain only newly added review material. If an
existing runtime, workflow, configuration, or state file must change, that belongs
in a later Claude implementation branch—not this review-only PR.
