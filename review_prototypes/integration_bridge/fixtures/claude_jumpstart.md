# Claude Jumpstart — Shadow Integration Bridge

This is an executable jumping-off point for adapting the review-only quality systems to the real explainer pipeline.
It does not authorize direct production wiring, publishing, or weakening the showrunner.

## Frozen boundaries

- Production modified: **false**
- Publishing enabled: **false**
- Showrunner authority changed: **false**
- Production contract probe: **100.0%**
- Migration gate readiness: **54.5%**

## Exact production targets

### Phase 0 — Contract lock
Freeze production symbols and schemas before Claude edits anything.
- `data_learning/story.py::build` — After viz_director.assign, optionally read a prevalidated bridge plan and attach kind/perf_override/plan_locked to each insight; default path remains byte-for-byte behaviorally identical.
  - Guard: QUALITY_BRIDGE_MODE=shadow|apply; default off; reject slug/fingerprint/segment-count mismatch.
  - Rollback: unset QUALITY_BRIDGE_MODE and delete the plan sidecar
- Gate [PASS] production contract probe: all required symbols/SHAs verified
- Gate [PASS] shadow adapter tests: duck-typed adapter and non-mutating apply suite

### Phase 1 — Shadow manifest
Generate bridge plans and manifests beside the baseline with zero render behavior changes.
- `data_learning/studio_render.py::render` — Read the attached scene plan when present, preserve existing segment_windows, and append quality_bridge metadata to the render manifest.
  - Guard: manifest extension only in shadow mode; no upload behavior changes.
  - Rollback: ignore quality_bridge metadata and render from current fields
- `scripts/post_stories.py::main` — Pass quality_bridge scene plans into showrunner context and keep PUBLISH FROZEN during shadow comparison.
  - Guard: never set --publish or PUBLISH_ENABLED; showrunner BLOCK remains sovereign.
  - Rollback: remove quality_bridge from context; no production state changed
- Gate [BLOCKED] baseline preview artifact: same story rendered without bridge
- Gate [BLOCKED] bridge shadow artifact: plan and context emitted without applying
- Gate [PASS] publish freeze: PUBLISH FROZEN and no uploader construction

### Phase 2 — Preview application
Apply bridge plans to copied/runtime objects only in explicit preview mode.
- `data_learning/studio_render.py::_build_soundtrack` — Accept optional frame-snapped audio placements from the bridge while retaining current synthesized SFX as the fallback.
  - Guard: only allow named cues from a fixed library; clamp timing/gain; preview first.
  - Rollback: omit the optional audio plan argument
- Gate [BLOCKED] complete MP4 watched: human/Claude watched the full output, not just frames
- Gate [BLOCKED] two consecutive showrunner passes: locked versions, no single-story regression

### Phase 3 — Repair adoption
Use bridge candidates inside existing scene-addressable blind keep-best repair.
- `scripts/scene_repair.py::propose` — Seed structural candidates from the bridge compiler, then render/score them through the existing blind keep-best machinery.
  - Guard: retain current >0.08 incumbent margin and existing minimal {viz, perf} persisted schema.
  - Rollback: fall back to the current VARIANTS table
- `scripts/repair_loop.py::repair` — Include hook/data_demo/payoff bridge remedies while preserving bounded attempts, monotone keep-best, and stop reasons.
  - Guard: max-iters remains bounded; verdict comparison is unchanged; no code-edit remedies.
  - Rollback: restore the current REMEDIES mapping
- Gate [PASS] repair monotonicity proof: worse candidate rejected and budget bounded
- Gate [PASS] showrunner sovereignty proof: verdict logic unchanged

### Phase 4 — Diagnostic context
Give the showrunner richer plans without changing authority or score rules.
- `scripts/showrunner_review.py::review_video` — Expose bridge-plan adherence as evidence to the brain, but do not alter WEIGHTS, AUTOFAIL_CHECKS, MIN_SCORE, decide_verdict, or fail-closed publish behavior.
  - Guard: contract test forbids edits to sovereign scoring and verdict symbols.
  - Rollback: stop passing bridge context; scoring remains untouched
- Gate [PASS] calibration suite unchanged: WEIGHTS/AUTOFAIL/decide_verdict contract locked
- Gate [BLOCKED] real-channel holdout: controlled batch beats baseline without guardrail regression

## Rules Claude must preserve

1. `SHOWRUNNER` remains sovereign and fail-closed on publish runs.
2. The default bridge mode is off; shadow mode may emit evidence but may not alter rendering.
3. Apply mode is preview-only until complete MP4 review and two consecutive showrunner passes.
4. Existing `state/scene_plans/{slug}.json` remains backward compatible with `{viz, perf}`.
5. No media, models, or render artifacts are committed to git.
