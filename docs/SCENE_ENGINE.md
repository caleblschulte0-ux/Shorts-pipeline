# The scene engine — mascot/data coupling, scene repair, and quality gates

This documents the systematic rebuild (2026-07-25) that replaced "a mascot
sprite posed near a chart" with a **unified scene system where the mascot and
the data physically affect each other**, plus the measurement/repair machinery
around it. It implements the external architecture review point-by-point.

## 1. Mechanical coupling (contact → cause → consequence)

Every chart beat bakes the host INTO the chart with his grip point ON the data
object (`charts._bake_host`), driven by beat-progress. The VERIFIED primitives
(`mascot_director.VERIFIED_PERFORMANCES`):

| primitive | contact | cause | consequence |
|---|---|---|---|
| `drag_line` | fists clamped on the rising tip | hauls down to stop it | dragged airborne, swinging |
| `pull_down_win` | fists clamped on the falling tip | hauls down | the value yields — grounded victory |
| `shoved_bar` | hands braced on the bar's face | pushes back | skids, then launched off it |
| `hoist_stack` | arms pressed under the fill | holds the pile up | buckles, barely heaves it |

Coupled kinds: trend, pictorial_race/rank/bars, stack, comparison, bubbles,
geo_us/geo_world (+ waffle/share/pictograph auto-route to coupled kinds).

## 2. A performance, not an action name

`mascot_director.performance_for(kind, claim, target)` selects and
parameterises a performance from the story's actual CLAIM (rising / falling /
contest / part-of-whole), returning `{goal, target, action, contact, cause,
consequence, beats[]}`. The chart records it in the attachment sidecar; the
scene-plan override (`insight.perf_override`) wins when a repair chose one.

## 3. One timeline owner

`data_learning/scene_timeline.py` owns the beat's phase boundaries
(`SETUP_END=0.18`, `EFFORT_END=0.74`) and generates the explicit event list
(`plan_scene`) recorded per scene. The mascot animators import these
boundaries; the hook burst constants live there too. No subsystem guesses its
own timing.

## 4. Attachment contract

Every build writes `{slug}_attach.json`: the performance spec, the per-frame
**grip path** (contact every frame), and the scene timeline. Consumed by the
benchmark validator, per-scene metrics, and the repair loop.

## 5. Exactly 30 fps + build-time temporal gate

Chart builds render `ceil(duration*30)` frames and play at exactly 30fps (no
dynamic source rates). `scripts/showrunner_review.temporal_hard_fail` blocks a
render IN CODE, BEFORE the vision review, when measured cadence breaches the
active quality phase's floor. Thresholds come from
`data_learning/quality_milestones.py`:

- phase 1: median ≥ 70, no hard failures (current)
- phase 2: median ≥ 80, every dimension above midpoint
- phase 3: median ≥ 90 across two consecutive runs
- prod: individual ≥ 90 + no hard failure

Raise with `QUALITY_PHASE` env. The gate only ADDS blocks — it never overrides
a showrunner BLOCK (see CLAUDE.md; the showrunner stays sovereign).

## 6. Benchmark suite (structure, not scores)

`data_learning/benchmarks/suite.json` freezes 6 archetype stories (trend,
ranking, part-to-whole, money transformation, scale, direct comparison) with
STRUCTURAL requirements (hook motion by 0.4s, mascot contact every frame, ≥3
performance beats, cause+consequence, ending payoff).
`scripts/benchmark_validate.py` verifies them offline from build artifacts and
runs as a fail-fast CI step: a renderer change must hold across the WHOLE
suite. `STRICT_CONTACT=1` restricts depiction selection to contact-verified
kinds (scene/mechanic inventions rejoin once they guarantee contact).

## 7. Primitive approval gate

`data_learning/tests/test_mascot_primitives.py` renders every primitive in
isolation and asserts: body present, distinct start/mid/end silhouettes,
visible progression (no frozen zone), no canvas clipping. Runs in CI before any
render; a primitive that regresses never ships. (It caught a frozen brace zone
in `pull_down_win` on its first run.)

## 8. Scene-addressable builds, metrics, and repair

- `studio_render._scene_metrics` encodes each scene alone and runs the SAME
  cadence detector + hard gate on it → `output/scenes/{slug}_sceneN.json`.
- `scripts/scene_repair.py`: picks the failing scene from the verdict,
  renders THREE structurally different candidates (kind × performance),
  blind-scores them (cadence + fullness + contact), keeps the winner only past
  a margin, persists to `state/scene_plans/{slug}.json`.
- The renderer applies plans (`insight.plan_locked` skips auto-routing).
- `scripts/repair_loop.py` remedies are now scene repairs. **No variance
  rerolls, no env nudges, no `MASCOT_BRAIN=1`.**

## 9. Failure census

`scripts/failure_census.py` classifies the recent verdict trail into recurring
engineering classes (per story, with recurred-after-fix detection) →
`state/failure_census.json`; printed after every preview run. Recurring classes
are epics, not rerender notes.
