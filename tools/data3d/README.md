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
   Then `stories/<name>/plan.json`, BEFORE any shot code (see "A shot is born to the recipe" below):
   `python store/shot_plan.py blank <name>` prints one to fill in, `python store/shot_plan.py check <name>` says what
   it breaks, and `python store/recipe_stage.py stub <name>` prints the first `shots.py` from it.
2. `stories/<name>/shots.py`: `shot1() .. shotN()` and `SHOTS`. Each builds its act and returns `data`, `conseq` (what
   each thing Data does CAUSES), `grips`. The harness (`store/shots.py`) adds the store, the lights and every check.
   Hands only move for a job: `reach()` (relaxed FK before and after, IK on the moving point during) keeps idle
   mittens out of the coat. Props that rot, droop, swing or spill: `store/produce.py`.
3. Voice it: `.github/triggers/data3d_render` with `story=<name>` and `mode=narrate`. Put the windows from the run's
   NARRATION line in `draft_windows`, then time the shots to them.
4. Local test pass (`STORY=<name> SHOT=n STAGING=on` with `STEP`) until every check reads OK, then the full render:
   the trigger with `story=<name>`, `narration_run=<the narrate run>`, `spp=48`, `pct=100`.

**Placement is frame-first** (`store/compose.py`, caaleb 2026-11-23: "our code is shit if it's cutting this off and
putting them in the wrong spot"). A shot says where on the 1080x1920 screen a thing goes (0..1 across, 0..1 up) and
the solver finds where it goes in the world, instead of typing world coordinates and aiming a camera somewhere else:
- Data: `frame_data(data, CAM, LOOK, lens, face_at=(x, y), height=h, t=...)` solves the CAMERA (truck and dolly, never
  him: his hands are already on the set) so his face lands at `face_at` and he stands `h` of the frame tall.
- a sign, a label, a prop: `place(obj, cam, box=(x0, y0, x1, y1), frame=f, depth=d | on_ground=True, scale_ok=...)`
  slides (and, if allowed, scales) it until its projected box sits in `box`; `place_keys` does it per keyframe for a
  moving thing. A solve that cannot fit prints a `COMPOSE ... -> FAIL` line.
- every shot returns `boxes` [(label, objs, box[, t0, t1])] for its signs and its beat's key prop; `compose.check`
  holds them through the shot, strict. `tests/test_data3d_compose.py` runs the solver without Blender.

The checks the board judge used to catch by eye (2026-11-23, run strict by `store/shots.py`; held by
`tests/test_data3d_what_the_board_caught.py`): `staging.edges` (no FONT object or sign / label mesh cut by the frame
edge longer than 0.3 s; he ends the beat whole in frame), `staging.keys` (the board's four stills each show something
new), `staging.talking` (facing us, centred, hands on no grip and feet still is a talking head), `staging.cause`
(a declared moving part starts to move only with his hand on a grip or on it).

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

## A shot is born to the recipe (2026-11-26)

The operator: "this needs to be an autonomous system that can pump out 1,000 of these", and, of shots that took 4 to
18 judge rounds each, "what are we not fixing here? Because clearly something is continuously not getting fixed."
What was not fixed: a shot started as a blank Blender file, and the panel found its staging forty minutes at a time.
Over the round reports of lava, cardrewards, helium and honey (1,225 hard lines, counted by keyword) the same faults
come back in every video: a toy or flat prop (194), a thing cut by the frame edge (188), a promise of the texts no still shows (249), a
subject too small or a shot too wide (128), a thing floating (85), a hand not on what it holds (60), a thing that
appears or changes place (50), the event behind him (50), one picture repeated (38). The shots that passed share one
staging (the recipe below), so it is now where a shot STARTS. The order for every new story:

**plan -> validator -> staging helper -> local checks -> pre-flight -> judge**

1. **The plan** (`store/shot_plan.py`; `stories/<story>/plan.json`, beside `script.json`). Per shot, before any shot
   code: `prop` (the ONE thing the shot is close on) and `props` (each with the object-name prefixes it is built
   under, `whole` or field-wide, and what real thing it is `built_as`); `framing` (close or medium, never wide);
   `data` (he stands beside / at the foot of / in front of the prop, on which side of the frame, a third of the frame
   or more); ONE `action`; ONE `consequence`; and the four `stills` (before, action, result, reaction), each with what
   it `shows`, what his `hands` are on, and what is `new` in it since the last (a prop that moves, comes, goes, grows,
   falls, breaks, opens, lights..., with its `cause`; or his pose). **The validator** (`shot_plan.problems`, run by
   `store/shots.py` beside the story gate, strict: no shot of a new story is built without a plan that passes)
   refuses: fewer than four distinct stills; a still with nothing new; the same change three times, or "bigger /
   nearer" as a change (one pose scaled); more than one action or consequence; a consequence the result still does
   not show, or a result that changes no prop; a clause of the storyboard line (FOR) or a number of the spoken line
   (SAYS) that no still shows; a wide or establishing camera as the only framing; a prop that changes with no cause,
   has no parts, or is a box / cone / sprite / card; hands on something the shot does not declare. Stories staged
   before the plan are named in `PLAN_BEFORE` with the reason; the list only shrinks.
2. **The staging helper** (`store/recipe_stage.py`). `from_plan(plan, prop_at, prop_size)` returns where he stands,
   his yaw, the camera and four keys (before: ready, looking at the prop; action: leaning in, hands on it; result: a
   step back; reaction: turned to us), searched so that he is a third of the frame or more, three-quarter (chest 20
   to 50 degrees off the lens, turned toward the prop), on his side of the frame with the prop whole, a quarter of
   the frame or more, on the other side and never behind his back. Its numbers are lava shots 3, 4 and 5 as they
   passed (24 mm, 0.345 / 0.35 / 0.42 of the frame, face at x 0.24 to 0.38). `place`, `perform` and `frame` put it on
   his rig; a shot is then a few lines (the module's head has the pattern, `stub` prints it for a planned story). A
   prop too big to be whole beside him is refused with the way out: come closer to less of it, or declare it
   `whole: false` and name the `focus` where the event happens.
3. **The measured check** (`store/recipe_check.py`, run by `store/shots.py` after `staging.keys`, strict for a
   planned story, printed for the rest; the facts go to `recipe.json` beside the stills). On the board's four stills
   as staged: CLOSE (0.3 of the frame or more on three of four), FACE (his face within 70 degrees of the lens on
   every still; not square-on with the event behind his back), FRAME (his whole body in the frame), EVENTS (each
   still differs from the last in kind: his pose bone by bone in his own frame, so nearer or bigger is not a new
   pose, or a declared thing changed in the world; and the result is in the world), HANDS (a hand within reach of
   what the plan says he holds; a grip in mid-move has a hand on it), EDGE (no whole declared thing cut by the
   frame), CAUSE (no whole declared thing changes place with no hand on it, no consequence declaring it and no
   cause in the plan), PLAN (what a still promises as new is measured there).
4. Then the checks that were already there, the pre-flight and the panel, unchanged. None of this can pass a shot or
   touches the judge's bar. `tests/test_data3d_a_shot_is_born_to_the_recipe.py` holds it on recorded scene facts:
   lava shots 3, 4 and 5 as they passed must pass; shot 2 as restaged along the crest (commit a91a0a528, judged 38)
   and the wide round-6 restage (483b15222, judged 14) must fail for what the panel said of them.

**What the staging helper was measured on.** `recipe_stage.stage` is plain math and is held by the test over a spread
of props (close, three-quarter, prop whole and big, nothing behind him). `recipe_stage.perform` (the canned four-event
performance) was built through `store/shots.py` with no render on ONE scratch shot (a 0.5 m crate, his hand on it) and
read OK on STAGING, KEYS, TALKING, CAUSE, ANATOMY, CLIPPING, TWITCH, FLUID, REACH, POP, HOLD, READ, FAR and RECIPE. A
taller crate pushed straight away from the lens failed ANATOMY and CLIPPING, so it is a first performance the checks
still judge on every build, not a pass. Props over about 0.6 m are staged out of his reach (`st["reach"]` is False) and
the shot keys its own tool, throw or walk.

## A shot passes the board in two or three rounds (2026-11-25, after the lava rounds)

The lava short failed seven storyboard rounds overnight and then took four a shot. The board judge
(`store/judge3d.py`) grades each shot's four stills against three texts: its storyboard line (FOR), its spoken line
(SAYS) and the script's `world`; anything named there and not visible is a hard fail. Three checks now run before a
panel is spent, in this order, each wired where named. None of them changes the judge's bar or can pass a shot.

1. **Showable lines** (`store/story_gate.py`, `showable_problems`, run by `store/shots.py` with the rest of the story
   gate): every number and named thing in a spoken line can be seen or counted in ONE phone frame. Code refuses a
   count above `COUNTABLE` (10), "N times", a rate, a percentage and a crowd by magnitude ("thousands"); a size
   ("three stories tall") is seen as a size. The cold readers of `story_gate.py judge` must also name, per line, the
   one picture that shows it (`pictures`) and list any line no frame can show (`unshowable`), or the story fails.
   `tests/test_data3d_a_spoken_line_fits_one_phone_frame.py`.
2. **The shape of a storyboard line** (`store/boardlint.py`, `shape`, run by `store/shots.py` before a shot is built):
   a line is `N name (place; camera): action`, and the action is ONE action and ONE consequence written as what four
   stills show. Refused: more than `MAX_EVENTS` (5) clauses, `MAX_BEATS` (4) sentences or `MAX_WORDS` (80) words of
   action; a camera move inside the action; a prop that leaves his hands and is not named in the last sentence.
   Stories written before the rule are named in `SHAPE_BEFORE` with the reason.
   `tests/test_data3d_a_storyboard_line_is_four_stills.py`. The staging that passes (`boardlint.RECIPE`, also given to
   the proof loop's reviser):
- write the line as what the four stills show: BEFORE, the ACTION, its RESULT, his REACTION. One action, one consequence.
- a CLOSE shot: Data fills a third of the frame or more, and the event is right beside him or in front of him, mid-frame.
- nothing that is the subject touches a frame edge in any still; if it does not fit, come closer to less of it.
- Data stands three-quarter to the lens: face and chest to us, never in profile for the whole shot, never his back.
- the four stills are clearly different from each other: a new state in each, not one pose held.
- one grade across the stills: the same light and colour in all four unless the line says the light changes.
- his feet are planted on the ground in every still (a jump is in the line or it is not in the shot).
- every prop the line names is in the result: in his hand, on the ground where it fell, or changed by what happened.
- say the camera once, in the opening brackets, and render that camera: no camera move inside the action.
3. **The pre-flight** (`store/preflight3d.py`, called by `store/judge3d.py` on every storyboard round, so by
   `proof_loop.py` and `board3d.sh` alike): code lists every claim of FOR + SAYS + the world for the shot
   (`python store/preflight3d.py claims STORY SHOT`), and ONE headless look at the sheet must tick each against a
   specific still and answer continuity between the stills (props accounted for, one grade, feet on the ground,
   subject whole in frame, four different stills). A shot with an unticked claim is not sent to the panel that round;
   it prints what to fix or which promise to take out of the text. No look, no round. The result is kept in
   `stories/<story>/preflight.json` keyed by the sheet's sha256. `tests/test_data3d_the_sheet_is_checked_before_the_panel.py`.

## The realism kit: fire, lava, houses, roads, ground, water and skies are never built by hand (2026-11-26)

Every 3D short used to build its own fire, smoke, lava, houses, sky and ground in its own shots, from spheres, boxes
and a flat colour, and the panel failed each one as OFF THE LOOK: "clay smoke", "flat flame sprite", "popcorn bombs",
"Monopoly houses", "the fountain lights nothing", "one flat green plane". The lava short met those notes in most of
its twenty-six board rounds. The three shots that passed were made of the same few parts (a real Poly Haven sky, a
real scanned texture on every surface, fire and smoke as a gas, lava as black crust with light in its seams, a lamp
beside everything that glows). `store/fx_kit.py` is those parts, lifted and made general. The harness imports it as
`FX`, so a story's shot calls `FX.fire(...)`, `FX.house(...)`, `FX.sky("dawn", sun_az=-55)`.

| element | group | glows | what it is |
|---|---|---|---|
| `FX.sky` | sky | yes, with its light | a REAL sky (Poly Haven HDRI) that lights the scene, with the sun lamp aimed at the sky's own sun: presets day, noon, afternoon, dawn, sunset, dusk, evening, blue_hour, night, overcast, heavy; sun_az turns the whole sky |
| `FX.ground` | ground |  | real scanned ground with relief (kinds: rock, lava_field, gravel, trail, scree, burned, grass, meadow, shore, mud, sand, snow, mountain): never a flat plane of one colour |
| `FX.road` | ground |  | a real asphalt road (scanned asphalt, a worn centre line, gravel shoulders with loose stones) |
| `FX.rocks` | ground |  | real scanned boulders (Poly Haven models) and broken stones scattered over a patch, each turned and sized differently: never a sphere, never evenly spaced |
| `FX.house` | built |  | a real small house: weathered painted corrugated tin (scanned) on a concrete base, a coloured tin roof with rust and grime, gutters, downpipes, corner boards, a chimney, paned windows, a door and steps; size, storeys, pitch and colours vary with seed; burn>0 chars it and breaks its roof open; lit windows cast their light |
| `FX.car` | vehicle |  | a real car (kinds: hatch, suv, van, pickup): one smooth lofted body with a bonnet, a raked windscreen, pillars and wheel arches, coated paint with road dirt, glass that carries the sky, rubber tyres on spoked rims, mirrors, shut lines, plates; head and tail lamps that are lit lenses AND the lamps they cast (spots on the road ahead, red behind) |
| `FX.parked_car` | vehicle |  | the one REAL car in the asset library: a scanned car parked under a tarpaulin (a prop for a drive or a yard; it has no lamps and does not drive). Falls back to FX.car when it is not unpacked |
| `FX.truck` | vehicle |  | a tipper truck: a cab-over cab (lofted, glazed, mirrors on arms), a steel chassis, six wheels on steel rims, a ribbed tipper body of worn painted steel that can be raised and loaded with rock; head, tail and amber marker lamps that light |
| `FX.digger` | vehicle |  | a digger (a tracked excavator): two steel tracks with pads, rollers and sprockets, a slewing house of worn yellow painted steel with a counterweight and an engine cover, a glazed cab, and a boom, stick and toothed bucket on chromed hydraulic rams that pose by angle; work lamps that light |
| `FX.fire` | fire | yes, with its light | a burning fire: torn flame tongues as a gas, a soot column rolling out of its top, and the warm flickering lamp it casts on everything near it |
| `FX.smoke_column` | fire |  | a column of smoke as a gas: it billows, widens as it climbs, leans downwind and thins away (dark soot by default; col for ash or white) |
| `FX.steam` | fire |  | a burst of white steam as a gas that boils up, spreads and dies away on the keys it is given |
| `FX.dust_puff` | fire |  | a puff of dust kicked up from the ground: a low, wide, tan cloud of gas that swells and settles |
| `FX.house_fire` | fire | yes, with its light | a house on fire from INSIDE: the blaze comes up through the hole in its roof into a soot column, flames lick out of its upper windows, and its light falls on the ground and the walls beside it (needs FX.house(burn=...)) |
| `FX.glow_light` | fire | yes, with its light | the lamp for anything that glows and is not from the kit (a lit sign, a lantern, a hot coal): put it beside the glowing thing so its light falls on what is near |
| `FX.lava_flow` | lava | yes, with its light | a lava flow: a lumpy slab of black cracked crust (real scanned rock) with orange light in its seams, hottest at its moving edge, drifting; lamps along its rim throw its glow on the ground and on Data |
| `FX.lava_pool` | lava | yes, with its light | a pool of MOLTEN lava: a level surface of dark glassy plates split by bright yellow-orange cracks that drift and re-form, brighter where it wells up and along its bank, held in a low levee of black rock, with its heat glow cast up and outward by its own lamps |
| `FX.embers` | lava | yes, with its light | glowing embers or lava bombs thrown on real ballistic arcs from a point: small beads of molten rock drawn into short streaks along their flight, yellow-white where they start and cooling to orange and dull red (sizes varied, never pale balls, never pink); the biggest leave a glowing splat with its own lamp where they land; with the lamp that lights the ground where they come from |
| `FX.lava_fountain` | lava | yes, with its light | a lava fountain, an ERUPTION and not a fire: a jet (or, with length, a fissure curtain) of white-yellow molten spray several houses high, solid at the vent and breaking into strands that fan out, hundreds of clots arcing off it and cooling to orange and dark red as they fall, splats glowing where the big ones land, a black spatter rampart with glowing cracks round the vent, a broad gas plume above lit orange from below, and strong orange lamps on the ground, the walls and the smoke |
| `FX.water` | water |  | open water: a dark, glossy surface with two scales of moving waves that mirrors the real sky (sea, harbour, lake); never a flat blue plane |

- **Every element returns a dict**: `objects`, `lights`, and what a stager needs (a root, a rim, a volume). An element
  that glows is registered `emits` and its wrapper refuses to return without a lamp, so a fountain that lights
  nothing cannot be built from the kit. `FX.sky` aims the sun lamp at the HDRI's own sun (one set of shadows) and
  `sun_az` turns the whole sky.
- **Assets** are the CC0 Poly Haven files of the orphan branch `data3d-assets`
  (`git archive origin/data3d-assets polyhaven | tar -x -C cache`). A missing one raises; a named second choice is
  another real asset and prints `FX FALLBACK`. Add an id to `.github/triggers/data3d_assets` to fetch more.
- **The lint** (`store/fx_lint.py`, run by `store/shots.py` on the shot being built, before the build and again on
  the built scene; `python store/fx_lint.py STORY`): `HAND` is a sphere, box or cylinder whose name says it is one of
  the kit's elements ("lava bomb splat", "street asphalt"); `UNLIT` is a shot that makes something glow and creates
  no lamp, or a glowing object with no lamp near it; `OWN` is a story defining its own fire or house. It only adds a
  block. Stories written before the kit are named in `fx_lint.BEFORE` with the reason, and the test fails when an
  entry is no longer needed. `tests/test_data3d_the_kit_not_by_hand.py`.
- **Look before using a change to the kit**: `python -I store/fx_sheet.py fire|erupt|curtain|lava|built|vehicles|plant|water|sky:<preset> OUT.jpg`
  renders one small sheet of a group beside a real set; open it at phone size. The proof loop's reviser is given
  `fx_kit.brief()` beside the staging recipe.
- **Emission is measured, not guessed**: under this pipeline's view transform an orange emission above ~2 renders
  peach and a red above ~1 salmon pink ("pink confetti"); only yellow-white may be bright. The kit's lava, clots and
  lenses are set from a rendered chart, and a lamp strong enough to bleach its own emitter is too strong.
- **Vehicles** (`store/fx_vehicles.py`: `FX.car` hatch/suv/van/pickup, `FX.truck`, `FX.digger`, `FX.parked_car`) are
  built, because the asset library has one car and it is under a tarpaulin. Head and tail lamps are lit lenses and
  the lamps they cast; `power` is per head lamp (70 W reads in daylight, 250 and up at dusk).
- **What it is not**: the kit makes the elements real; it does not stage them. A fountain cut by the frame edge or a
  house row seen from 60 m still fails the board for those reasons.

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

## One real person (caaleb 2026-11-23, of the lightning short)

"He's doing too much. He's changing emotions too often. He's twidgeting too fast. His legs are glitching out of his
coat. His head moves really fast ... Not that I'm saying we need to make him less reactive." The rig now makes him
that way, and `store/steady.py` (every shot, after the face lint; FAIL under `STAGING=strict`, `STEADY` lines in
proof_loop) holds it:
- **Faces are CAST, not keyed.** A shot's `expression()` calls are what it ASKS for; `finish()` casts the faces he
  shows (`face_plan`): each held `FACE_HOLD` (1.5 s), at most `FACE_MAX` starting in any `FACE_WINDOW`, each blended in
  over `FACE_BLEND`, changing only on a moment the shot asked for a change. Surprised/alarmed/surprised/alarmed is ONE
  shock.
- **Looks are cast too** (`look_plan`): head turns land at least `LOOK_GAP` apart; a look asked sooner is a glance of
  the eyes. The head, neck, chest and spine FOLLOW the asked pose at a person's speed and settle (`head_follow`,
  `HEAD_LIMITS`), and the neck soaks up the body's jolts so the head rides smooth through a hop or a stagger
  (`gaze_steady`). A held pose drifts low and slow (`LIFE_AMP`, `LIFE_SLOW`).
- **The coat rides the legs** (`coat_weights`), the legs are solved at their rest roll (they were turned over, which
  spun the coat round the thigh), and what is sewn on it rides its surface (`COAT_SEWN`, Surface Deform, sliced every
  `SEW_STEP`).
Lightning as posted vs the same shots built now: faces 4-8 -> 2-3 a shot; head 141-310 -> 60-103 deg/s; head jitter
73-97% -> 16-50% of frames; coat 57-180 -> 0-11 frames. `DATA_STEADY=0` builds the old way.
`tests/test_data3d_steady.py`.


## The shots run side by side (2026-11-26)

Measured first (runs 44400238941 and 45115274403): the final render was already forty jobs, never one. Setup is half
a minute of a job and the scene build about a minute; the rest is Cycles, 1,758 runner-minutes for a 729-frame short
(87 s a frame in one stretch, 287 s in the next). The account runs twenty jobs at once, so a full render cannot take
under about 90 minutes of frames however it is cut; it took 105 and 143, after a proof of 11 to 35 minutes. What a
short costs is runner-minutes, and two things lower the wait:

- **A board round in CI, every shot at once.** Push `.github/triggers/data3d_board` (`story=lava`, optionally
  `shots=1 3`, `keys=4`, `narration_run=<id>`, `dry=1`). Each shot gets its own runner: the same `shots.py` stills
  call as `store/board3d.sh` and the same `judge3d.py` panel on that shot alone. The collect job writes the round
  into the story's `judge_rounds.md`, `notes_ledger.json` and `preflight.json` on the branch's tip (pull before the
  next edit; `judge_rounds.md` merges by union). Stills, sheets and verdicts are the run's artifacts
  (`gh run download <id>`). Five shots cost the wall-clock of the slowest one. It needs `CLAUDE_CODE_OAUTH_TOKEN`;
  it renders no video and opens no gate.
- **A render copies the shots that did not change.** `store/render_plan.py` runs after the proof and the judge have
  passed. Each shot has a key, a hash of everything its pixels are made from; a shot whose key a run of the last
  three days still holds is copied from it, and only the others render, each in its own frame ranges. A fix to one
  shot of five renders about a fifth of the frames. `fresh=1` in the trigger copies nothing; `reshoot=3 4` renders
  those shots whatever their key; `reuse_run=<id> reshoot=3 4` is the old by-hand form. `python store/render_plan.py
  keys <story>` prints the keys. An edit to a helper or a kit changes every shot's key; an edit inside one
  `def shotN():` changes only that shot's.

Twenty runners is the ceiling for everything in this repository at once. More videos a day than that allows needs
more runners (larger or self-hosted), which is the operator's call, not a code change.
