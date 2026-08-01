# NO DULL BEATS

> Owner, verbatim: *"If you know what beat is the next dull beat, you should be
> fixing that stuff. There shouldn't be any dull beats. There shouldn't be any
> dead beats at all. Fix that system-wise."*

## The law

**The pipeline may not ship a dull beat.** Knowing a beat is dull is not the
finish line — it is the trigger to fix it. The judges (interest, cool) can
already TELL; the system now ACTS on that automatically, before the video is
delivered.

## The loop (`scripts/no_dull_beats.py`)

```
render ─▶ judge (interest + cool) ─▶ any dull beat?
   ▲                                      │ yes
   │                                      ▼
   └──── re-render ◀── escalate each dull beat to MOTION of its subject
                                          │ no
                                          ▼
                                     ship it (0 dull beats)
```

Runs until **zero dull beats**, or it runs out of escalations — in which case it
**reports** exactly which beats are stuck and why (almost always motion that is
access-gated), never hides it.

## What counts as "dull" (judged on pixels, not intent)

A beat is dull if **any** of:
- **appeal < 0.55** — a flat card nobody stops scrolling for;
- the cool judge flagged it **DULL / LOW_MOTION / STILL_WHEN_MOTION_EXISTS**;
- it sits inside an interest-judge **dead stretch** and appeal < 0.68.

The **HOOK is exempt when its appeal is high** — a bright designed slam is
allowed to hold for a beat; that is a deliberate open, not a dull spot.

## The escalation

One level per round, per beat:

> a flat/designed card or a still  →  `_force_motion`

The planner re-emits the beat as a **depict shot**, so the motion-first gate puts
a MOVING clip of the beat's subject under its text (still fallback only if no clip
clears the bar). A dull card becomes a moving shot. The subject comes from the
beat's `subject` / `motion_query` / media query, or is derived from its own
narration.

## Why the stock keys matter here

Escalation reaches for motion of the subject. For a **ground / human-scale**
beat, that motion lives in Pexels/Pixabay — so `PEXELS_API_KEY` /
`PIXABAY_API_KEY` being **top of the pipeline** (now forwarded in `curiosity.yml`,
and stock ordered first for ground perspectives in `media.find`) is what lets the
"no dull beats" loop actually succeed instead of reporting "stuck: motion
access-gated." Space-scale subjects escalate against NASA and need no key.

## Relationship to the Showrunner

The Showrunner (`quality_memory/`) remembers dull beats *across* videos and warns
before a render; `no_dull_beats.py` fixes them *within* a render. Prediction +
prevention + cure.
