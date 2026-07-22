# Editorial reset — the channel now fails CLOSED

**Date:** 2026-07-22
**Why:** The pipeline had a control-system problem, not a polish problem. It
was optimizing for green CI, valid JSON, publishing volume, and impressive
commit messages — not for taste, premise quality, real data, or whether a
human would send the video to a friend. Almost every layer *soft-failed*
(infra hiccup → ship anyway; empty queue → invent synthetic stories; weak
premise → render regardless), so nothing ever forced the finished video to be
good.

This reset inverts the default for the **publish** decision: a video uploads
only if it *proves* it deserves to. Everything unproven is **held**, not
shipped.

## What changed

### 1. Publishing is frozen (fail-closed kill-switch)
`scripts/editorial_gate.py :: publish_enabled()`. Uploading now requires an
explicit opt-in — `PUBLISH_ENABLED=1` in the env or `--publish` on the CLI.
Without it, `post_stories.py` still renders and reviews (previews keep
working) but **never uploads**. There is no YAML cron to disable — the daily
kickoff is an external Claude Routine — so the freeze lives on the upload path
itself, the one lever we control in-repo.

### 2. Real data only — illustrative numbers can never publish
`editorial_gate.data_provenance()`. Every segment's dataset must have a source
with `officiality ∈ {official, primary, secondary}`, a publisher, and an
access date. **519 of 546 datasets were `illustrative`** (LLM-authored). Those
are now unpublishable. A data channel that authors its own numbers to keep the
queue full is not a data channel.

### 3. Premise bar — weak premises die before render
`editorial_gate.premise_ok()`. The title + hook must clear a taste bar: a real
expectation-reversal and a consequential number. A searchable noun phrase
("Oldest Written Languages", "Tectonic Plates on the Move") is an auto-reject.
An adversarial LLM judge — whose job is to find reasons to **reject** — has the
final say when a brain is reachable; a deterministic floor governs when it
isn't.

### 4. The queue-filler is gone
`scripts/author_stories.py` is disabled by default (it authored the
illustrative numbers). The `author` workflow mode is a no-op. **Zero videos on
a weak day beats four generic ones.** Real stories are added by hand from a
real, cited dataset.

### 5. The visual gate actually looks, and fails closed on a publish run
`post_stories.py` + `scripts/showrunner_review.py`. The showrunner extracts
frames from the finished video and grades it. On a **publish** run it fails
**closed**: if the reviewer can't run (no key, API/ffmpeg error, timeout, or a
verdict with no score) the video is **held**, because we don't *know* it's
good. Only previews/frozen runs fail open (so iteration isn't blocked by
infra). `SHOWRUNNER=off` is refused on a publish run.

### 6. One controlled format
`studio_render.py`. Optional layers are no longer all mandatory at once.
Blender 3D bookends are OFF by default (`EXPLAINER_3D=1` to opt in); the
b-roll filler strip and AI/stock cutouts are already off in the CLEAN path;
AI-invented procedural mechanics are gated behind `VIZ_IMAGES=on`. The default
production look is one intentional 2D format: flat dark editorial background,
one real sourced chart, Data (the mascot host), narration, burned captions.

### 7. One experiment at a time
`state/brain_context.json`. `max_concurrent_experiments: 1`. Dozens of
simultaneous changes make it impossible to learn anything. Two canaries, one
changed variable, a predetermined success metric, then keep or revert. The
scoring now weights `reaction_rate` (comments + shares + subs per view)
heavily — the analytics showed videos that held attention still generated zero
reactions. Retention is not interest.

## How to publish a real video again

1. Add a **real, cited dataset** by hand under `data_learning/data/` with a
   source whose `officiality` is `official`/`primary`/`secondary`, a
   `publisher`, and an `access_date`.
2. Write a story whose **premise reverses an expectation** and hangs on one
   consequential number from that data.
3. Preview it: `python scripts/post_stories.py --slugs <slug> --dry-run`
   (renders + reviews, uploads nothing). Check `editorial_gate` passes:
   `python scripts/editorial_gate.py <slug>`.
4. Canary ONE video: the `canary` workflow mode publishes a single video with
   `PUBLISH_ENABLED=1 --publish`, still behind the fail-closed review gate.
5. Measure the predetermined metric before changing anything else.

## Not done here (follow-ups)
- A full renderer teardown (deleting the unused Blender / b-roll / procedural
  subsystems rather than gating them) — left reversible on purpose.
- Backfilling real datasets to replace the ~519 illustrative ones.
- Wiring the premise judge into the authoring UX so new stories are graded as
  they're written.
