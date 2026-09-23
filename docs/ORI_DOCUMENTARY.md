# OpenRangeInteractive — the sleep films

**What ships:** once a week (`curiosity.yml`, Friday 19:00 UTC, plus
`clock.yml` re-firing a missed slot), one **two-hour** 1920x1080 history
story to fall asleep to, drawn entirely by code in a hand-drawn cartoon
style, uploaded to the OpenRangeInteractive channel **only if the
fail-closed showrunner passes it**.

```bash
python scripts/ori_author.py                     # write the next script (needs a brain)
python -m data_learning.ori_sleep --slug <slug> --out o.mp4 --max-seconds 90   # preview
python -m data_learning.ori_sleep --slug <slug> --out o.mp4                    # the whole film
python scripts/post_ori.py --dry-run             # render + judge, no upload
```

Stop everything for this channel: commit `state/curiosity_kill_switch`.

## Why (2026-09-22 → 2026-09-23)

The channel had posted one video and then nothing for eleven weeks. The
first rebuild (2026-09-22) was an 8-minute stock-footage documentary; its
first CI run was rightly blocked by the showrunner — a bird in a tree and
cartoon planets under "Life Without the Sun", the New York skyline under
"The Bottom of the World" — because a keyword search cannot match footage
to a line.

The operator's rulings the next day, in his words:

- *"people dont want to watch somthing thwy can tell is AI"* — and the
  market research agrees: in a January 2026 YouGov survey 72% of US users
  view AI content negatively; YouTube's July 2025 "inauthentic content"
  policy demonetises mass-produced slideshows; in early 2026 it removed
  sixteen AI-slop channels (4.7B views). Human-drawn channels sell the
  difference (History with Dave titles every video "(NO AI)").
- *"that going to sleep niche ... I put this on, turn my phone over, so I'm
  not even watching the screen and I'm just like listening."* The channels
  there ("Boring History For Sleep", "History for Sleep") run 1:50–2:50
  films; "What Did Early Humans ACTUALLY Do All Day?" sits at 2.6M views,
  "Why You Wouldn't Last a Day in Medieval Times" at 4.3M. Nearly all of
  them are AI painting slideshows.
- *"we do like one video like a week."*
- The art: the cartoon look of History with Dave and Deep Epoch — round
  white heads, ink outlines, flat colour — *"it's what I've shown you."*
- The voice is a separate conversation (he will bring ElevenLabs); until
  then Kokoro `bm_george`, slowed, with breaths between sentences.

## The pieces

| file | job |
|---|---|
| `data_learning/doodle/` | the art kit: `ink` (marker line, flat fill, shadow side, grain), `people` (the rig: poses, actions, moods, items), `props`, `settings` (sky, land, weather, water), `scene` (validate, lay out, render) |
| `data_learning/ori_episodes/<slug>.json` | one episode script — the queue. `ori_sleep.validate()` is the contract; every narrated beat carries the scene drawn under it |
| `data_learning/ori.config.json` | the topic bank (each with its era), queue minimum, the technical floor |
| `scripts/ori_author.py` | writes a script as an outline then one call per chapter, each checked against the kit's own vocabulary (`scene.vocabulary`), one retry with the reasons, dropped if still broken |
| `data_learning/ori_sleep.py` | script → narration timed per sentence → scenes drawn in parallel chunks with dissolves → sleep bed → mp4 + thumbnail + chapters + captions |
| `scripts/post_ori.py` | kill switch → reconcile → render → floor → **showrunner** → leak scan → claim → upload → receipt → `state/curiosity_posted_log.json` |

## Motion is measured, never faked

The showrunner's cadence probe reads a held frame as a duplicate, and the
operator ruled out every trick that makes a still picture shiver
(`shared/camera_float.py`: no camera drift, no bob, no breathing crop). A
sleep film is calm, so it earns its motion honestly: **every scene must
contain something that really moves**, and `doodle.scene.validate` refuses
one that does not. The strengths in `_fire_strength` / `motion_strength`
are numbers measured with the REAL probe (encoded 4-second clips through
`showrunner_review._temporal_evidence`): a campfire at night in a close shot
holds 4% of frames, the same fire at noon is a small orange shape on bright
grass and does not count; water, rain, a hearth and a candle count; a torch
and a wide-shot fire are helpers. `tests/test_ori_sleep.py` re-measures the
staples and a random sample of accepted scenes every run.

