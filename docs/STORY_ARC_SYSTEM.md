# The Story Arc System (third channel) — v2: Story Director

Auto-detected multi-clip narrative stories. **Governing specification:
docs/STORY_DIRECTOR_PLAYBOOK.md** — this file is the implementation map.

v1 (2026-07-23) was a compilation generator: each beat rendered as its own
mini-production with chapter cards between. v2 inverts it: **the story
director owns one timeline; clips are raw material inside it.** Cards are
deleted from the architecture (spec §2/§11); context lives as brief
overlays ON moving footage.

## Pipeline (scripts/run_third.py `_story_attempt`)

```
corpus (posted log + wide 7d/30d sweep)
  -> storyline.find_clusters      people-clustering, ALIASES, jaccard dedupe
  -> event records                state/third_events.json survives runs
  -> scene_analysis.analyze_source   FULL transcript + frames -> people,
       |                             dialogue/visual beats, missing context
       +-> clip_edit.maybe_vod_window  §6 expansion when a source opens
                                       mid-sentence / lacks its payoff
  -> story_director.plan_story    eligibility (meaningful CHANGE or reject)
       |                          + explicit structure (6 approved) + full
       |                          EDL: exact in/out, per-segment purpose,
       |                          context overlays, global effect budget
  -> story.render_story           dedicated renderer: extract exact cuts,
       |                          uniform 9:16 reframe, captions, hook over
       |                          the OPENING FOOTAGE, overlays over motion,
       |                          loudnorm mix, hard-cut assemble. NO CARDS.
  -> story_director.review_rough_cut   12-question narrative critic
  -> story_director.revise_edl    exactly ONE revision, then re-review
  -> mechanical QA + duration band (25-90s) + story_key/near_dup dedupe
  -> publish, else clip fallback  (§21: never force a story)
```

## Laws (acceptance-tested: scripts/test_story_acceptance.py + smoke)

- **No cards, ever**: no `_card`, no `CARD_DUR`, no card mp4s, no blank
  canvas, no fade-from-black. First frame = moving source footage.
- **Director controls the timeline**: renderer executes the EDL only;
  beats cannot add their own replays/slow-mo; effect budget global
  (<=1 replay, <=2 subtle_punch), validated in `validate_edl`.
- **Every segment has a stated purpose** or the EDL is rejected.
- **Context recovery, never invention**: incomplete sources trigger VOD
  expansion via helix video_id+vod_offset; unrecoverable context means
  the director simply lacks it and the eligibility gate rejects.
- **Arc integrity**: failed opening or payoff beat aborts to clip
  fallback; only middle beats may drop.
- **Overlay hygiene**: 2-6 words, upper-third, ~1.3s, banned meta-labels
  ("PART TWO", "THE CLIMAX"...) stripped at validation.
- **One revision maximum**, then abandon (§19/§21).
- **Dedupe**: story_key (member-set hash) + near_dup (>=60% jaccard vs
  ANY shipped story) at cluster, plan, and rendered-member level.
- **Measurement isolation**: `story` arm in analytics; streamer prior
  excludes story retention; ledger carries story_structure, n_beats,
  duration, used_vod_expansion, context_overlay_count, replay_count,
  revision_count, narrative_score (§22).

## Phase Two (editing quality) — implemented

- **J/L cuts** (§13/§14): a beat may carry `transition: "j_cut"|"l_cut"`;
  the assemble blends audio 0.3s across that join (video stays a hard
  cut) — abrupt audio starts/stops disappear. Hard-cut-only stories keep
  the lossless concat path.
- **Framing continuity** (§15): per-beat `framing: "wide"|"tight"` —
  the DIRECTOR chooses (wide for the incident, tight punch-in for the
  response); renderer applies a modest centered crop.
- **Replay** (§12/§16): `{"type":"replay","at":s}` renders ONE slowed
  labeled re-show appended after its beat; budget enforced at validation.
- **Dialogue chain** (§14): highpass 60Hz + loudnorm + limiter per
  segment to one mix target.
- **Narration** (§14): optional top-level
  `{"text", "after_beat", "essential_because"}` — requires a stated
  justification, <=15 words, motive/drama words rejected at validation
  ("furious", "planning", "secretly"...). Synthesized via edge-tts,
  ducked under with sidechain; best-effort (TTS failure ships clean).

## Phase Three (learning) — plumbing live, evidence-gated

- Analytics entries carry the §22 fields; `summary["story_structures"]`
  aggregates per-structure mature performance.
- `_story_guidance()` feeds the director real channel evidence ONLY when
  >=25 mature story posts exist (`enough_data`) — before that the
  director plans blind, per §23: never optimize creative decisions
  before coherence is proven.

## Knobs (capture spec, `state/third_packages/default_clip.json`)

| key | default | meaning |
|---|---|---|
| `story_count` | 1 | story slots/day (raise only after ~20-25 mature story posts) |
| `story_lookback_days` | 30 | posted-log corpus window |
| `story_top` | 6 | clips per channel per window in the wide sweep |
| `story_max_clusters` | 3 | clusters offered to the director per slot |
| `story_dur_min/max` | 25 / 90 | story length band (s) |

Quality floors for normal clips: `min_banger` 0.5 (title-stage, unknown
=0.5 passes), `min_banger_content` 0.7 (transcript-aware, fails open).

## Ops notes

- Whisper transcripts are content-addressed in `cache/transcripts/`
  (persisted by actions/cache) — scene analysis pre-warms nothing twice.
- A story slot is expensive (downloads + scene analysis + 1-2 renders +
  2-3 brain calls). One slot/day; `_STORY_POOL` caches the wide sweep.
- Event records commit with the posted log via ci_commit_state.
- SCOPING LAWS (two live incidents): never re-import a module-level name
  inside `process()`; never use `+=` on a closed-over list in a nested
  function (use `.extend`).
