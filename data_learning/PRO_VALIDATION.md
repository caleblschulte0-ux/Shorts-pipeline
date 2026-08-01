# Pro-pipeline validation — the enforced studio, proven on real renders

This records the end-to-end validation of the canonical producer
(`scripts/produce.py`: `pro_render` + the full `no_dull_beats` director loop +
honest fallback ledger + blind vision taste verdict + publishing package). It is
the audit's bar #13: prove the **same** path renders → judges → repairs →
packages → (dry-run) publishes different story types with zero owner
involvement. Run 2026-07-22/23 in the CI-equivalent container (ffmpeg + edge-tts,
no Blender needed by these stories).

## The path, once

```
data_learning/pro_stories/<slug>.beats.json
  -> no_dull_beats.run   (pro_render draft + deterministic director gates
                          novelty/hook/pacing/variety/dull/cool/cards
                          + auto-repair + re-render; emits the publishing
                          sidecars + the honest fallback ledger)
  -> blind VISION taste subagent on <out>_pkg/  (no code, no intent)
       -> scripts/judge_verdict.py validates + writes <out>_pkg/verdict.json
  -> produce.evaluate  (director rc + fallback verdict + package present
                        + provenance + taste verdict; STALE/absent verdict
                        FAILS CLOSED)
  -> PASS (publishable) or QUARANTINE (reasons + produce_report.json)
```

## Results — the gate discriminates

| Story | Archetype | Director | Blind taste | Provenance | Outcome |
|---|---|---|---|---|---|
| **money-goes** | money / social | CLEAN (0 stale/0 dull, cards 17%, hook 8/10) | **PASS** (personality 3/5, no labels, cards ~30%) | 7 `facts[]` sources | ✅ **PASS** — publishable (8 chapters, 12 sources, valid description) |
| sitting-still-speed | science / scale | (clean metrics) | **REJECT** (personality 1/5: INFOGRAPHIC_REEL, NO_CHARACTER, SAMENESS, CHEAP_TYPOGRAPHY, CARDS_OVER_BUDGET; ~85% cards) | n/a | ⛔ **QUARANTINE** — soulless card reel |
| hurricane-engine | mechanism | **REJECT** rc=3 (4 stale spans; 38s) | (not reached) | n/a | ⛔ **QUARANTINE** — too static / too short |
| money-goes-weak | negative control | **REJECT** rc=4 (cards=100% > 42%) | (not reached) | `require_provenance`, no facts → blocked | ⛔ **QUARANTINE** — 3 independent gates |

The enforced pipeline **promoted the one genuinely good film and refused the
three weak/soulless ones**, autonomously, with honest machine-readable reasons.
This is the discrimination the old path lacked: legacy `longform_render` would
have published all four.

## The auto-repair loop, observed for real

money-goes round 1 QUARANTINED on a real stale span (152.5–158.0s): `scene_grocery`
followed by a second produce-shelf still held the "food shelf" idea too long. The
blind taste judge **independently** flagged the same duplicate — two different
gates, same defect. The fix (differentiate beat 17 → a person-eating POV with
motion) was applied; round 2 the director auto-escalated beat 17 to motion and
returned **CLEAN**; the re-judge returned **PASS**. Honest note: beat 17's new
food photo missed the keyless media gateway and degraded to a statement card
(recorded in `fallbacks.json` as `degraded` — reviewable, not blocking).

## Hardening surfaced by running it

- **Stale-verdict guard** (`produce.evaluate`): a re-render rebuilds the blind
  package but does not delete an old `verdict.json`; a verdict older than the mp4
  is now treated as STALE and fails closed, so a new cut can never be promoted on
  the previous cut's judgment.
- **Fail-closed on a render crash** (`produce.produce`): a dying render subprocess
  (malformed beat, builder `KeyError`, TTS death) now QUARANTINES with the failure
  recorded instead of crashing the producer.
- **`--force` is dedup/scheduling only**: the `post_curiosity` quality-gate block
  is unconditional — no `--force` escape — so a quarantined film cannot be forced
  out.

## Honest state of the content library (not a pipeline failure)

Two of the three shipped stories fail taste **as authored**. `sitting-still-speed`
and the weak control are card reels; the system now surfaces that instead of
publishing it. Making the science/scale and mechanism archetypes publishable is a
re-authoring job toward the palette (character vignettes / living scenes / real
footage), tracked as follow-up — NOT a change to the enforcement.

## Follow-ups
- Re-author `sitting-still-speed` and `hurricane-engine` toward the palette so all
  three archetypes reach a PASS (hurricane also needs length to clear the 120s
  watch-page floor).
- money-goes beat 17: a broader food-scene query (or a real diner clip) to replace
  the degraded statement card.
- P1/P2 creative items remain (semantic phases, honest media taxonomy, visual-
  family repetition scoring, comparative media selection, transitions, retention
  learning) — see the plan.