What actually moves: flames whose tongues take a new height twelve times a
second (linear, because eased noise goes flat at every knot and two frames
on a flat spot are two identical frames), embers rising, firelight that
flickers across ground and faces and never clips to white, sun and moon
glints winking on the water, rain, animals grazing, people doing their work.

## The picture has to be readable (the first film's verdict, 2026-09-23)

The first CI run rendered the whole film and the showrunner passed it at 74
with the notes a good editor would write: *"sleepers are drawn lying in the
fire with a plank through their heads"*, a spear tip across a seated
watcher's face, one cave-and-fire template for most of the film, no dawn in
"Toward Morning". Every one is now a rule with a test
(`tests/test_ori_sleep.py::ThePictureIsReadable`):

- **Everything on the ground has its real width.** `scene.figure_extent`
  reads the rig (a sleeper is five heads long, a sitter's legs reach two
  heads forward); `layout` keeps every figure and every mid/front prop clear
  of every other, sliding a thing away from the fire until it fits and
  drawing a shot that cannot fit at its natural size a little smaller
  (`SHRINK`) rather than overlapped. `layout()["collisions"]` names what
  still touches; every scene of every episode on the shelf must say `[]`.
- A bedroll goes under its sleeper, sized to them, symmetric (the folded
  corner was the plank); a cook's pot sits between their knees. Both are the
  overlaps that are meant, and the checker knows them by `under`.
- A held spear rests its butt on the ground and leans away from the body.
- Sewing shows a hide over the knees; knapping shows the core and its flakes.
- The author refuses a chapter where more than half the beats are one
  setting and shot (`ori_author.SAME_LOOK_SHARE`), where two beats in a
  row are the same picture, or where one picture would pass three in ten
  of the whole film so far (`FILM_LOOK_SHARE` — each chapter's prompt
  carries the running tally and how many more it may use), and the last chapter's outdoor scenes are asked
  for at dawn — a campfire at dawn in a close shot measured 0.06-0.10 held
  frames, alive; in a wide shot 0.52-0.63, not.

The second film (same day) was BLOCKED at 74 for `junk_imagery`: the
curled wolf's head bump, ear and tail read as "an animal upside down with
its legs in the air", figures were cropped at the frame edge (a mammoth at
the 6% slot), the cold chapter showed nothing cold, and the children's game
and the fire-feeding the words describe were drawn as idle sitting. So:

- The wolf is a round body that breathes, head on its paws, ears laid back,
  a closed eye, tail tucked.
- **Nothing is cut by the frame edge** (`scene.EDGE`): a span outside the
  safe margin is a collision like any other, so the same slide-and-shrink
  loop keeps it in frame; back-layer props only take slots they fit in.
- Two more actions, `play` (a stick swung with both hands) and `feed_fire`
  (a branch pushed toward the flames), a bent pointing arm, arms crossed
  for `hug_self`, and a `frost` weather (pale ground, white-edged tufts,
  stars still out).

The third film (same day, BLOCKED at 74): cave paintings drawn in the open
sky (a painting prop in an outdoor setting), a carried bundle crossing a
seated head, a mammoth's tusk in the fire, a sleeper's hide touching the
fire's stones, a cloud behind the title. So:

- A prop may be tied to settings (`Prop.settings`); `cave_painting` only
  exists in `cave_inside`, refused by name anywhere else.
- A figure's extent includes what it reaches for or holds
  (`scene.ACTION_REACH`, `ITEM_REACH`): a pointing arm, a fishing rod, a
  spear, a bundle. A bundle is carried at the waist in both arms.
- Back-layer props with a body (`SOLID_BACK`: animals, a hide rack, a
  torch post, a hut) take room like anything else; trees and tents stay
  scenery.
- The fire's footprint includes its stones; a sleeper's extent its fur.
- The opening title sits on a soft dark band.
- The cave mouth has the range behind it only half the time.
- The CI persist step, losing a push race, restored its stale copy of a
  listed directory it had not written over an episode edit that had landed
  since (`scripts/ci_commit_state.sh`); it restores only what the run
  changed now, with a real-git test.

