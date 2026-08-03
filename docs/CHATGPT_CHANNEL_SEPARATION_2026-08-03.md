# ChatGPT channel-separation correction — 2026-08-03

This change was authored by ChatGPT at the operator's explicit request.

## Problem

ChatGPT's 2026-08-02 production-repair commit incorrectly imported the
Explainer/Data mascot into the separate Trending channel's graph-race and
Reddit-story renderers. It also changed the Trending authoring contract and
showrunner rubric to expect that cross-channel mascot.

## Correction

- Data remains owned by the Explainer renderer.
- Trending graph races render charts without Data.
- Trending Reddit stories render their verified shot imagery without Data.
- Trending Reddit shot contracts no longer request `mascot_pose`.
- The Trending showrunner treats any visible Data mascot as a channel-brand
  violation instead of excusing it with code-declared choreography.
- The prior code path that overwrote the vision judge's mascot result was
  removed.

No mascot assets were deleted, and no existing package, checkpoint, posted
log, or successful upload was erased.

## Validation

- `python -m unittest tests.test_channel_mascot_separation`
- `python -m unittest tests.test_showrunner_gate`
- Relevant registry, authoring, renderer, and takeover regression suites.

## Rollback

Revert the single commit titled:

`chatgpt: isolate Data mascot to Explainer`

Reverting would restore the incorrect cross-channel behavior, so rollback is
provided for auditability—not recommended as production policy.
