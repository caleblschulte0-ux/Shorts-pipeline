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

## System-wide, 2026-11-14 (after the saffron rounds)

Every one of these runs on every story, wired where named, held by the test named:
- **storyboard lint** (`store/boardlint.py`, run by `store/shots.py` before a shot is built): a beat's payoff is a BIG
  prop or action, never "barely / slightly / subtle" or a face alone ("reacts", "looks alarmed", "a wry look").
  Posted stories are exempt; `saffron` is grandfathered with its reason. `tests/test_data3d_storyboard_lint.py`.
- **face lint** (`store/facelint.py`, beside twitch): inside a worried / alarmed / surprised / sad / wry / determined
  window the smile key and the mouth's SMILE READ (its corners' upturn, in resting smiles: rest is itself a smile)
  stay low. An expression now releases into whichever face holds the moment it ends, not to rest. `tests/test_data3d_face.py`.
- **faces differ**: every `EXPRESSIONS` entry is at least `MIN_APART` from every other over what a viewer can see;
  `wry` is ONE-SIDED (`cock`: one brow up; `side`: the mouth pulled to one side; shape keys only, his look unchanged).
- **looks read**: `look_at()` aims each pupil onto the target from where it really is on the final body (`eyes=False` opts out; a later `gaze()` at that frame wins) and a big look down bends the
  NECK too (up to 38 deg, layered in `finish()`); `anatomy.py` holds head+neck under `HEAD_BEND_MAX`.
- **motion you can see**: a consequence may declare `{"moves": True | [objects]}`; its travel is measured in pixels at
  1080x1920 and must reach `staging.MOVE_MIN` (6% of the frame height). A 2% needle flick is what failed the judge.
- **hands last**: `data.reach()` is shared (character.py); every IK key is re-solved in `finish()` if a later body act
  moved it off its target (`HANDS` line). `tests/test_data3d_rig.py` (on the rig when `DATA3D_BPY` names a bpy python).
- **the 180 rule** (`store/proof_loop.py`): three rounds under the bar on one idea and the reviser must carry the line
  with a DIFFERENT idea, camera / timing / framing tweaks forbidden. **Round reports**: every judge run appends to
  `stories/<story>/judge_rounds.md` (`store/rounds.py`). `tests/test_data3d_loop_and_reports.py`.
- **prop kit** (`store/prop_kit.py`): `alarm_clock`, `wilt`, `zero_mark`, `wall_clock`, `spin_clock`, held equivalent
  to the saffron code they came from.

## The ending asks the viewer something (caaleb 2026-11-13)

"We need to be ending the videos with like a question, so people have a reason to comment or engage." A new story's
last line ends on a question a viewer can answer in a comment (at most the registry's `question_words`), and the 3D
music bed sits at `MUSIC_BED_3D` in `story/assemble.py`, under the 2D explainer's. Held by
`tests/test_data3d_story.py::test_a_3d_short_ends_on_a_question_and_its_music_sits_low`.

## The order a smart studio works in (caaleb 2026-11-13: "what would an even smarter person be doing?")

1. **Start from staging that passed.** The idea's prop big and right in front of Data at chest height, camera about
   a metre away, Data chest-up; a field-wide effect gets a low camera among the near things. The consequence
   pre-check (`store/staging.py`, `CONSEQ_MIN_H`, `CONSEQ_INSIDE`) fails a prop under 12% of the frame or cut by its
   edge in seconds, before anything renders.
2. **Storyboard pass:** `STORY=<story> VBPY=<blender python> bash store/board3d.sh <dir>` renders four rough key
   stills of every shot (two shots at a time, every measured check first) and the judge reads them at phone size
   (`JUDGE3D_BOARD=1`). Fix until it passes. Minutes, not the 40 a proof costs.
3. **Proofs in parallel, in CI:** push the render trigger; `data3d_render.yml` proofs all shots at once and its
   judge must pass before a single full frame renders. Don't proof shot after shot on one machine.