The fourth film (70, BLOCKED): a tree canopy sitting on a standing man's
head, the cave-fire-seated-figure template in six chapters, chapters whose
frames did not show their words, beards read as a black wedge across the
face, a cloud through the title. So:

- Scenery with a trunk (`Prop.solid_width`) takes room for the trunk, so
  nobody stands under a canopy's centre.
- The focal fire sits between 38% and 62% of the width by seed, not dead
  centre every time; the author caps one picture at a fifth of the film
  and one SETTING, whatever the shot, at a quarter (`FILM_PLACE_SHARE`).
- A beard sits under the chin a shade lighter than the hair; the darkest
  hair is dark brown, not black; the telling gesture rises to the shoulder.
- The title band is opaque enough that a cloud cannot cross the words.

## The storyboard is looked at before the render (`data_learning/ori_storyboard.py`)

His words, the morning after: *"it needs to be getting consistent 90s ...
don't make a great video and then ruin it because of the judge ... you
don't want to be like, oh, well, this hasn't been passing the judge, I'm
just going to make the judge easier."* The 90+ verdicts in the ledger all
have `craft 3` and `data_demo 5`; the sleep films sat at `craft 1`,
`data_demo 3` — picture defects and pictures that do not show their words.
Every one was learned after a two-hour render.

So the same brain looks at the STORYBOARD first: every scene as a still,
nine to a sheet with its passage, marked BROKEN or not and SHOWS THE WORDS
0-2. Repairs are small and deterministic, escalating by round — another
layout (`variant`), one prop fewer, another place — and a scene that does
not show its passage gets one author call to re-specify it under the kit's
vocabulary, kept only if it validates. Changed beats are looked at again,
up to three rounds. A clean board is stamped with the kit's hash and not
reviewed again until the kit changes; a judge that cannot look never blocks
the film. The ledger is `state/ori_storyboard.jsonl`. The showrunner's
verdict on the finished film is unchanged — this only moves defects to
where fixing them is cheap.

### The fifth film's notes (78, SHIP — the first pass), and what moved

The first film through the storyboard shipped at 78 with no auto-fails
and `craft 2`. Its notes were smaller than the earlier films' and every
one is a picture rule now, not a judge rule:

- *"dark hair and a beard against the black of the cave mouth — a
  floating white mask."* The opening is ground the setting owns:
  `settings.cave_opening(seed)` is a pure function, so the layout — which
  runs before the still is painted — keeps every person's HEAD column off
  it. A fire, a curled wolf, an arm or a pot in front of it still reads,
  so those may stand there (`blocked` in the layout; `ground` spans in the
  collision check). Three cuts were measured on the shelf's 141 scenes: the
  whole opening taken from everything cost thirty-eight scenes their
  layout; people's whole spans kept off it, none of the layouts but six
  of the natural sizes; heads only, with the fire allowed to move a
  little before anyone is drawn smaller (`FOCAL_SHIFTS`), zero
  collisions and fewer shrunk scenes than before the rule. A cook's span
  includes the pot placed beyond her, which is what kept putting her pot
  outside the frame.
- *"the sky chapter does not show anyone looking up."* It did — every
  figure in it did `look_up`, which was two dots moved a finger's width.
  Looking up is a whole-body thing now: the head tips up and back
  (`people.head_of`), the face and its open mouth go to the top of the
  head, and a hand goes to the brow, the way anyone looks at something far
  and high. It reads from across the room.
- *"a blocky mammoth by the fire."* The body was a blob on four boxes.
  It has a high domed hump over the shoulders, a back that slopes to the
  rump and a shaggy fringe hanging along the belly now — and the layout
  had been cutting it by the frame at every size, because a 1,000 px back
  prop placed AFTER the people had nowhere left to go, and `settle` gave
  up on the spot whose first try hung off the left edge instead of walking
  in. Solid scenery is placed before the people (`place_prop`, `early`)
  and a slide only stops at the edge it is walking toward.
- The rebalanced script (35 cave-mouth scenes of 141, argued down from 57)
  was put BACK by the run's own persist: the storyboard had stamped the
  old copy in a run that checked out three hours earlier, and on the push
  race `ci_commit_state.sh` restored the run's copy over the branch's.
  A file changed on both sides with no merge rule keeps the branch's copy
  now, and says so in the log; the ledgers beside it are still unioned
  (`tests/test_ci_persist_merges_the_library.py`).

