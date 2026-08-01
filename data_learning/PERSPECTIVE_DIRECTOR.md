# THE PERSPECTIVE DIRECTOR

Topical is not the same as point-conveying. A hurricane seen from orbit is *about*
hurricanes, but a slow cloud from space does not make a viewer FEEL the point —
that this thing is violent, powerful, and would destroy you. The same storm seen
**from the ground** — palms bent flat, rain going sideways, a street underwater,
a person leaning into the wind — conveys the point instantly and is far more
view-worthy. This director asks, for every beat: *is this the way that best
conveys the point and that a viewer most wants to see?* — and when it isn't, it
specifies a better shot and goes to get it.

## The core test

For each beat, given its POINT (what the viewer should feel/understand), ask:

1. **Does the perspective convey the point?** "This storm is deadly" is conveyed
   by consequence at human scale (surge, damage, people), not by an abstract wide.
   "This is enormous" is conveyed by scale contrast. "This is beautiful/eerie" by
   the calm eye. Match the CAMERA to the FEELING, not just the topic.
2. **Is it the most view-worthy way to show it?** Between two accurate options,
   pick the one a person would rather watch: visceral > abstract, human-scale >
   god's-eye, in-the-moment > diagrammatic, consequence > depiction — unless the
   point itself is scale/overview (then the wide wins).
3. **Would a different PERSPECTIVE be cooler here?** Explicitly consider the
   ground/POV/close/human angle before defaulting to the wide or orbital one.

## Perspective menu (default reach order per feeling)

- **Danger / power / stakes** → ground-level in the weather: wind bending trees,
  horizontal rain, storm surge, flying debris, a person braced against it. THEN
  optionally the orbital wide as a chaser.
- **Scale / overview / "where it is"** → the satellite/orbital wide (this is the
  one case the god's-eye is right).
- **Mechanism / how it works** → a designed diagram (already have flat_engine).
- **Beauty / eeriness** → the specific striking shot (the clear eye, the eyewall).
- **Human meaning / consequence** → people, streets, aftermath, scale relative to
  a body/a house/a city.

## The rule the hurricane broke

A film about a hurricane that shows ONLY the orbital view is like a film about a
lion that only shows it sleeping. Give at least one **ground-truth / human-scale**
shot of the subject as it is actually experienced — the money shot of relatability
— then use the abstract/orbital for scale and context. Never let the whole film
live at one distance from the subject.

## What the director outputs (per weak beat)

`{beat, verdict: WEAK_PERSPECTIVE|OK, why, ideal_shot: {perspective, scale,
subject, source_hint, search_terms}}` — e.g. for the hurricane HOOK/MECHANISM:
"orbital cloud is abstract; the point is danger — get ground-level footage of the
storm making landfall (bending palms / horizontal rain / surge). source_hint:
stock/CC (Pexels, Pixabay, Wikimedia, archive.org); terms: 'hurricane wind palm
trees ground', 'storm surge street', 'tropical storm making landfall'."

## Sourcing (the DOING) — THE MEDIA GATEWAY

The director's ideal-shot spec drives the **media gateway** (`data_learning/
media.py`) — one front-of-pipeline entry point that reaches many sources for an
IMAGE *or* a VIDEO at a given perspective, honours commercial CC licensing, and
DECLARES the access it can't reach instead of silently shipping a worse shot:

- **Openverse** — 800M+ CC/PD images; free, no key. Real photos of real events
  (a street drowned by surge), commercial-filterable. The default for "get a real
  photo of X." **This is the enabler the free video pools never were.**
- **Wikimedia Commons** — PD/CC images + video.
- **Google Images (Apify)** — broadest / most RECENT news photos; the operator's
  preferred "just google a recent hurricane" path. Premium (Apify credits) and
  currently blocked on interactive paid-actor approval in the headless remote
  environment — `media.access_report()` DECLARES this need rather than faking it.
- **NASA** — space/orbital/Earth-science video.
- **Pexels / Pixabay** — CC0 ground-level video b-roll; needs a free key.

Images become motion via a **Ken Burns** shot (`image_beat` — a still gets a pan
PLUS a zoom, more move than footage, so a real photo reads as a live camera move,
never a frozen slide). Every image writes a CC credit to the package.

### The lesson the free pool taught (appeal ≠ point-conveyance)

`best_image` ranks on appeal × relevance, drops orbital/satellite titles for a
ground beat, and gates on a topical anchor — but that still isn't enough. For the
"Nothing on Earth can stop it" payoff those filters picked a bright-red FDNY fire
truck being *washed* (topical to Sandy, high appeal, correct perspective) — the
exact OPPOSITE of unstoppable devastation. **Whether an image conveys the POINT is
a semantic/vision judgment a pixel metric can't make.** So the gateway does the
automatable filtering; a **vision judge** (a subagent, or the operator's Google
Images path returning devastation on the first hits) makes the final point-
conveyance pick. The Katrina drowning-street payoff was chosen exactly this way.

Every fetched image/clip still passes the exact-window analyzer, the interest/
appeal metric (a bland clip is rejected even if on-topic), and the continuity
director.

## Where it sits

A judge (sees the beat map + frames, reasons about perspective) plus this
doctrine. It runs alongside the editorial, continuity, interest and hook
directors. Its verdict feeds authoring/repair: swap the abstract beat for the
point-conveying one, or ADD a ground-truth beat next to the orbital one.
