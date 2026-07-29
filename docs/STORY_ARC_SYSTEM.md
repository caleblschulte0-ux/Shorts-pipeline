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

- **J/L cuts** (§13/§14): a beat may carry `transition: "j_cut"|"l_cut"`.
  Each segment's own audio stays locked to its own picture; the lead/lag
  is a SEPARATE bridge of real source dialogue placed in the overlap (see
  the third-review fix below). Hard-cut-only stories keep the lossless
  concat path.
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

## Review hardening (2nd external review) — implemented

Fixes to places where the implementation claimed more than it did:

1. **Genuine multimodal vision**: `author._call_claude(read_files=True)`
   grants `--allowedTools Read` so the scene analyst can actually open the
   contact sheet. Vision provenance is tracked — `visual_beats` are kept
   ONLY when a vision-capable model (Claude with Read) inspected the
   frames; the text-only Groq fallback's visual claims are discarded, so
   "visual events are never invented" is now enforced, not hoped.
2. **Semantic event identity**: event ids fingerprint people + salient
   action tokens (from scene summaries) + ISO week, not people+month — so
   an argument on the 3rd and a gift on the 15th between the same pair get
   distinct records.
3. **Complete evidence**: transcript caps raised (16k report / 8k director)
   so a VOD-expanded 2-3 min window's later reaction reaches the director;
   the identified dialogue/visual beats always survive intact regardless.
4. **Real J/L cuts + A/V lock**: J-cut = next audio LEADS its video,
   L-cut = previous audio TAILS past its video, via absolute adelay
   offsets + amix; the mix is trimmed/padded to the exact video length so
   audio never drifts (the old code did an identical acrossfade for both
   and lost 0.3s per join). Smoke asserts A/V duration alignment.
5. **Subject-aware tight framing**: `tight` crops around the shot_plan
   face-tracked subject centroid, not a blind centre.
6/7. **Replay from raw + timeline repair**: the replay renders from the
   RAW source at its source timestamp (no vertical-in-vertical, no
   duplicated captions, no replayed hook), and its rendered duration
   advances the caption timeline so the critic's timestamps don't drift.
8. **Narrative EDL validation**: last beat must be a payoff/climax/
   reaction (no trailing off on context), central_question + 3-7-word hook
   required, first beat must fit the structure, cuts must land on real
   dialogue/visual windows, target_duration clamped 25-90, reaction hold
   floored to 0.8s.
9. **Story QA fails CLOSED**: an unreachable critic abandons the story to
   the clip fallback (incoherence is the story format's core risk).
10. **Narration key `over_beat`** matches the ducked-over-that-beat
   behavior (`after_beat` still read for compat).

## Review hardening (3rd external review) — implemented

The third review confirmed the architecture and caught three fixes that
had claimed more than they delivered:

A. **Real J/L cuts (no desync, no silence)**: the prior version shifted a
   whole segment's audio 0.4s early — a j_cut therefore desynced the
   visible speaker for the *entire* shot — and an l_cut just `apad`ded
   silence (recovering no real dialogue). Now every segment's audio stays
   lip-synced to its own picture (`adelay=video_off[i]`), and the lead/lag
   is a **separate bridge of genuine source audio** placed in the overlap:
   a j_cut extracts ~0.4s of the *incoming* source's dialogue from before
   its visible start (`_extract_audio(src, [start-lead, start])`); an l_cut
   extracts ~0.4s of the *previous* source's real dialogue after its
   visible end (`[end_prev, end_prev+lead]`). A cut is only honored when
   that pre-/post-roll actually exists in the source — otherwise it
   silently degrades to a hard cut. `alimiter` caps the brief overlap sum;
   the mix is still trimmed/padded to the exact video length. Acceptance
   asserts the real extraction windows and the honesty degradation; smoke
   renders both a j_cut and an l_cut and asserts a real bridge file plus
   A/V alignment.
B. **The rough-cut critic can see**: `review_rough_cut()` handed the critic
   a contact-sheet path but `_brain()` called Claude without the Read
   grant, so the critic was blind to the assembled frames. `_brain()` now
   accepts `read_files` and `review_rough_cut()` passes it whenever the
   rough-cut sheet exists — the narrative critic actually inspects the
   picture it is judging (Groq fallback stays text-only).
C. **Semantic subclustering, not just naming**: `find_clusters()` groups by
   shared people, so distinct incidents between the same streamers landed
   in one pile; the fingerprint only *named* that pile. Now, after scene
   analysis, `_semantic_subclusters()` single-links sources that share ≥2
   salient action tokens within the same ISO week (±1 week for a
   boundary-crossing incident) and the director is called **once per
   semantic event**, not once per mixed pile. Deliberately split-happy:
   sources with no shared action vocabulary form separate groups (dropped
   if <2 sources), because compiling unrelated same-people clips into a
   fake story is the worse error (§21).

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
