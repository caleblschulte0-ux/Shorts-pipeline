# THE DIRECTOR — one ordered pipeline, every gate called, every flag fixed

This is the contract that stops good judges from being built and never called.
The channel has many directors and judges (hook, interest, cool, visual,
perspective, QA). Each is worthless unless it (a) actually RUNS on every render,
(b) runs in a fixed **order of importance**, and (c) drives a **fix** when it
raises a hand — not just a printed complaint.

The failure this document exists to prevent really happened: `hook_director.py`
was written, tested, and correct — and imported **nowhere**. A 10-second calm
Earth open reached preview because nothing graded the opening. "We have a hook
judge" is a lie if the render loop never calls it.

## The law

1. **Every gate runs on every render.** If a gate is not in the DIRECTOR's
   scorecard (below), it did not run. There is no "we have a judge for that"
   without a call site the scorecard prints.
2. **A flag drives a fix, or an honest FAIL — never a silent pass.** If a beat is
   flagged boring / held / fragment / dull / weak-hook, the DIRECTOR must either
   repair it (escalate to motion, recut, re-author) and re-verify, or stop and
   report exactly what it could not fix and why (e.g. stock-access-gated). A
   render that shipped with a known flag unaddressed is a bug in the DIRECTOR.
3. **Order of importance is fixed.** Retention is front-loaded: the opening
   decides whether the rest is ever seen. Gates run top-down; a lower gate never
   masks a failure in a higher one.

## The order of importance (the scorecard)

The DIRECTOR (`scripts/no_dull_beats.py`, run per render) prints this scorecard
every round. Each line is a gate that RAN:

| # | Gate | Judge | Fix when flagged |
|---|------|-------|------------------|
| 1 | **HOOK** — the opening ~3–8s | `hook_director` (metric pre-screen) + vision hook judge | recut beat 0: force a dynamic window, stamp hook text that contradicts the setup, pick a non-generic subject |
| 2 | **DEAD-TIME / DULL** — appeal, dead fraction, novelty | `interest_judge` + `cool_judge` prescreen | escalate the dull beat to motion of its subject (motion-first, dynamic window); revert-on-miss |
| 3 | **COOL / FRAGMENT** — a boring crop of something spectacular, a held shot | `cool_judge` (FRAGMENT_OF_THE_SPECTACLE, LONG_HOLD, STILL_WHEN_MOTION_EXISTS) | escalate to the whole spectacle / a moving window |
| 4 | **VISUAL / LEGIBILITY / MOTION QA** | `visual_judge`, `editorial_review`, `qa_motion/frames/semantics` | fix or report |
| — | **RECORD** | `showrunner` memory | ledger → rules; the lessons compound |

Higher number never runs before a lower one is settled in the same round.

## Metric pre-screen vs. vision taste-judge

Two kinds of judge, and the DIRECTOR must use both correctly:

- **Metric pre-screens** (cheap, deterministic: motion, appeal, dead-fraction,
  sustained-motion) run *inside* the DIRECTOR loop. They catch the objective
  failures — frozen, sub-floor motion, a held shot.
- **Vision taste-judges** decide the things a number cannot: "is this the
  *coolest* way to show it," "is this hook generic-but-pretty," "does this crop
  bury the spectacle." A metric will pass a gorgeous Earth-from-orbit frame that
  a human instantly files as "generic space video I've scrolled past a thousand
  times." That verdict is a vision model's call. A pure-Python loop cannot spawn
  one — **the orchestrator spawns the vision judges** (same pattern as
  `cool_judge` / `visual_judge`: the script builds a blind media package, the
  orchestrator's vision subagent renders the verdict).

So the DIRECTOR loop runs the metric pre-screens as the fast first pass; the
orchestrator (`post_curiosity` / the workflow / a human review step) runs the
vision judges before publish. Neither is optional. A hook that passes the metric
pre-screen but a vision judge calls generic is **not** cleared.

## Wiring checklist (do this for every new judge)

A judge is not "done" until:

- [ ] it has a call site inside the DIRECTOR loop **or** the orchestrator's
      vision-judge stage;
- [ ] its verdict appears in the DIRECTOR scorecard;
- [ ] a failing verdict triggers a concrete fix path (or an explicit, reported
      FAIL) — grep the loop for where the flag is consumed;
- [ ] `grep -rl <judge_name> scripts/ data_learning/` shows an importer that is
      not a doc or the module itself.

If you cannot check every box, the judge is decorative. Wire it or delete it.
