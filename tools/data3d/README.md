# tools/data3d — the 3D Data character and the 3D explainer sets (rebuild, 2026-11-06)

The first build of all this lived only in a session scratchpad and was wiped by a container restart on
2026-11-06 02:03Z. Everything here is committed on every change for that reason. Nothing in this folder is imported by
the posting pipeline; it is tooling for the 3D look trial (caaleb's rule: the pipeline keeps posting the 2D B-look
until 3D is approved).

- `base_build.py`: ChatGPT/Codex's approved Data model, verbatim from branch `codex/data-3d-reference`. Never redesign him.
- `character.py`: the rig on that model and the animation API (see NOTES_lost_asset_api.md for the API the lost
  version had; this one keeps the same names where it can).
- `store/`: the checkout set, staging, lighting and post.
- Environment: `python3.11 -m venv vbpy && vbpy/bin/pip install bpy==5.0.0 pillow numpy` (the bpy wheel is 380 MB).

Director rules (caaleb): pose for the ONE camera that sees it (Crash Bandicoot / early PlayStation): a side-on arm to a
cart handle is one straight line shoulder to handle end, measured every frame, never eyeballed. Still for approval
before any clip; a fast every-10th-frame test pass viewed at full size before any full render.

## Making the next 3D short (the system as of the second short, 2026-11-12)

caaleb, 2026-11-12: "get it done without me having to say anything, and then for me to give it my stamp of approval."
A new short is a FOLDER and a trigger, nothing else:

1. `stories/<name>/script.json`: `slug`, `title`, `lines` (hook, beats, closing, inside the registry's explainer
   pacing caps: `tests/test_data3d_story.py` holds it), `sources` (every claim with the source's own words and URL),
   `storyboard` (one brief per shot; the judge grades each shot against it), `draft_windows` (the voice's windows once
   it is voiced).
2. `stories/<name>/shots.py`: `shot1() .. shotN()` and `SHOTS`. Each builds its act and returns `data`, `conseq` (what
   each thing Data does CAUSES), `grips`. The harness (`store/shots.py`) adds the store, the lights and every check.
   Hands only move for a job: `reach()` (relaxed FK before and after, IK on the moving point during) keeps idle
   mittens out of the coat. Props that rot, droop, swing or spill: `store/produce.py`.
3. Voice it: `.github/triggers/data3d_render` with `story=<name>` and `mode=narrate`. Put the windows from the run's
   NARRATION line in `draft_windows`, then time the shots to them.
4. Local test pass (`STORY=<name> SHOT=n STAGING=on` with `STEP`) until every check reads OK, then the full render:
   the trigger with `story=<name>`, `narration_run=<the narrate run>`, `spp=48`, `pct=100`.

What every shot is held to before a frame renders (store/shots.py runs them; a story after the first fails on any):
- **one clock**: `clock.py`, 30 fps, everywhere; shots tile the voice with no gap (`clock.span`).
- **medium shot or closer**: `staging.MIN_H` 0.28 of the frame, head to feet, on 85% of frames (the first short ran
  at 0.14 and was called "tiny").
- **face to the lens**, **every action shows its consequence**, **no joint bends the way no body can**.
- **no clipping**: `clipping.py`, strict for every story but the first.
- **the ending is the payoff**: the last shot's final second still shows a declared consequence and the camera does
  not pull back (`staging.ending`; the first short's showrunner hold was "ends on Data standing idle").
- **native**: `story/assemble.py` refuses frames that are not 1080x1920 and writes `render.json` (the measured
  output); captions sit inside the Shorts / TikTok safe area and are timed to where the voice is actually speaking.
- **judged**: `judge3d.py` reads the story's own storyboard; the showrunner's preview verdict is written beside the
  video (`showrunner_preview.json`). Posting is `data3d_upload.yml` on main, only on the operator's word.

## The ending asks the viewer something (caaleb 2026-11-13)

"We need to be ending the videos with like a question, so people have a reason to comment or engage." A new story's
last line ends on a question a viewer can answer in a comment (at most the registry's `question_words`), and the 3D
music bed sits at `MUSIC_BED_3D` in `story/assemble.py`, under the 2D explainer's. Held by
`tests/test_data3d_story.py::test_a_3d_short_ends_on_a_question_and_its_music_sits_low`.
