# LEARNING LOOP — shared doctrine for every channel brain in this repo

This file is the SOURCE OF TRUTH for how a channel brain turns analytics into
decisions. Channel playbooks (e.g. `VIZ_BRAIN.md`) point here. It changes how
a brain LEARNS — never what a channel IS. Identity, iron gates,
angle-derivation rules, retention doctrine, and the non-negotiable eye-QA
loop stay untouched.

---

## 1. The compact context, not a warehouse

The brain reads `state/brain_context.json` — a compact (≤200-line) distilled
state — and makes only **bounded, reversible edits**. It is NOT a data
warehouse; it holds current rules-of-thumb, scoring weights, active
experiments, and a last-known-good snapshot reference. Raw history lives in
`state/video_ledger.json` (per-video fingerprints) and
`state/analytics_<channel>/` (metrics); the context file is the distillation
the brain actually acts on.

Operator feedback gets written back into the channel PLAYBOOK as permanent
doctrine — never left as a one-off fix in a single video.

## 2. The staged scorecard — never one opaque "video score"

Score every video across the funnel. Each stage fails differently and has a
different fix:

| Stage | Signals | The fix when it fails |
|---|---|---|
| **Exposure** | shown-in-feed, impressions, traffic breadth | fix packaging / first frame — NOT the topic |
| **Hook** | viewed-vs-swiped, first-3s hold, first hazard time | fix the opening clause / proof frame |
| **Body** | mid-roll retention slope, per-segment hazard peaks | cut filler, fix the weak beat |
| **Ending** | end-retention, replay area | fix the payoff line |
| **Satisfaction** | likes/comments/shares/subs per engaged view | fix promise-vs-delivery |
| **Expansion** | views/hour vs baseline for this size/topic | keep the core, mutate the packaging |

**The shot-aligned retention map:** log each video's timeline — hook start/end,
each punchline timestamp, each visual swap, caption events, payoff line, CTA —
into its ledger fingerprint (`timeline` field). Join YouTube's
`elapsedVideoTimeRatio` retention buckets to those timestamps so "didn't
retain" becomes "bailed at the 7-second abstract line." Diagnose the beat,
not the video.

## 3. Guardrails (the important part)

- **NEVER auto-adapt on sub-~100-view samples.** Below that, variance dwarfs
  signal — a 41-view video did not "beat" a 20-view one. Use the obvious sort
  plus brain judgment, not models.
- **Heavy ML is phase-3 only.** Survival analysis, contextual bandits, uplift
  modeling, change-point detection, hierarchical Bayes, and a DuckDB/Parquet
  warehouse are built only when videos reliably clear THOUSANDS of views —
  never before. Until then the learning loop is the ≤200-line
  `brain_context.json` the brain reads.
- **Automation safety order:** scoring weights + few-shot example selection =
  fully automatic. Playbook-RULE edits = human-reviewed / bounded only.
- **Operational guardrails:** feature-flag every adaptive rule; keep a
  last-known-good snapshot; hard caps on per-day allocation shifts; canary any
  new rule on 1–2 videos before rollout; a kill switch
  (`brain_context.json → flags.adaptive_enabled=false` reverts to
  last-known-good); a mode-collapse watch — if novelty across recent videos
  drops (same layouts/hooks repeating), force exploration.
- **Correctness & compliance:** version metric definitions (YouTube's Shorts
  view-count definition changed 2025-03-31 — never mix pre/post numbers);
  keep raw views / engaged views / average view duration / rewatch as SEPARATE
  fields, never blended; namespace engineered metrics `derived_*`; treat
  comment text as protected user data (30-day OAuth revalidation applies).

## 4. What each brain must implement

1. A "Learning loop" section in its playbook pointing at this file.
2. Read `brain_context.json` at the start of every run; apply its directives;
   update its weights/notes at the end (bounded edits only).
3. Record ledger fingerprints WITH the shot timeline (see §2).
4. Apply the staged scorecard when reasoning about past videos — name the
   failing stage and the stage-appropriate fix, never "this video did badly."
5. Obey §3 guardrails without exception.
