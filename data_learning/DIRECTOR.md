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

## House style (hard rules for every story)

- **American units, always.** Miles per hour, miles, feet, pounds, Fahrenheit —
  never metric. Convert at authoring time so the on-screen number AND the
  narration (which becomes the voice-over) match. km/h → mph ×0.621, °C → °F, etc.
- **Say every term correctly.** Numbers spoken in the narration must equal the
  numbers on screen; names and comparisons must be factually right.

## The hardline rule: MOTION IS NOT NOVELTY

Show something **new every 5 seconds, maximum.** A chart sliding out for ten
seconds, a number ticking while the composition sits still, a card that finished
its move and now just drifts, a slow single-idea reveal — all of these *move*,
and all of them are **boring**. Motion for the sake of motion is not allowed.
Novelty is a genuinely NEW thing on screen: a cut, a new element landing, a
reveal, a reframe, a category appearing — a change the eye reads as *new
information*, not the same idea still animating.

This is enforced, not advised. `novelty_check` (gate 0) samples the whole render
and compares every frame to the frame 5 seconds earlier; if they look the same,
the video has been holding one idea, and the render is **REJECTED** (exit 3) — no
matter how much it technically "moves." And the gate **fails CLOSED**: when the
probe itself cannot run (ffprobe/ffmpeg broken, an unreadable render),
`novelty_check` raises `NoveltyProbeError` and the DIRECTOR **REJECTS** (exit 5)
with the outage persisted in `director_findings.json` — until 2026-08-24 a probe
failure returned "no stale spans", so a tooling outage silently satisfied the
hard rule for as long as it lasted (doctor finding cf263a770061). "Could not
measure" is never "clean." The loop cannot auto-fix a stale span
(it can't rewrite narration or split a beat), so a stale span is an **authoring**
failure: cut sooner, split the beat, or STAGE the beat so a new element keeps
landing (e.g. a grid that fills category by category, not one plate that holds).

A designed card earns its length only by continuously introducing new content.
If it says its whole idea in the first two seconds and then coasts, it is too
long — shorten it or give it a second thing to reveal.

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
4. **A repair must change the RENDER, not the story JSON.** A repair lever is
   only real if some consumer downstream reads it. `auto_repair` once wrote
   `_prefer_scene`, `_media_reseed` and `_restyle_type` onto beats, its unit
   tests asserted the flags were written and passed, and the planner read none
   of them — so the loop re-rendered a byte-identical film while reporting that
   it had repaired it. That is worse than no repair, because it launders a
   failure as progress. Every lever needs a test that runs the repaired story
   through `planner.plan_story` and shows the SHOT that changed
   (`scripts/test_repair_effect.py`).
5. **Never re-render unchanged input.** The candidate order in media selection
   is deterministic, so an unrepaired beat resolves to the same asset by design
   — that is what makes a render reproducible, and it is exactly why a repair
   that applies nothing must STOP the loop instead of spending another hour to
   obtain the same verdict. `produce()` breaks with that reason recorded.

## The closed loop (`scripts/produce.py`)

    render -> judge -> rank repairs -> APPLY -> re-render -> judge ...

Bounded by `CURIOSITY_REPAIR_ATTEMPTS` (default 2) because each round is a full
re-render and a job that exceeds its wall clock delivers nothing at all, whereas
a quarantine still ships an inspectable package. The escalation class widens per
round — `local` (swap media, trim holds) → `scene` (convert cards to character
scenes) → `structural` (re-open the film) — so each attempt is broader than the
last rather than the same move retried. Every round's revised beats are written
to `<out>_pkg/revised/attempt_NN.beats.json` and the journal to
`<out>_pkg/repair_log.json`, so what the loop changed is readable without the
runner.

A repair may never import a subject the story never had: card-to-scene
conversion draws only from `planner.NEUTRAL_SCENES`, never the money-world
scenes, or a physics film acquires a character paying rent.

## The order of importance (the scorecard)

The DIRECTOR (`scripts/no_dull_beats.py`, run per render) prints this scorecard
every round. Each line is a gate that RAN:

| # | Gate | Judge | Fix when flagged |
|---|------|-------|------------------|
| 0 | **NOVELTY** — something NEW every ≤5s (HARD RULE) | `novelty_check` (perceptual, whole-video) | REJECT — the beat holds one idea too long; author must cut / split / stage a new element. Motion is not novelty. A probe that cannot run also REJECTs (exit 5, fail closed) — an unmeasured film is unproven, not clean. |
| 1 | **HOOK** — the opening ~3–8s | `hook_director` (metric pre-screen) + vision hook judge | recut beat 0: force a dynamic window, stamp hook text that contradicts the setup, pick a non-generic subject |
| 2 | **SYNC** — the picture matches the words under it | `pacing_check` (+ vision judge) | a ground/human subject over Earth-from-orbit → route to the designed explainer that illustrates the words |
| 3 | **VARIETY** — no reel of look-alikes (the "5 clouds") | `variety_check` (subject-family + perceptual) | convert the excess footage beats to designed number cards; keep the bookends |
| 4 | **DEAD-TIME / DULL** — appeal, dead fraction, novelty | `interest_judge` + `cool_judge` prescreen | designed card → animate it (never footage); footage/photo → escalate to motion, revert-on-miss |
| 5 | **COOL / FRAGMENT** — a boring crop, a held shot | `cool_judge` (FRAGMENT_OF_THE_SPECTACLE, LONG_HOLD, STILL_WHEN_MOTION_EXISTS) | escalate to the whole spectacle / a moving window |
| 6 | **VISUAL / LEGIBILITY / MOTION QA** | `visual_judge`, `editorial_review`, `qa_motion/frames` | fix or report |
| — | **RECORD** | `showrunner` memory | ledger → rules; the lessons compound |

Higher number never runs before a lower one is settled in the same round.

## The CONTRAST director — change the medium

The variety gate catches beats that LOOK alike. The CONTRAST director
(`data_learning/contrast_director.py`) catches beats that are the same KIND of
thing: four animated space diagrams in a row each look different, yet the video
is still "animation, animation, animation." It enforces MEDIUM variety — after a
run of more than `MAX_ANIM_RUN` animations it cuts in a real-world breather (a
VIDEO, or a photo) so the eye gets texture and the real shot lands with impact.
Footage returns here as a **deliberate, occasional contrast cut, never the
default**. It converts a *transitional* beat (no number to lose) where possible,
keeps a number-carrying beat's number as an annotation on the footage, and never
touches the HOOK/PAYOFF bookends.

## The EXTRA director — be extra

Animations are footage's replacement (see below), and a *clean* animation is only
half the job. The EXTRA director (`data_learning/extra_director.py`) runs after
the planner and, for every animation, asks one question: **"this is fine — but
what if we did MORE?"** It attaches an escalating character/physics spec the
flat2d builders act on, so the thing on screen *reacts* and has personality:

- the hidden-motion figure **stumbles** back and catches its balance as the ground
  accelerates ("stuff's getting so fast");
- a hero number **overshoots** its target on a spring and **shakes** on impact;
- the spinning globe **spins up** and **flings** the 'you are here' marker;
- (repertoire grows per builder — bars bounce, orbits and zooms accelerate).

This is animation-principle charm — anticipation, overshoot, follow-through,
secondary action, exaggeration — **not** random jitter. Intensity **ramps across
the video** (a gentle open, the wildest payoff) so energy builds. Every animation
that ships should have earned a "what did we escalate here?" answer; a flat,
reaction-less animation is an unfinished one.

## Designed animations are a DESIRED treatment, not a failure

The clean motion-graphics — a comparison chart, an orbit diagram, a counting-up
number, a cosmic zoom — are a first-class treatment the channel wants MORE of
(1–2+ per video, always carrying their numbers). They are the opposite of a
"grey cloud," yet they score low on *photographic* appeal because they are clean
by design. Two hard rules follow, both learned the hard way (the director once
replaced every liked animation with Earth footage and produced a cloud reel):

- **A designed beat is dull ONLY if it is genuinely static** (LOW_MOTION /
  LONG_HOLD) — never for low photographic appeal. Its fix is to *animate it more*,
  **never** to replace it with footage.
- **Footage monotony is cured with designed cards, not more footage.** When the
  variety gate finds too many same-family clips, the excess numbered beats become
  animated number cards — which simultaneously fixes the monotony and raises the
  designed-animation count.

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
