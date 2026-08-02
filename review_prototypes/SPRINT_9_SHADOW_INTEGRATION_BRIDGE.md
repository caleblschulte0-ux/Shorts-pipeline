# Sprint 9 — Shadow Integration Bridge and Claude Jumpstart

This sprint crosses the largest remaining safe boundary: it maps the isolated
viewer-quality systems onto the **actual production contracts** without importing,
modifying, or publishing through the live pipeline.

Everything remains under `review_prototypes/integration_bridge/`.

## The leap

- Duck-typed adapter for the real `data_learning.story.Story` and `Segment` shape.
- Compiler that only emits production-supported depiction kinds and mechanically
  coupled mascot actions already consumed by `charts.py` and `studio_render.py`.
- Non-mutating shadow apply: overrides are applied to a deep copy using existing
  `insight.kind`, `insight.perf_override`, `insight.plan_locked`, and segment fields.
- Backward-compatible `state/scene_plans/{slug}.json` payload generation using the
  current `{viz, perf}` schema.
- Manifest bridge that preserves `segment_windows` while adding scene timelines,
  transitions, audio cues, callback tokens, goals, and targets.
- Showrunner context bridge for better scene-specific diagnosis without changing
  weights, auto-fails, thresholds, verdict authority, or fail-closed behavior.
- Verdict router that turns a sovereign BLOCK into three structural candidates but
  never changes the verdict and never accepts a worse candidate.
- AST/SHA contract probe covering the exact production files and symbols Claude must
  verify before patching.
- Seven exact patch targets across five gated migration phases, each with guards,
  acceptance tests, rollback instructions, and risk level.

## Exact production surfaces mapped

- `data_learning/story.py::build`
- `data_learning/charts.py::_perf_action` and `render_story_build`
- `data_learning/scene_timeline.py::plan_scene`
- `data_learning/studio_render.py::render`, `_build_soundtrack`, `_plan_events`
- `scripts/post_stories.py::main`
- `scripts/showrunner_review.py::review_video` and `decide_verdict`
- `scripts/scene_repair.py::propose`
- `scripts/repair_loop.py::repair`

## Verification

- 39/39 isolated tests passed.
- 8/8 production contract files mapped to frozen branch SHAs.
- 5/5 archetypes and 25/25 scenes compile through the shadow bridge.
- Original Story objects remain unchanged after shadow application.
- Existing manifest fields and `segment_windows` remain unchanged.
- Existing scene-plan persistence schema remains `{viz, perf}`.
- A showrunner BLOCK is never flipped or weakened.
- Production files modified: 0.
- Publishing enabled: false.
