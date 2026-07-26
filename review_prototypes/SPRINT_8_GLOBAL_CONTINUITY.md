# Sprint 8 — Global Motion, Audio, and Continuity

This sprint improves the viewer-facing flow of a complete Short rather than polishing scenes independently. It remains isolated under `review_prototypes/visible_quality/continuity_lab/` and is not imported by production.

## Implemented

- global motion paths that carry the focal object through consecutive scenes;
- transition sequence optimization across the whole video instead of greedy per-cut selection;
- frame-snapped sound cues, number-hit synchronization, voice ducking, payoff silence, and loudness constraints;
- useful-occupancy layouts that avoid the Shorts action rail and lower metadata area;
- story-wide rhythm curves with immediate hook motion, consequence peak, payoff release, and callback landing;
- deterministic 1080×1920 SVG evidence frames with motion paths and audio markers;
- full proof across money, share, ranking, comparison, and single-stat archetypes;
- an updated scorecard that keeps production wiring and real-world proof at zero.

## Scope boundary

No production renderer, workflow, uploader, or existing pipeline file is imported or modified.
