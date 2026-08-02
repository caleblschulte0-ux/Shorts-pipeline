# Claude Execution Handoff — Review Only

> **Status:** REVIEW MATERIAL ONLY
>
> This file is intentionally not imported, invoked, or referenced by any production workflow. It changes no runtime behavior. Claude should review this package, compare it against the live implementation, and deliberately adopt only validated pieces.

## Current verified state

Branch inspected: `claude/shorts-pipeline-data-handoff-ea2zmb`

Verified head: `5dc49c8182ed4e45097ada67ea3b992a39cdcbce`

The branch contains meaningful progress beyond the original mascot patch:

- six-story structural benchmark
- failure census
- scene timeline scaffolding
- mascot primitive checks
- scene-addressable repair candidate generation
- bounded repair controller
- quality phases
- preview workflow structural gates

However, the following gaps remain material.

## Highest-priority gaps

### 1. The proving workflow bypasses the repair controller

The preview workflow still performs a one-shot render through `post_stories.py`. It prints the verdict and stops. The normal proving path must eventually call the bounded repair controller, while retaining a separate one-shot debugging mode.

### 2. “Keep best” is not transactional

The controller remembers the best verdict but does not preserve and restore the corresponding plan, MP4, scene assets, and canonical verdict. A losing repair can remain persisted even when the summary says an earlier attempt was best.

### 3. Weakest-scene selection is inferred from prose

The repair code searches verdict text for `segN` and otherwise defaults to the last segment. The showrunner should emit structured scene identity, timestamps, visible evidence, root cause, and repair goal.

### 4. Candidate ranking is mostly mechanical

Current candidate scoring emphasizes effective FPS, alpha fullness, and contact coverage. Those metrics are useful prefilters, but they cannot determine whether a candidate explains the claim, fits narration, is visually coherent, or is entertaining. Surviving candidates need blind visual comparison.

### 5. Structural checks partially certify intent rather than appearance

Attachment sidecars and programmed action descriptions prove that the generator intended contact and consequence. They do not prove that hands align visually, clipping is absent, scale is believable, or the performance reads to a viewer.

### 6. Performance vocabulary is narrow

The current benchmark heavily reuses dragged/airborne and shoved/launched mechanics. This solves decorative idling but risks replacing it with a formulaic visual grammar.

### 7. Finished-video quality remains unproven

The code is still configured for quality phase 1. There is no verified evidence of two consecutive full six-story runs meeting a 90 median and 85 floor under an unchanged judge.

---

# Required execution sequence

Claude should implement these phases in order and report honestly after each phase.

## Phase A — Operational repair loop

1. Add isolated attempt directories.
2. Snapshot incumbent scene plans before each repair.
3. Render each attempt into its own directory.
4. Compare full-video verdicts.
5. Promote the winner transactionally.
6. Restore the incumbent after a losing attempt.
7. Wire the repair controller into the proving workflow.

### Acceptance tests

- Baseline 68, repair 54 → baseline plan/video remain canonical.
- Baseline 68, repair 76 → repaired plan/video become canonical.
- Missing verdict → no promotion.
- Hard-failing repair cannot replace a non-hard-failing incumbent.

## Phase B — Structured diagnosis

Extend showrunner output with:

```json
{
  "weakest_scene": {
    "id": "segment_1",
    "index": 1,
    "start": 7.2,
    "end": 12.8,
    "failure_class": "decorative_mascot",
    "visible_evidence": "Data tracks the bar edge without a readable objective.",
    "root_cause": "Position is coupled, performance is not.",
    "repair_goal": "Create goal, effort, reversal, and consequence."
  }
}
```

Remove prose parsing from the normal path. Keep any fallback explicitly logged as degraded diagnosis.

## Phase C — Two-stage candidate selection

### Objective prefilter

Reject candidates for:

- low effective FPS
- excessive duplicate frames
- clipping
- overflow
- invalid safe margins
- missing contact metadata
- incompatible data shape
- invalid labels

### Visual ranking

Blindly rank survivors for:

- claim clarity
- narration fit
- readable cause and consequence
- mascot purpose
- composition
- novelty
- payoff
- overall preference

No candidate should win solely because it fills more pixels.

## Phase D — Honest benchmarks

Maintain separate reports:

- `benchmark_structural.json`
- `benchmark_visual.json`
- `benchmark_full_video.json`

A story passes globally only when all required layers pass.

Replace ambiguous causal checks with:

- `mascot_contacts_data`
- `visual_contact_verified`
- `data_affects_mascot`
- `mascot_affects_data`
- `cause_consequence_readable`
- `performance_supports_claim`

## Phase E — Broader performance library

Build and validate at least twelve performance families beyond drag/shove, such as:

- stack
- balance
- catch
- carry
- block
- race
- climb
- compress
- stretch
- bury/overwhelm
- discover
- compare
- transform
- recover

Select by narrative relationship and emotional meaning, not chart kind alone.

## Phase F — Hook and ending tournaments

For weak stories:

1. Generate three structurally distinct three-second hooks.
2. Prefilter technically.
3. Blind-rank visually.
4. Use only the winner in the complete render.

Repeat with at least two ending candidates when payoff is weak.

## Phase G — Quality milestones

### Phase 1

- six complete stories
- two consecutive runs
- median ≥ 70
- floor ≥ 65
- zero hard failures
- active-scene effective FPS ≥ 24
- no decorative mascot failures
- verified rollback

### Phase 2

- median ≥ 80
- floor ≥ 75
- no dominant repeated performance family
- hook and payoff dimensions meet target
- two consecutive runs

### Final 90 gate

- median ≥ 90
- floor ≥ 85
- zero hard failures
- no judge weakening
- no random rerolls
- transactional winner restoration proven
- artifacts retained
- two consecutive full-suite runs

---

# Next-level work after consistent 90s

Once the 90 gate is real, continue with:

1. **Exemplar retrieval:** index high-scoring scene structures by relationship, claim type, and payoff pattern.
2. **Reject memory:** block known weak structures before render.
3. **Novelty budgeting:** prevent the same action family, camera move, or payoff from dominating a batch.
4. **Counterfactual judging:** ask whether a simpler scene explains the claim better.
5. **Audience signal loop:** compare judge scores with retention, rewatches, shares, comments, and follows without allowing engagement metrics to excuse factual or craft failures.
6. **Calibration drift checks:** preserve fixed weak/baseline/strong reference videos so judge changes cannot silently inflate scores.
7. **Cost-aware search:** spend extra candidate renders only on scenes with the highest expected score gain.
8. **Regression attribution:** identify which renderer subsystem caused each score movement.

---

# Required status report format

After every phase, Claude should report:

## Completed
Only implemented, wired, rendered, and validated work.

## Partial
Code that exists but is not fully integrated or proven.

## Not completed
Everything remaining.

## Tests
Exact commands and outcomes.

## Full renders
Story slugs, run IDs, verdicts, artifact paths.

## Before/after
Scores, failures, temporal metrics, and regressions.

## Next bounded task
One clearly defined next phase.

The governing rule is:

> Existing code is not a completed capability until the real workflow executes it and rendered evidence proves it.