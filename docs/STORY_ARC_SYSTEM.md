# The Story Arc System (third channel)

Auto-detected multi-clip narrative compilations — the "whole story,
beginning to end" format (e.g. a beef that starts, escalates, and ends in
a makeup hug), stitched from clips across streamers and days. Shipped
2026-07-23; first proven live in the `20260723b` dry-run canary (built the
Kai Cenat SU dean arc and the stableronaldo→Cudi makeup arc unaided).

## Architecture (three layers + wiring)

```
posted log + wide 7d/30d discovery sweep          (corpus)
        │
        ▼
third_capture/storyline.py     find_clusters(): group clips by shared
        │                      PEOPLE; alias-normalized, jaccard-deduped;
        │                      a cluster must span >=2 moments on >=2 dates
        ▼
author.order_story()           the showrunner brain (claude→groq): STRICT
        │                      is-this-a-story gate; orders 2-5 beats
        │                      (setup/escalation/climax/resolution), writes
        │                      chapter cards + hook + <=95-char title
        ▼
third_capture/story.py         build_story(): each beat rendered through
        │                      the normal single-clip path (clip_edit.edit);
        │                      hook OVERLAYS beat 1 (playbook §5 — never
        │                      open on a card); chapter cards only BETWEEN
        │                      beats; normalize -> concat -c copy
        ▼
scripts/run_third.py           _story_attempt(): orchestrates + QA
                               (story-length durations allowed, any hard
                               problem rejects) + falls back to a normal
                               clip on ANY miss. Slots: `story_count` of
                               the daily `count`, date-seeded.
```

## The laws

- **Event-driven, quality-gated**: a story ships only when a genuine arc
  exists. No arc → the slot silently becomes a normal clip. A forced story
  is worse than a good clip.
- **story_key dedupe**: a compilation's identity = hash of its member set
  (`storyline.story_key`). The posted-log entry carries `story_key` +
  `member_keys` and **no `source_url`** — so the same arc can never ship
  twice, while member clips stay legal for single-slot posts (and
  already-posted clips are legal story material; the compilation is the
  new artifact).
- **Measurement isolation**: analytics tracks a `story` arm
  (`fetch_analytics`), and `_learned_prior` EXCLUDES story-format
  retention so single-clip streamer priors stay clean. Judge the arm only
  at >=25 mature videos (playbook §11).
- **Attribution**: the description credits every member source.

## Knobs (capture spec, `state/third_packages/default_clip.json`)

| key | default | meaning |
|---|---|---|
| `story_count` (top level) | 2 | story slots per day (of `count`) |
| `story_lookback_days` | 30 | posted-log corpus window |
| `story_top` | 6 | clips per channel per window in the wide sweep |
| `story_max_clusters` | 4 | clusters offered to the showrunner per slot |

Constants in `story.py`: `MIN_BEATS=2`, `MAX_BEATS=5`, `CARD_DUR=1.5`.

## Ops notes

- The wide sweep is cached run-wide (`_STORY_POOL`); transcripts are
  content-addressed in `cache/transcripts/` (persisted by actions/cache) —
  a re-picked clip never pays Whisper twice.
- A story build is expensive (~10-20 min: N downloads + N full renders).
  The slot-retry loop re-attempts on failure, so keep `_story_attempt`
  failure-paths returning None (fallback) rather than raising.
- Known scoping trap (live incident 2026-07-23): `process()` imports
  `author` at the top of its try-block ON PURPOSE — later in-branch
  imports make `author` local to the whole function, and any path that
  skips them dies at the final safe_title choke with UnboundLocalError.
- Smoke coverage: `scripts/smoke_third.py` renders a 2-beat story on
  synthetic fixtures every CI run.
