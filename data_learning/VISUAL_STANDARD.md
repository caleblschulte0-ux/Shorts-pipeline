# THE VISUAL STANDARD — what a ledger-blind judge measures (v9)

This is the rubric for `scripts/visual_judge.py`. It is handed, verbatim, to
three independent vision-model judges who see **only rendered pixels** — never
the code, the ledger, the spec, the template name, or the intent. They judge
the clip the way a viewer scrolling a feed would: on what is on screen.

The standing danger this defeats: a system that games its own tests by piling
on shiny lighting, fast camera, motion blur, particles, and streaks, then
declaring the result "cinematic." Rendering complexity is NOT quality.
Direction is quality.

---

## The target
A polished visual documentary / explainer sequence — the class of work made by
professional motion designers and cosmic-scale documentary editors. NOT an
automatically-generated educational graphic. The blunt test a judge applies:

> "If I saw this clip with no context, would I believe a professional studio
> made it — or would I assume software auto-generated it?"

---

## CRITICAL FAILURES (any one → the clip FAILS, regardless of everything else)
A judge returns the label if the problem is present anywhere in the clip.
Critical failures OVERRIDE any positive score.

- **CHART_GRAMMAR** — it is (or is secretly) a chart: parallel lanes, axes,
  vertical/horizontal bars or slabs, a gauge/dial, values attached to isolated
  columns, or objects that move only to represent a number. Changing the
  material, lighting, depth, or background does NOT make a chart not-a-chart.
- **PASTED_MEDIA** — a photo/still that reads as dropped-in B-roll: a near-static
  image cut into moving content, a subject floating on its own background,
  anything that looks composited-over rather than part of the world.
- **UNMOTIVATED_CAMERA** — the camera moves without a reason the shot gives it;
  drift/spin/zoom that isn't following, revealing, or entering something.
- **SUBJECT_AMBIGUITY** — no single obvious thing to look at; the eye doesn't
  know where to go; competing elements of equal weight.
- **GENERIC_CG** — looks like a default 3D render / screensaver: technically
  rendered but says nothing, no authored composition, "shiny but empty."
- **EFFECT_OVERUSE** — motion blur / shake / streaks / particles / DOF used as a
  filter stack to fake production value on a weak underlying shot. Tells: blur
  obscuring the subject or hiding bad interpolation; continuous random shake;
  streaks that sit behind the subject as decoration unrelated to motion
  direction; focus hunting.
- **MOTION_SICKNESS** — camera motion that would be unpleasant to watch:
  jittery, too fast, unstable, disorienting without purpose.
- **WEAK_TRANSFORMATION** — nothing meaningfully changes; the end state looks
  like the start state; movement without development.
- **NO_MENTAL_MODEL_CHANGE** — the viewer's understanding doesn't shift; it
  shows a fact instead of making them realize something.
- **CHEAP_TYPOGRAPHY** — type that looks like a default template: bad weight,
  spacing, placement, or scale; text competing with the image; tiny labels.
- **EMPTY_COMPOSITION** — a small subject in a large empty (often black) frame;
  wasted space; the frame isn't filled or used.
- **BAD_INTERPOLATION** — visible frame-blending artifacts, warping edges,
  ghosting, smeared motion from the fps up-interpolation.

## REQUIRED POSITIVE TRAITS (a passing clip has ALL of these)
- **Obvious primary subject** — one clear thing the eye lands on immediately.
- **Clear starting state** — the shot establishes where we begin.
- **Meaningful transformation** — something real changes across the clip.
- **Clear ending state** — the shot lands somewhere, resolved.
- **Full-frame composition** — the image occupies and uses the whole frame.
- **Motivated camera** — every camera move follows/reveals/enters/rides something.
- **Coherent environment** — one believable world, not alternating looks.
- **Mobile readability** — reads at phone size; nothing critical too small.
- **≥1 memorable frame** — at least one image worth screenshotting.

## For an ENDING clip specifically
The last shot must be the STRONGEST image — frame-filling, largest scale,
resolves the opening, ends on a memorable composition, not a statistic fading
into black. Judged independently stronger than any earlier moment.

---

## What the judge is given (motion, not just stills)
- the full low-resolution clip (and/or an animated GIF strip),
- a contact sheet of sampled frames,
- the begin / middle / end frames,
- a camera-motion trace (per-frame mean pixel displacement — lets a judge see
  smoothness, speed spikes, and whether motion is continuous or stalls).
The judge is NEVER given code, ledger, spec, template name, or stated intent.

## Verdict shape (each judge returns this)
```
{
  "role": "viewer" | "editor" | "adversarial",
  "critical_failures": ["CHART_GRAMMAR", ...],     // empty if none
  "missing_positives": ["motivated camera", ...],  // required traits absent
  "score": 0-10,                                    // overall, for reference only
  "verdict": "PASS" | "FAIL",
  "one_line": "the single most important thing right or wrong"
}
```

## Panel decision
- The Adversarial judge is prompted to hunt for reasons to reject.
- A clip PASSES only when: **no critical failure from ANY judge**, no required
  positive missing by consensus, and ≥2 of 3 roles return PASS with the
  Adversarial judge not raising a critical failure.
- Any critical failure from any judge → the clip FAILS and is iterated or the
  approach is replaced. The average score never rescues a critical failure.