### The sixth film (83, SHIP): scale, and the cold

Round four's film scored 83 with `hook 4` and no auto-fails. Its notes:
*"figure scale is inconsistent: a man about as tall as the trees, a woman
filling the cave mouth next to a small child"*, *"no visible cold"*, the
children's game and the sky chapter (the last already fixed above).

- **A close shot brings the WORLD nearer, not only the people.** The
  people were drawn at 2.05 and the setting at one size for every shot, so
  in a close shot the tree line came to a seated woman's shoulder and a
  standing woman overtopped the cave. `draw_still` takes the shot now: the
  cave mouth grows by `CLOSE_WORLD`, the tree line by `CLOSE_TREES` (fewer,
  bigger trees), and a tree placed as a prop stands about twice a figure
  (`scene.SCENERY_K`; a hut or a mammoth keeps its size).
- **Cold you can see.** In frost or snow every waking figure breathes out a
  puff every few seconds (`people._breath`).
- **A new chapter opens on a new place.** The judge samples each chapter's
  first, middle and last frame; two chapters opened where the last had
  closed, and *"the cave-fire template recurs in over half the sampled
  frames, so chapters blur together"*. `_chapter_problems` refuses a
  chapter whose first beat is set where the previous chapter's last beat
  was; the shelf's two offenders moved (the night watch to the riverbank,
  the old man's chapter to the cave mouth, his back to the rock).

### The seventh film (74, BLOCK): one composition, and what could stand in the cave

The first film with faces off the opening, the point-up and the mammoth
came back LOWER, with a `junk_imagery` auto-fail: *"the same cave-mouth +
campfire + seated-figure picture repeats back to back ... the stock layout
for about 16 of 42 samples"*, plus a tipi drawn inside the cave mouth, the
wolf there as *"an unclear grey blob"*, the mammoth's trunk over a tent, a
torch flame inside a tree canopy, and the sky chapter still not reading.
The judge is noisy — 83 and 74 on the same script a run apart — but every
note names a real thing, so every note moved the film, not the judge:

- **Only a light may stand in the mouth of the cave.** A fire reads there;
  a tent, a woodpile or a wolf is a shape against black. Small props (under
  `SMALL_PROP`) and anything under its sleeper (the bed, and the wolf, which
  now curls beside the sleeper instead of finding its own spot) are exempt.
  The fire may travel further (`FOCAL_SHIFTS` to ±0.24) before anyone is
  drawn smaller: 141 scenes, zero collisions, 12 shrunk (was 20).
- **The fire ranges over the middle half of the frame**, not the middle
  quarter, so two fire scenes are less often the same picture.
- **The torch stands among the people** (mid layer): on the back line its
  flame sat inside the tree canopies. A carried torch is held out in front
  and above the head, like the spear, never across the face.
- **The mammoth is as wide as its trunk** (720).
- **Looking up, fourth try.** Two dots moved a finger's width (5th film),
  then a hand at the brow (7th: still "no one looks up"). A round head is
  taller than a natural arm, so an arm straight up crossed the face and one
  raised behind vanished behind the head. Now: the head tips well back, the
  face and open mouth go to the crown, and the front arm — stretched, drawn
  UNDER the head so it rises from behind the shoulder — points at the sky
  with the hand clear above the crown. Lying down, the figure is on its back
  with its face to the sky and an arm raised at it (`people._face_up`),
  which is the judge's own picture for a sky chapter.

## Any topic: the era is found or the refusal is honest

