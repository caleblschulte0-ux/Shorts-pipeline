# "Where Your Life Actually Goes" — hard stop after 3 CI renders

Slug `spend-your-life`. Three full renders through the canonical producer
(`post_curiosity → produce.produce → no_dull_beats.run → pro_render →
facts_gate → produce.evaluate`). All three quarantined. This records *why*,
with receipts, so the next attempt starts from evidence instead of guesses.

## Attempt log

| # | run | outcome | what it taught |
|---|-----|---------|----------------|
| 1 | 30498… | crash | `TypeError: sleep_scene() got an unexpected keyword argument 'extra'` — **11 of 16 scene builders rejected the expression payload the renderer passes to all of them.** The entire time/life scene set was unrenderable and had been since the payload landed. Fixed + regression test `scripts/test_scene_dispatch.py`. |
| 2 | 30504256714 | `director_rc=1` | Complete 3:38 film, 6 chapters, 11 sources, 2 fallbacks. Beat 24 degraded to a statement card → the single dull beat. Replaced with `scene_savings` (zero media dependency). |
| 3 | 30509688188 | `director_rc=1` + taste **REJECT 3.0/10** | The real ceiling, below. |

## Attempt 3 measurements (head `ec0a4d8`, 1h24m render)

- `director_rc = 1` — ROUND-LIMIT: 3 repair rounds, beats still dull.
- `fallbacks.json`: `{"verdict": "ok", "fallbacks": []}` — no degradations.
- Facts gate: PASS, 8/8 claims covered.
- Card budget (deterministic): **18.4%, under budget.**
- Blind taste judge (fresh agent, evidence only): **REJECT**,
  `personality 3`, `overall_10 3.0`,
  labels `CARDS_OVER_BUDGET`, `EMPTY_COMPOSITION`,
  card fraction *as seen* **46%**.

## Root cause: the media funnel, not the authoring

Provider mix across three consecutive runs: **zero Pexels, zero Pixabay.**
Attempt 3 served `commons 6 · openverse 3 · archive 1 · ia 1`. What the
Creative-Commons pools actually returned for a gentle film about sleep,
work, screens and time (`credits.json`, verbatim titles):

```
commons    大批民众自发前往香港火灾现场周边献花悼念.webm   (fire-memorial vigil, broadcaster
                                                        watermark + burned-in subtitles)
commons    Bodycam Video From Attack on LAPD Officer at Harbor Station.webm
commons    Police Bodycam Shows Man Lose Consciousness During Arrest.webm
commons    Czechoslovak arms factories 1938 newsreel.webm
commons    Deska- Fifteen Inches of Pure White Snow.webm
openverse  Bozo Nightmare                                (a clown doll on a bed)
archive    Acoustics and Your Environment: … Highway Traffic Noise
ia         "Your Name Here" Story, The (Outtakes)
```

The blind judge — with no access to this file — independently named the
"POLICE ACTIVITY" logo, the `AXON BODY 3 X6039BCN0` timecode, the Chinese
broadcaster watermark, the clown doll, and the tonal whiplash. Its diagnosis
and the credits agree exactly.

**No grade, no regrade, no re-author fixes this.** Third-party chyrons,
bodycam timecode and burned-in subtitles are an amateur tell that survives
any colour pass, and a mourning vigil plus two police bodycams of violence
do not belong in this film at any grade.

## Two real code gaps this render exposed

1. **No media-appropriateness / branding gate.** Nothing rejected a police
   bodycam of a man losing consciousness, or a clip with a broadcaster
   watermark and hard-burned subtitles, from a film about how many years you
   sleep. Licence was clean; suitability was never asked. This belongs in
   the shared media layer (`data_learning/media.py` funnel), not in a
   channel.
2. **The card budget under-counts by ~2.5×.** Deterministic 18.4% vs 46%
   seen. `composition_budget` counts only `flat_*` `CARD_KINDS`; the
   yellow-number stat-plate *look* is also produced by `scene_*` builders,
   which the gate does not count. This is audit finding #9 (visual-family
   repetition, scored on the render) still open: a renamed money bar is
   still a money bar.

## What the owner has to decide

The pipeline is working — it rendered a complete film three times, caught
its own dull beat, refused to publish an unjudged cut, and its blind judge
produced a diagnosis that matches the credits line for line. What it cannot
do is source clean, tonally appropriate moving footage from the CC pools
alone. Unblock one of:

- **Make `PEXELS_API_KEY` / `PIXABAY_API_KEY` actually resolve on the
  runner** (they are absent from every credits mix so far). This is the
  single highest-leverage fix.
- **Answer the open exchange asks** so generated imagery can fill the gaps:
  `image-20260729-taxes-01`, `image-auto-b50b663f30`. Blocked on the proven
  Drive limitation — the connector cannot set anyone-with-link sharing.
- **Accept a no-footage cut** authored entirely from scene/character
  vignettes, and let the two gate fixes above land first.

## Addendum — the director's gates re-run offline on the finished cut

The CI gate report only goes to stdout, so the gates were re-run locally
against the downloaded master to name the beats. Results:

- `dead_fraction` **0.39** — 86 of 218s read as dead. `mean_appeal` 0.628.
  Twelve boring stretches. One stale span, `88.5–96.0s`.
- Hard-dull beats, all `DEVELOP`, all with `fix=motion`:
  **beat 8** (appeal 0.477), **beat 12** (dead stretch, 0.564),
  **beat 16** (0.402). The floor is 0.55.
- The cool judge flags 9 suspects. **Five of them are the CHAPTER cards** —
  beats 2, 6, 10, 14, 19, appeal **0.32 · 0.33 · 0.37 · 0.40 · 0.38**.
  Every single chapter title card scores below the dull floor.

Two things follow.

**The three hard-dull beats all ask for `motion`** — moving footage — which
is exactly what the funnel cannot supply cleanly. That closes the loop: the
director's own prescribed repair is blocked by the same missing providers.

**The five chapter cards are dull by construction, and that needs no
footage at all.** A held title plate cannot clear a 0.55 appeal floor.
This is the one part of the failure that is fully fixable in-engine, and it
makes the no-footage option viable: redesign the chapter transition so it
carries motion or a character beat instead of a frozen plate, and five dead
beats become live ones without a single new asset.
