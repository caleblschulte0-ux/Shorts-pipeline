# Sprint 5 — Visible Video Quality

This package improves what the viewer actually sees. It is isolated under
`review_prototypes/visible_quality/` and is not imported by the live pipeline.

## What it changes in a scene plan

- Replaces generic spoken hooks with a visual event that begins at frame one.
- Selects a demonstration from the actual data shape and narrative role.
- Avoids repeating one chart/mechanic for three consecutive beats.
- Gives Data a three-act setup → effort → payoff performance.
- Keeps the mascot physically caused by the data object rather than decorating it.
- Cuts narration into short, timed caption phrases with numeric emphasis.
- Emits synchronized camera, chart, mascot, label, and payoff motion cues.
- Reuses the opening visual object in the ending so the Short resolves visually.
- Emits existing-engine-facing fields: `kind`, `perf_override`,
  `highlight_label`, `host_baked`, and a structured `scene_plan`.

## Representative result

The included grocery-price fixture upgrades a repetitive chart-led plan into:

1. two years slam onto opposite sides of the frame;
2. the value gap physically opens;
3. Data grips the line and is dragged through the climb;
4. the accumulated difference becomes a physical burden stack;
5. the opening split-screen returns with the full path drawn between both dates.

The test suite requires the upgraded plan to beat the representative baseline by
at least 25 points on visible hook, demonstration variety, mascot causality,
caption rhythm, composition, and payoff.
