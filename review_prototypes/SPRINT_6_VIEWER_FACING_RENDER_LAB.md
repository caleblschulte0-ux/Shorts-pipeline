# Sprint 6 — Viewer-Facing Render Lab

This sprint moves beyond creative planning into actual deterministic preview output.
It remains isolated under `review_prototypes/visible_quality/render_lab/` and is
not imported by the production pipeline.

## What is implemented

- Real 1080×1920 SVG keyframes for hook, trend, burden, and callback scenes.
- Five inspectable moments per scene: frame one, setup, effort, payoff, and final.
- Caption choreography with short chunks, numeric emphasis, impact timing, and
  role-specific entrances and exits.
- Camera keyframes for snap pushes, tip-following, counter-pans, pressure pullbacks,
  gap dollies, row tracking, and callback pullbacks.
- Synchronized sound-design manifests with bounded cue density and voice ducking.
- A deterministic storyboard compiler that emits HTML, SVG frames, and JSON.
- A visible-quality linter covering first-frame motion, occupancy, caption rhythm,
  demonstration variety, mascot-action variety, camera variety, sound sync, and
  visual callback completion.
- Fail-closed contracts for missing callbacks, late motion, invalid canvas boxes,
  caption overflow, and timing errors.

## Representative result

The grocery-price story now produces a real preview bundle with:

1. a 2019-versus-2026 value collision in the opening frame;
2. a chart line that physically yanks the mascot upward;
3. the $350 increase converted into a stack the mascot must support;
4. a closing bridge that restores the opening values and labels the gap as the story.

The generated preview scores **95.9** on the review-only visible-quality linter.

## Verification

- 18/18 local tests passed.
- Production files modified: 0.
- Workflow files modified: 0.
- Production imports added: 0.
- Publishing calls added: 0.
