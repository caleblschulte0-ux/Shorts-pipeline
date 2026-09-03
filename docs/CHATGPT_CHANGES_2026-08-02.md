# ChatGPT production-rescue changes — 2026-08-02

This file records the production code changed by ChatGPT with the owner's
explicit authorization on 2026-08-02. The changes are intentionally grouped
in one Git commit so Claude or a maintainer can undo them with:

```bash
git revert <the commit whose subject starts "chatgpt: repair takeover production ownership">
```

Do not delete or rewrite existing production history to undo this work.

## Why this was added

The first whole-pipeline ChatGPT takeover reached `DONE`, but all six Trending
videos failed or were quarantined and zero were uploaded. The failures exposed
four gaps:

1. Phase B committed image paths from its disposable runner; the separate
   render runner could not read them.
2. The Reddit renderer did not consume the story-shot images that ChatGPT had
   generated.
3. The graph-race renderer supplied no host mascot or sufficiently continuous
   performance, while the showrunner gate correctly required both.
4. A green handoff meant `DONE`, not verified renders and uploads.

## Files and behavior changed

- `scripts/exchange_phase_b.py`: preserves verified, durable Drive URLs and
  media identity instead of temporary runner paths; supports idempotent media
  repair on a rerun.
- `make_reddit_story.py`: renders verified per-shot illustrations in the top
  half, gameplay/captions in the bottom half, and host-mascot reactions.
- `engines/chart_race.py`: adds a data-reactive host mascot and continuous,
  honest visual performance.
- `funnel/gemini_images.py` and `scripts/run_trending_daily.py`: make visual QA
  aware of the actual Reddit layout and record a per-channel production
  outcome; expected quarantines/failures now fail the job.
- `config/channel_registry.json` and `shared/channel_registry.py`: add the
  whole-pipeline `production_supervisor` role to every enabled channel.
- `.github/workflows/daily.yml`: removes its second creative brain and reserve
  fallback. This workflow now accepts only a validated pre-render manifest and
  remains responsible for deterministic render/QA/upload.
- `CLAUDE.md`, `CLAUDE_ROUTINE_INSTRUCTIONS.md`, `exchange/README.md`, and
  `docs/FALLBACKS.md`: document immediate no-bundle takeover and the difference
  between handoff completion and production completion.
- Tests pin the durable-media, dynamic-registry, no-second-brain, and visual-QA
  contracts.

## Operational boundary

Normal day: Claude owns research, authoring, shot/media requests, sequencing,
and the renderer-ready plan. ChatGPT supplies requested media and finalizes the
validated plan.

Claude-out day: the missing or invalid plan is the takeover signal. ChatGPT
owns the whole active registry—research, authoring, media, manifest, render/QA
supervision, retry/repair, and verified uploads. The renderer never authors.

`response.json` and `DONE` are handoff artifacts. A day is not successful
until the production outcome records every expected upload or an explicit
terminal failure.
