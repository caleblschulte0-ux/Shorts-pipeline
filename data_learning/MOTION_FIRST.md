# THE MOTION-FIRST LAW

> Owner's note, verbatim: *"If we have the choice to show a picture of a car it
> hurt — or an actual hurricane video of it beating down; or the choice between a
> still picture of a hurricane from space and a moving picture of a hurricane
> time-lapse — that's what we need to be showing. It needs to be favoring stuff
> like that. That's way cooler and more interesting to watch than the still
> image. And you're fixing the system, not just this video."*

## The law

**When a beat's job is to DEPICT a real subject, a MOVING clip of that subject
always beats a still of it.** Motion is more view-worthy than a photograph of the
same thing, every time. A still is *earned*, never a default — it is shown only
when:

1. **No clip of the subject clears the bar** — clean window + genuine movement +
   on-topic + right perspective. (Then the still is the honest fallback, and the
   render **logs why**: "no moving clip cleared the bar," not silence.)
2. **The still carries information a clip can't** — a chart, a map, a diagram, a
   specific document or dated photograph. That case never reaches the gate: it is
   authored `still: true` (or is a `flat`/`number` beat, which have no depiction
   image at all).

This is a **selection-time preference wired into the system**, not a note on one
video. Every depiction beat in every story is motion-first by default.

## Where it lives (three layers, one decision)

| Layer | File | Role |
|---|---|---|
| **Authoring gate** | `planner.py` `_motion_eligible()` | A depiction beat (`function: experience`) that declared a still is emitted as a `depict` / `depict_text` shot carrying a `motion_query` **and** the still as fallback. Beats that explain (charts/maps) or pin `still: true` stay stills. |
| **Decision gate** | `media.py` `motion_first()` | Given the subject + beat length, probe the most on-topic video candidates (NASA + stock), confirm each has a clean, **genuinely moving** window (`_clip_motion ≥ MOTION_FLOOR`) at the **right perspective**, and return the first winner — else `None`. |
| **Render resolution** | `pro_render.py` `_depict_shot()` | Motion hit → render as footage (with any text laid over the clip). Miss → render the declared still. Either way the choice is logged. |

## The bars a clip must clear (why a still can still win)

A clip only wins if it is genuinely *better to watch*, not merely "a video":

- **Clean window** — `footage_hybrid.pick_window` finds a `dur`-second span with
  no black / title-card / hard-cut frames (existing footage law).
- **Genuine movement** — `media._clip_motion ≥ MOTION_FLOOR` (mean frame-to-frame
  change). A video that is functionally a frozen plate is *not* cooler than a
  photo, so it does not win. A time-lapse, a spinning storm, a flooding street
  clears this easily.
- **On-topic** — `_relevance(title, subject) ≥ MOTION_REL_FLOOR`. An off-topic
  clip is not "the same subject."
- **Right perspective** — a `ground` / human-scale beat drops orbital-tell clips.
  We never "upgrade" a human-scale consequence shot to another shot-from-space;
  that would defeat the perspective director. If only orbital motion exists for a
  ground beat, the ground still wins.

The honest consequence: when the moving version of a subject lives behind an
access-gated pool (stock video keys unset) and NASA has only the wrong
perspective, the gate falls back to the still **and says so** — which is also the
signal for where an API key would buy a cooler shot.

## Author's contract

- Default: give a depiction beat an `image` block with a `query` (or a beat-level
  `subject`). The system will *prefer motion* of that subject automatically.
- Force a still: set `"still": true` on the image block (a chart, a map, a
  specific document — something a clip cannot replace).
- Force motion only: use a `footage` block as before (no still fallback wanted).
- Steer the motion search: add `"motion_query"` to the image block when the
  still's own `query` is not the best phrase to find a clip with.

## Regression guard

`scripts/cool_judge.py` carries a `STILL_WHEN_MOTION_EXISTS` label: a low-motion
depiction beat is flagged so a still that *should* have been motion cannot pass
silently. The law is enforced at authoring (planner), at selection (gate), and
audited after the fact (cool judge).