`ori_author.era_for` reads a topic's words against `ERA_WORDS` (no model);
a topic naming none of them is put to the brain, which may answer only
with an era the kit draws; a topic naming two eras at once is a question,
not a count. A topic the kit cannot draw is refused by name ("the kit has
no era for ... — add the era's settings and props first, or pass --era"),
never quietly drawn in the wrong world. Growing what the system can take
means growing the kit: an era is an `OUTFIT`, settings, props and measured
strengths, and `ERA_WORDS` for the words that name it.

## What the probes needed

The probes used to hold every sampled frame in Python lists; a two-hour film
is 172,800 frames and the runner ran out of memory, which the gate would
have read as an unmeasured probe and held forever. They stream now
(`_gray_stream`, `_max_block_diff_np`) and
`tests/test_showrunner_probe_stream.py` holds the old code verbatim as the
oracle: same answers, no memory.

## Rules the tests hold (`tests/test_ori_sleep.py`)

- Every name the validator accepts draws; every name it refuses is refused
  by name; another era's props are refused; a still scene is refused.
- 11,000–22,000 narrated words, 8–20 chapters (the author aims at 14–16 chapters of 1,000–1,400 words, about two hours), 20–190 words a beat; the
  thumbnail is a close doodle scene with 2–4 words.
- A short episode renders end to end with a stand-in voice: video, audio,
  captions, chapters, a 1920x1080 thumbnail.
- The author drops an episode whose chapter stays broken after one retry.
- The gate runs before the upload, knows it is a publish run, and a BLOCK
  never reaches the uploader. A claim is written before the upload and a
  receipt after, so a crash in between is reconciled, never guessed.

## What is deliberately left

- The registry entry for `curiosity` still describes the retired pro queue
  and stays `enabled: false`, so Phase A/B, the daily alarm and ChatGPT's
  stocking job do not start supervising this channel. The sleep path is in
  `ON_BUT_GATED` (`tests/test_disabled_channels_stay_off.py`), like long-form.
- The stock-footage documentary renderer is gone (2026-09-23), with its
  three scripts. Its lesson lives in `post_ori.py`'s judge context: the
  judge is told what each chapter says so it can check the picture.
- Three eras are drawn (`stone_age`, `medieval`, `ancient` — the Roman and
  Greek Mediterranean: tunics, a forum with a colonnade and a town behind,
  a villa interior with a painted dado, an olive grove, a temple, a villa,
  columns, amphorae, a brazier and an oil lamp, a market stall, goats); a
  topic outside them waits for its settings and props to be added to the
  kit, with the tests that say they resolve and move. Adding an era is
  data plus drawings: `OUTFIT`, `Setting.eras`, `Prop.eras`, and a measured
  strength for each new living light (brazier: night close 0.18, night wide
  0.32, day close 0.37, day wide 0.59; oil lamp 0.26-0.28 everywhere).
- A fourth era, `victorian` (the 19th century): dark coats and long
  dresses with a cap or a bonnet, a gas-lit terrace street on cobbles, a
  papered parlour, a farmyard with a barn; props: a terrace, a barn, a gas
  lamp, an iron range, a chair, a bookshelf, a long-case clock with a
  swinging pendulum, a horse-drawn cab, a chimney wall. Measured: the range
  0.04 close / 0.23 wide (carries a room); a gas lamp 0.53 alone, 0.19
  with someone walking under it, 0.17 with a held lantern, 0.33 in falling
  snow (a helper: something has to move in its light); a walker on an
  unlit street at night is a black frame (1.0); falling snow alone is
  below the probe's notice (1.0) and a helper with a lamp.
- A fifth era, `egypt` (the Nile valley): white linen with a broad collar,
  black hair, a kilt or a straight dress; the Nile bank with palms, the
  desert with dunes and the pyramids on the skyline, a whitewashed mud-brick
  room with a painted band; a pyramid (desert only), palms, an obelisk, a
  water jar, a papyrus skiff, a mud-brick house, a basket of dates; the
  brazier, oil lamp, stall and goat are shared with the Mediterranean.
  Measured: the Nile follows the river table (0.88 by day, 0.28 at dusk);
  a desert campfire at night 0.00; a lamp in a mud-brick room 0.26.
- A sixth era, `early_modern` (1500-1750): wool coats and doublets in deep
  colours, a tricorn or a coif; a harbour on a stone quay with a ship at
  anchor across the water, a beamed tavern with a leaded window and a
  shelf of tankards, a half-timbered market square (shared with the
  Middle Ages); a ship (harbour and seashore only, a lantern at its
  stern), a timber house, crates, a mooring post; the stall, barn, hearth,
  cottage and wheat are shared. The sea and hearth tables already cover
  its light.
- Fog is measured too: a river under fog holds 0.20 at night and 0.97 by
  day, a cauldron 0.06 clear and 0.34 in fog — so water counts only at
  night in fog and a cauldron drops a step.
- Back props in a water setting stand on the far shore (across the bay for
  the sea), never in the water; a small light stands on a table when there
  is one.
