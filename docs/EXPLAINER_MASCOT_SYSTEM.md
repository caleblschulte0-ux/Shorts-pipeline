# Explainer Mascot Action System (separate subsystem — NOT the curiosity character system)

**Status:** frozen during the curiosity recovery (Phase 0). No new mascot features
until the curiosity canonical path is proven.

## What it is

The vertical explainer/data-channel renderer on `main` carries its own mascot
performance system:

- `data_learning/studio_render.py` — explainer renderer
- `data_learning/mascot.py` — mascot rig
- `data_learning/charts.py` + mascot direction — chart-aware staging

Capabilities (kept, they are real progress): prop-aware and chart-aware actions —
carrying, pushing, holding, sitting, leaning, presenting, cheering, pointing,
climbing, lifting, riding chart lines, interacting with bars and data points —
staged near the spoken value, timed to the narration, with a setup → action →
payoff arc and whole-body motion.

## What curiosity shares with it (concepts, not code)

The curiosity long-form character system is `data_learning/expression.py` +
`data_learning/scenes.py` (recovered on `feature/curiosity-pro-integration`).
It implements the same **principles** with its own architecture:

| Principle | Explainer mascot | Curiosity character |
|---|---|---|
| Structured emotion (not a Boolean) | action verbs + chart anchors | `{"expression": {"emotion", "intensity", "start", "end"}}` configs |
| Whole-body motion | crouch/stand/sway/legs/arms/hops | pose + stride + lean + head angle + body sway + gesture deltas |
| Setup → action → payoff | wind-up / action zone / payoff pose | per-scene arc phases in `scenes.py` |
| Safe clamping / determinism | pose bounds | clamped pose-deltas, deterministic interpolation |

The two systems are **not coupled**: curiosity does not import explainer chart
code, and improving the mascot does not change the curiosity production path.
Any future unification is a deliberate refactor into a shared utility module —
not a claim that one already is the other.
