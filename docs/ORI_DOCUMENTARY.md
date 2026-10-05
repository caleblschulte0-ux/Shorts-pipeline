# OpenRangeInteractive — the sleep films

**What ships:** once a week (`curiosity.yml`, Friday 19:00 UTC, plus
`clock.yml` re-firing a missed slot), one **20-30 minute** 1920x1080 history
story to fall asleep to (the operator, 2026-09-24, on the 114-minute
medieval film: *"114 Mins is to long shoot for like 20-30 mins"*; it was
two hours until then), drawn entirely by code in a hand-drawn cartoon
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

- **The storyboard is strict about the words now.** Across three films the
  storyboard editor never once graded a scene 0 on showing its words, and
  1 ("right place, activity not shown") never triggered anything — while
  the film's judge said chapter after chapter "never shows the activity the
  narration describes". A scene graded 1 is re-specified now too
  (`SHOWS_MIN`), the prompt asks whether a viewer who had not heard the
  words could guess the activity, the respec is told the chapter and the
  actions that show things, and the author calls are capped
  (`MAX_RESPECS`) so a strict editor cannot cost a render slot.

- **Two scenes at a fire are not the same arrangement.** The standing-spot
  sets are tried in a seed-chosen order and two of them put everyone on one
  side of the fire; the shelf went from 12 shrunk scenes to 7 on the way. A
  storyboard respec is also held to the author's picture rules: one that
  copies its neighbour's picture is refused and the small repair happens.

- **A clear night in the open may show the Milky Way** (`settings._milky_way`,
  half the time by seed, `OPEN_SKY` settings only): a soft band of haze and
  four hundred faint stars across the sky. The judge asked for "a dense
  starfield or Milky Way" under the sky chapter; it is also what a night
  away from any town looks like, and it tells one open-sky night from the
  next.

### The eighth film (70, SHIP, craft 1): the board found the cost of the nearer world

Run #9 carried the nearer world and the tree line, and its storyboard
flagged ten scenes in round one: a prop tree's canopy cut off by the top
edge (2.77 was too tall), a torch flame "at the top of the pine" and a fire
"floating in the pine" (the flame at canopy height, and a snow peak read
as a pine), a tree trunk through a tent, a tent behind a fire read as a
fire in the tent, a beard read as "a brown prop across the face", a fire
"on top of the river". Every one is a rule now:

- **The tree line is data** (`settings.tree_line`, a pure function of
  setting, seed and shot), drawn by the still and read by the layout: a
  back prop or a tall one keeps off the trunks and canopies (`TREE_KEEP`).
- **A prop tree stays inside the frame** (`TREE_TALL`, `TOP_ROOM`); the
  torch is shorter (200) so its flame sits below the canopies and peaks;
  the tent is a structure (`SOLID_BACK`) that nothing stands in front of.
- **The beard is a fringe along the jaw**, not a wedge under the chin; a
  carried load rides at the waist.
- **The water band sits back from the bank** (`WATER_BAND`), and the
  current is brisker and brighter with more glints: measured with the
  gate's probe the moved band had split the ripples across two block rows
  and a night river fell to 0.46 duplicate frames; it is 0.00 now, at dusk
  and by day too.
- **A round-three repair never copies a neighbour's place**, and the
  Milky Way is soft haze rather than a stroked bar.

- **A crowded scene goes back to the author.** `_chapter_problems` runs
  the layout (fast, deterministic) and refuses a beat the layout can only
  fit by drawing everyone under `CROWD_SHRINK` of natural size — "a
  sleeper's head right next to the fire's base at the tiny render size" is
  a scene with too much in it, not a drawing defect. The shelf's one such
  beat moved to the forest.

- **A chapter moves, and no one place owns the judged moments.** The judge
  looks at a quarter, 55% and 85% of every chapter. `_mark_beats` finds the
  beat playing at each (by words, which is screen time); a chapter whose
  three are in one place is refused, and across the film no setting may
  hold more than `MARK_SHARE` of those moments. Measured on the shelf
  before the rule: the cave mouth stood at the half-mark of nine chapters
  in fourteen, 16 of 42 judged moments — exactly the judge's count. Five
  beats moved (an old man looking up at the first star went under the
  mountains' open sky) and three crowded wide cave scenes lost a rack or a
  tent; the beat whose words say "the mouth of a wide, shallow cave" stayed.

### A system, not a video (2026-09-24)

His words, after the ninth run: *"remember we're making a system that makes
good videos not making one good video."* Everything above that had landed
as a hand edit to the shelf's one script — a beat moved to the mountains, a
rack dropped from a crowded wide — was one-video work, and a rule that lives
only as a hand edit is not a rule. So:

- **`ori_author.repair_film`** holds a whole script to the picture rules,
  deterministically: a chapter standing in one place at its three judged
  moments, one place owning too many of those moments, a scene too crowded
  for its shot, neighbours that are the same picture. Each fix is the
  smallest change that lowers the problem count — drop inessential props
  from the last while each drop fits better, widen the shot (lighting a
  torch if a wide night needs it), or move one beat to the least-used
  nearby place — and a beat whose words name its place (`SETTING_WORDS`) is
  never moved. It runs on every script the author writes and again in
  `post_ori` before the storyboard. Replayed on the run-#9 script it makes
  the same eight changes the hand had made, and leaves the one whose words
  pin it, saying so.
- **The proof is a second topic.** `curiosity.yml` takes `author_topic`
  (and `author_era`): the run authors a fresh script, repairs it, boards it,
  renders it and judges it — the whole system on a topic nobody polished.

- **The first fresh-topic run failed at the author**, not the judge:
  chapter 1 of "What did medieval peasants do after dark?" was rejected
  twice for *"nothing in this scene moves enough"* and the author gave up.
  A motion rule handed back to a brain twice is not a system. `mend_scene`
  fixes what code can fix before the brain is asked again: the plainest
  light the setting and era allow (one, then two — a wide night needs a fire
  and a torch; a hearth is never lit outdoors), a prop the kit does not
  know dropped, the shot brought close. Three attempts instead of two, and
  the brain sees only what is left. The hook subtitle is bigger and white.

- **Actions the judge can name from the picture** (run #10, 78: "the game
  is never shown", "the knapping is never shown", "held sticks rise out of
  heads like antennae", "a bowl covers the man's face"). The knapper's
  hammerstone rises to the shoulder and comes down on a bigger core with a
  flake in the air on each strike; a child at play swings the stick between
  chest and knee and tosses a pale pebble up and catches it; a held stick is
  a staff from the hand to the ground; food comes to the front of the chin,
  never over the mouth; and the look-up keeps its hands down — every raised
  arm tried (straight up, behind, at the brow, stretched past the crown)
  read as something else — so the tipped head and open mouth say it, and a
  figure lying on its back says it best. The storyboard editor is asked to
  NAME the missing activity when it grades a scene under 2, so the respec
  has something to aim at.

- **The second fresh-topic run failed at chapter 2** — three attempts on a
  held `candle` the kit does not draw, a crowded scene, and the cottage at
  all three judged moments. Every one is deterministic: `mend_scene` puts
  down what cannot be held and fixes a pose or mood the kit does not know;
  `uncrowd_scene` (shared with `repair_film`) drops props while each drop
  fits better and widens with a torch; and `repair_film` now runs on each
  chapter as it is written, with the earlier chapters as context, so the
  film-level rules are repaired in code before the brain is asked again.
  A chapter with all three faults costs one brain call in the test.

- **The third fresh-topic run failed at chapter 3**, and the log lied about
  why: four wide shots "drawn at 60% size" and two same-picture pairs, all
  written off as *"the words pin those beats"*. A prop drop, a person drop
  or a shot change touches no word. `uncrowd_scene` drops the last props
  from a cast of four now (the rule's own words: "drop a prop or a
  person"), and counts FEWER collisions as progress — a close shot holding
  two houses and a cow needed three drops and the first two fixed nothing
  alone, so the greedy pass stopped at the first. `repair_film` has a shot
  flip (`try_shot`, with the wide night's second light) for a pair whose
  words pin the place, because the rule itself says "change the setting OR
  the shot". Measured over 400 random medieval scenes: 7 left crowded
  before, none after. And the "could not fix" line names the true reason.

- **The fourth fresh-topic run reached chapter 13 of 14 and hit the
  author step's sixty-minute clock.** Fourteen chapters at four to six
  minutes a brain call never fit in sixty; the step has 120 now. The
  retries it spent are code too: `mend_idle` gives an idle cast the action
  its words describe (`ACTION_WORDS`: sew, eat, play, feed_fire, look_up...;
  a fire says warm_hands, two people say talk) until the idle share holds;
  a daylight scene no fire can light goes to dusk, then night, and tries
  again; a chapter that opens where the last one closed, its own words
  pinning the place, moves the previous chapter's last beat instead; and
  `uncrowd_scene` measures "fits better" on a gradient — the layout draws
  in steps (100, 92, 84, 76%), so two drops that each leave a wide at 76%
  and together reach 92% looked like no progress one at a time, which is
  what left a beat-1 wide at 76% three chapters running. The ground the
  scene occupies is the second measure, and a place the brain pinned
  (`at`) is let go before anything is dropped.

- **The fifth fresh-topic run authored (49 minutes, the first ever) and
  then could not finish rendering.** The outline prompt said "14-16
  chapters" and each chapter was asked for 1,000-1,400 words — up to 2h50
  of narration — and the brain wrote 16 chapters, 190 beats, 19,611 words:
  a 149-minute film. Measured in that run: storyboard 34 min (3 rounds, 376
  repairs on 190 beats), narration 62 min in one process, and the drawing
  still going at the step's 230-minute clock. No verdict, no film. Three
  rules came out of it, all code: the film is sized to the slot BEFORE a
  chapter is written (`TARGET_WORDS` 14,500 at the measured 131 words a
  minute, 10-13 chapters, per-chapter bounds derived from the count with a
  hard cap that keeps the total under `MAX_WORDS`, now 16,000 ≈ 2h02);
  the narration is spoken in a process pool a chapter at a time and written
  in order; and the storyboard polish has a 45-minute wall clock beside its
  call count. The 190-beat script came off the shelf — the weekly cron
  would otherwise have picked a film that cannot finish.

- **The sixth fresh-topic run rendered in the slot and was BLOCKED by the
  code gate at 11:36** (run #16: 13 chapters, 157 beats, 114 min; storyboard
  27 min, narration 44, drawing 88; score 9 = the pre-gate, the vision judge
  never asked). 43 seconds frozen on a daylight close shot of a woman
  gathering wood with a child walking beside her — a scene the motion
  table called alive because somebody was walking. Measured against the
  gate's OWN detector with the real probe: a walker swings its legs on the
  spot and at a child's size in a close shot every frame is a duplicate
  (0.75-1.0, run 96); chop 0.14/5 and wave 0.18/4 pass; eat 0.78/44, yawn
  0.62/60 and stir 0.93/49 sit at the 45-frame ceiling. So in daylight only
  chopping and waving count (hoe +1), and `mend_scene` takes such a scene to
  dusk with a fire, which measures 0.0. The storyboard editor still flagged
  106 of 157 after three rounds, and its notes became code too: whoever
  feeds, warms or stirs is placed BESIDE the fire (measured before: a woman
  warming her hands 6-15 heads from the hearth while an idle child stood
  one head away) and the cast keeps its order; a beat moved outdoors leaves
  its hearth, bed and table behind (`take_outdoors`: hearth -> campfire, a
  candle -> a torch), and a brain-written hearth in a field is mended the
  same way; the axe and the hoe clear the face through the whole swing
  (a test holds the gap at 0.1 R; it was -0.06 R and -0.79 R).
  Closer to the fire is never smaller: at each size the adjacent
  arrangement is tried first and the plain slots second, so the cook keeps
  her natural size. And `mend_film` — every scene mend, the crowd, the idle,
  then the film rules — runs on every script before it is rendered, so a
  script written under yesterday's rules is brought to today's in code:
  the medieval script took 18 such repairs, the stone-age one none.

- **20-30 minutes, not two hours** (his words, 2026-09-24 evening, on the
  114-minute film: *"114 Mins is to long shoot for like 20-30 mins"*).
  `TARGET_WORDS` 3,300 (~25 min at the measured pace), 4-6 chapters,
  `MIN_WORDS`/`MAX_WORDS` 2,400-4,000, 3-8 chapters at the renderer. The
  Roman run in flight (a 114-minute film) was cancelled and redispatched at
  the new length; the two two-hour scripts left the shelf. The whole loop
  is a quarter the size now: a run should author in ~20 min, board in a
  few, narrate in ~10, draw in ~20 and judge inside the hour.

- **Run #18 (the first 25-minute film, "What did ordinary Romans do after
  dark?"): 66, BLOCK — the first full vision verdict on a fresh topic.**
  The whole loop took 1h29 (author 19 min, storyboard 22, narration and
  drawing ~35, judge ~10). The auto-fail was junk imagery, and every
  instance was WORDS AND PICTURE DIVERGING: "the supper chapter opens on a
  beach" for *the household gathers under one low roof*, a Roman street in
  an olive grove, the watchman crossing "an open grass field", "the finale
  is an empty sunset shore instead of Rome falling asleep". The repair and
  the storyboard had been moving beats to "nearby" landscapes to satisfy
  picture caps with no regard for what the words describe. So, as code:
  - **The words decide the place** (`place_class`, `PLACE_WORDS`,
    `PLACE_SETTINGS`): a passage names a class of place — indoors, the
    city, the river, the lake, the sea, the grove, the forest, the
    mountains, the snow, the farm, the cave, the desert — and its beat is
    held to the era's settings for that class (a rule in
    `_chapter_problems`, a mend in `mend_place`, and every move in
    `repair_film` and the storyboard's `_next_setting`/`respec` stays
    inside the class). Exact word forms only: a prefix match made
    "village" an interior through "villa"; "city" and "town" are the
    film's topic, not the shot's place; a tie goes to whichever the text
    names first (*around a plain table ... bread, olives* is at the
    table). A beat the words place does not count against the film-wide
    place caps — a Roman film whose only city is the forum cannot "take
    the rest elsewhere" — and inside a class with several settings a
    balance rule alternates them. A beat with no place words keeps its
    kind of place, and between two indoor beats it stays indoors.
  - **The film ends in the dark**: the last third of the last chapter is
    night (the prompt asked for dawn; the judge saw it "brighten back to
    sunset").
  - **A campfire does not burn in a built room** (`validate`; a cave or
    hut floor keeps its fire, `EARTH_FLOORS`), and one written into a
    villa or cottage becomes the era's hearth or brazier (`bring_indoors`);
    a square is lit by torches and braziers, not "a campfire in the road".
  - **The doorway shows the night at night** (`settings._outside`) and
    the water's glints go under whoever stands on the bank.
  Replayed on the Roman script, the mend moved 45 beats to where their
  words put them and then settled (a second pass changes nothing).
  Not built, named by the judge: a bakery with a domed oven, a door with
  a bar, a jug, a tray — the kit has no such props, and the storyboard
  editor's "no X visible" notes are mostly these.

- **Run #19 (Victorian London, 65) and run #21 (the same script re-rendered,
  the first film narrated by ElevenLabs, 65 again).** The same notes twice:
  cows in a terrace street, mountains behind a London lake, a forest
  campfire in the parlour chapter, a bonfire for the playhouse crowd, a
  lamplighter in open countryside. The second time explained the first:
  the storyboard rewrote 55 scenes AFTER `mend_film` and put the mended
  mistakes back — a place-less beat re-specified onto a farmyard (the cows
  came with it), two street campfires, a cottage in a street, a doubled gas
  lamp. So `post_ori` runs `mend_film` again after the storyboard; a film
  has a HOME (`film_home`, its two most-named classes of place) and a beat
  whose words name no place stays in it (`mend_home`, and `repair_film`'s
  moves prefer it to open landscapes); rural buildings leave city streets
  and a prop listed twice is drawn once (`drop_out_of_place`); animals stay
  only where the words name them (a drover's cattle stay); a room's fire
  moved into a street becomes the era's street light; and a Victorian or
  early-modern lake or river has a skyline behind it, not an alpine range
  (`settings.CITY_ERAS`). Place words gained the lamplighter, the
  constable, the playhouse, gaslight, the Nile, the Thames and "water";
  "lamp" left the room and "boat" left the sea.
  Run #20 (Egypt) never rendered: a new balance rule fought the Nile
  passages' own words for three attempts (it now skips word-pinned beats
  and waits for six), and a 900-word first chapter was refused in a film
  with room for it (the chapter bounds now run on the film's remaining
  budget). NOT BUILT, named by the judge: a lamplighter's pole reaching a
  lamp, a playhouse front, a constable's helmet.

- **Run #22 (Egypt, a fresh topic end to end, 74, BLOCK; 24.0 minutes,
  narrated by ElevenLabs).** The first film inside the 20-30 minute ruling,
  and the judge called it "calm, consistent ... a good opening and ending".
  Blocked because the chapter titled "Watching the Stars" was indoors at
  its judged moments. The words-decide-place rule could not see it: "star",
  "sky" and "moon" named no class of place, and the chapter's marks were
  computed by beat count while the judge samples by TIME. So there is a
  `sky` class, and it may be drawn at any outdoor place, because it keeps
  the stars out of rooms rather than choosing a landscape. A chapter whose
  TITLE names a place must show it at two of its three judged moments.
  Those moments are checked against every beat playing near them
  (`_mark_windows`), because the voice's pace is only an estimate and the
  judge's 85% frame was the beat after the one the rule computed. The
  lying stargazer lost its raised arm (read as "a stick from the head",
  like every raised arm before it). The Egyptian dog is its own drawing:
  warm coat, ears up, pale muzzle. The storyboard had called the grey
  wolf-shaped one "flat and dark and reads as dead". Also named, not yet
  built: keep the first chapter outdoors until the lamp chapter begins.
  Run #23 (Elizabethan London, a fresh topic) never rendered, and the
  fault was that title rule. "The Bell That Shut the Gates" read as a city
  title, so the brain was told three times to stand in a market square
  while its words were on the Thames and in a tavern, and the film was
  dropped. The rule is now about the SIDE OF THE DOOR, which is the
  contradiction the judge saw: a sky, river or forest title promises
  outdoors, a room title promises indoors, and a city or cave title
  promises neither (a tavern is a city word; a cave has an inside).
  Place-less beats at the judged moments are moved in code (`mend_title`,
  run inside `repair_film`, which now also scores the rule so it never
  undoes the move). Only words that pin a beat to the wrong side go back to
  the brain. The rule is also SOFT (`SOFT` in `_with_retry`): a last attempt
  whose only remaining problem is the title is kept, and says so in the log.
  It is a pre-check of what the judge might see, not a gate, and losing a
  whole film to it is worse than letting the judge judge.

- **Run #24 (Elizabethan London, the re-run, 74, BLOCK).** It rendered, and
  the notes were five. (1) The final chapter's harbour and riverside frames
  "contradict 'you watch the last candle pinched out'". That line is the
  chapter's OPENING, and the frames' own words said harbour and riverbank:
  the judge had only ever been given each chapter's first 180 characters,
  while its directive asks whether a scene shows what is said AT THAT
  MOMENT. The render now records the line spoken at each of the 18 frames
  the judge samples (`ori_sleep.judged_lines`, keyed by its own frame
  labels), and `post_ori` hands them over as `narration_at_frame`, with the
  showrunner's context budget raised for sleep films only so they are not
  cut. That is the judge's input made true, not its bar lowered; every rule
  and threshold is unchanged. This has probably been behind "the pictures
  do not match the words" in most runs since the first. (2) "The market
  square begins to empty" was drawn on the quay, because both are city
  places and the least-used one won. A setting the words NAME now wins
  within its class. (3) "Back at the tavern, the keeper banks the fire" was
  drawn in the street, because "tavern" and "inn" were city words; they
  are rooms (`tavern_inside`) now. (4) A watchman waved with his lantern
  over his face: a carried light (`people.LOW_HELD`) now stays at the side,
  and the gesture moves to the other hand. (5) NOT BUILT, named by the judge:
  a bellman's hand bell, a city gate being barred, market stalls being
  packed away.

- **Run #25 (medieval villagers, a fresh topic, 74, BLOCK): the first
  verdict with `narration_at_frame`.** The judge now quotes the line that
  is actually playing, and its notes are concrete and fair: every one is a
  picture that disagrees with its own words, which is what the rules are
  for. "Beyond the fields ... a lake lies flat" was drawn as a field: the
  words after beyond, past, behind or away from name where the scene is
  NOT. "In the farmyard" named no place, because exact-form matching did not
  know the word, so the cow went to a market square and floated there.
  `farmyard` is a farm word now. A market square whose words said "the
  stalls stand empty" had none: `add_named_props` adds one prop the words
  name when it fits (stall, barn, cart, table, bed, loom, woodpile). "The
  embers glow low beneath ash" was a roaring fire: a scene may say
  `"fire": "low"`, drawn as a banked bed of embers (`props.banked`), set
  from the words by `mend_fire`, and measured with the gate's own probe. It
  keeps full motion credit only indoors at a close shot (0.17 held frames),
  and elsewhere it is a helper (0.41 and 0.54). A crouched elder feeding
  the hearth read as "standing with a cane": `feed_fire` now holds a
  `branch` pushed forward and down into the fire with a glowing end,
  instead of a staff from hand to ground. NOT BUILT, named by the judge: a
  lord's hall set (stone walls, a long table, banners).

- **Run #26 (ancient Greeks) never rendered, for ONE WORD.** The film's
  running word budget counted with `split()` and the check with
  `OS._words`, which splits "well-worn" in two, so the assembled script came
  out at 4001 of 4000 and forty-five minutes of writing were thrown away. The
  budget now counts the way the check does, and `trim_to_length` cuts whole
  closing sentences from the longest middle beats of a film that is still a
  little over, rather than losing it.

- **Run #26 re-run (ancient Greeks, 74, BLOCK), and the operator's verdict:
  "3/10 AI slop ... they need to be more entertaining to watch."** The
  judge's 74 was not the measure that mattered; he watched it. The frames
  showed why. People were scattered across empty rooms, sat on nothing,
  and faced the camera. The Greek room was a red band smoothed into a curved
  "horizon", with an arch holding a blob. A Stone Age thatch hut stood in for
  a Greek home 17 times, and thatched huts stood on Greek riverbanks. One
  picture held for 35-55 seconds per passage. His direction (2026-10-01):
  "throw in some" real paintings, with the camera DEAD STILL (his standing
  ruling against camera movement holds, and paintings get drawn motion
  instead), and make what we have more entertaining. Done so far:
  - **Shots:** a passage longer than `SHOT_MAX` (16 s) is cut at its
    sentence breaks into up to three shots of the same place (the scene,
    the other shot size, a new arrangement), each checked valid and
    collision-free (`ori_sleep.shots`). The median hold fell from 25 s to
    14 s. The camera never moves; the picture changes.
  - **Rooms:** `villa_inside` was redrawn with straight edges (`ink.box`):
    a meander frieze, a stone doorframe onto the courtyard at this hour,
    and a niche with a jar. A plain Greek `house_inside` was added
    (whitewash, beams, a shuttered window, a shelf of pots). `hut_inside`
    and the `hut` prop are now Stone Age and medieval only. `mend_scene`
    moves a scene its era cannot draw into that era's own setting of the
    same class, so the shelf was brought over in code.
  - **People at a table:** anyone eating, drinking, talking or sewing is
    seated beside it, on a stool.
  - **Honest motion credit:** a candle counts fully only in a pale room
    (measured: 0.26 against 0.52-0.61 in the cave, hut, parlour and
    tavern).
  - **Mends that settle:** collisions at the render's own seed are fixed by
    another arrangement, not by dropping props; the named-prop mend runs
    last with a comfort margin; the room-balance rule now counts progress.
    A second `mend_film` pass over the shelf changes nothing.
  - **Voice:** ElevenLabs is OFF (`config/ELEVENLABS_OFF`) on his word.
    Kokoro narrates until he says otherwise.

- **The Greek film again, with the fixes above (78, BLOCK; Kokoro voice).**
  Up from 74. The judge: "A calm, consistent and beautifully paced sleep
  film, but the Men's Symposium chapter never shows a symposium, and several
  passages are drawn over the wrong place or activity." The Testa etching
  opened beat 8 of that chapter, which is none of its three judged moments.
  Named and not yet built: an andron (couches, reclining men, a krater), a
  banked brazier, beached boats with furled sails, a drawn stream, and a
  town behind the opening shore. The Met refused some searches from the CI
  runner (HTTP 403), so the Art Institute carried the paintings. Sent to the
  operator for his own verdict; his eye, not the judge's, is the bar.

- **The operator on that render: movement "a 5 out of 10 ... we need more
  movement per cut ... not forced movement, purposeful movement."** Counted
  in the Greek script: 15 of its 115 people "walked" on the spot for a whole
  passage, 12 carried things nowhere, 17 slept, and nothing in the world
  moved but water and flames. So:
  - **People go places.** Someone walking crosses the frame on a lane behind
    the others, walking in from beyond the edge at exactly the pace their
    feet carry them (`scene._walkers`, `walker_x`; no foot slides). They are
    no longer packed into a standing spot to march on it.
  - **The words decide who moves** (`ori_author.mend_motion`). When a
    passage says somebody walks, carries, crosses, passes, heads home or
    makes their way, and nobody on screen is moving, a standing figure sets
    off. Out of doors only, a passer-by with a torch (night) or basket
    (earlier) goes through instead. "Empty", "nobody" and "all asleep" move
    no one, and no stranger is walked through a room.
  - **The evening happens** (`settings._evening`). At dusk the town's lamps
    are lit one window at a time, at night they glow, smoke rises from the
    hearths where supper is on, and at dusk a flock goes home to roost
    across the sky. Each is a thing the evening is actually doing; none of
    it is a camera move or a wobble.

- **The Greek film with purposeful movement (78, BLOCK; Kokoro).** Same
  score; "shows the words" (data_demo) rose from 2 to 3, and the longest
  still stretch anywhere in the film is 1.0 s. Still wrong, from the judge
  and from looking at the frames: back props in sea and city scenes are
  placed on the horizon line, so a hay cart floats over the sea and a cart
  hangs over the forum colonnade; a brazier blazes where the words say
  embers (`mend_fire` covers the hearth and the campfire, not the brazier);
  a sunset after the moonlit chapters runs time backwards; and there are
  still no symposium couches, beached boats or stream. Sent to the operator
  for his verdict on the movement.

- **The operator on that one, 2026-10-02:** *"Pretty much all [it] is right
  now is just people moving their fucking arms ... If we're gonna have
  somebody walking, have the scene pan and have them actually walk across
  it for a second ... All of our scenes are too long ... they should be
  one, two sentences tops. You display the sentence that we're talking
  about, and then new scene ... a lot more motion. Shorter clips."*
  - **A shot a sentence** (`ori_sleep.shots`). A passage is cut at its
    sentence breaks, and a sentence over 8 s at a comma. Two sentences
    share a shot only when both are short. The Greek script went from 68
    pictures to 273 shots, median 6.2 s, longest 11 s.
  - **Each shot shows what its sentence is about** (`coverage`, `_choose`).
    The place when a passage opens somewhere new (never a wide room:
    small people on an empty wall), whoever is walking, the person the
    sentence names (she, the child, the old man...) framed in on them, the
    fire or lamp it names as a held close-up, otherwise the next angle not
    just seen. No shot repeats the one before it.
  - **The pan, by his ruling.** A walker is followed: the camera travels
    one way, eased, while they stroll across at the pace of their own
    stride (`Scene.camera`, `PAN_ZOOM`, `PAN_PACE`). A pan without a walker
    is refused by `validate`. Every other shot holds still, including the
    framed close-ups. Dissolves are 0.6 s now, down from 1.2.

- **The first render with sentence-length shots (9, BLOCK before the
  watch).** The gate's frozen-frame check found 47 identical frames at
  13:08: the Symposium painting, held for a whole sentence, moved only by a
  slow candle-light wave across the whole picture. The probe had passed it
  over 4 s, but not over a real sentence. A fast-flickering halo round the
  flame now does what a real candle does, and the painting test probes 12 s
  and demands a run under 12 frames (measured 6-10). A framed close-up of a
  person now only frames in when a moving light (or water) stays in the
  picture, so a crop cannot freeze a shot the same way.

- **The short-shot Greek film (70, BLOCK; Kokoro; longest still 1.0 s).**
  The freeze was fixed, and 4,916 frames were sampled with no hold over a
  second. The judge: *"about a third of the shots drop the people their
  sentence describes and show an empty floor with a lamp instead"*
  (craft 1, data_demo 1). "A man breaks bread ... a woman lifts a cup" was
  a lamp on a bare floor, and the market sellers became a cauldron in an
  empty yard. The cause was the shot planner itself: the `insert` close-up
  was the light ALONE, and it was 45 of the 273 shots. Fixed:
  - the fire/lamp close-up is the light AND whoever is at it (someone
    warming, tending, eating or talking first), framed so both are in the
    picture and the head is never cut;
  - a sentence that names two people is the shot of both;
  - a test runs the whole shelf Greek script and fails if any shot whose
    sentence names someone has nobody in it.
  - The technical floor still said 4,800 s (80 minutes, the retired long
    format) against his 20-30 minute ruling; it is 15 minutes now.
  - A brazier banks like a hearth when the words say embers (only where
    something else in the picture still moves: a banked brazier counts for
    little). 17 shelf passages re-mended.
  Still open from its notes: a harbour with
  boats on the sand, a spring with a jar, and a frame caught mid-dissolve.

- **The Greek film with people at the fire (74, BLOCK; Kokoro; longest
  still 0.67 s).** No more empty lamp shots, and craft and data_demo each rose
  from 1 to 2. Its notes now are about MATCHING:
  - a single of the man "breaking bread" leaves the table, bread and cup
    behind;
  - "sellers packing baskets" shows the woman at the cauldron;
  - the harbour boats and the stream are never drawn;
  - "a woman sets down her spindle" shows a man asleep on a terrace;
  - the brazier reads as "a modern kettle grill on three legs";
  - one seated-figure-and-lamp interior carries six passages;
  - a figure is cut by the left edge.
  Next: a period bronze brazier; a close-up keeps whatever its sentence's
  action uses (table, bread, cup, spindle); a harbour with beached boats; a
  stream; varied interiors.

- **The operator on that one, 2026-10-03:** *"sure, you're doing more cuts,
  but at the end of the day, it's still just stick figures moving their
  arms. Like, more needs to be happening per scene. Significantly more."*
  **Happenings** (`data_learning/doodle/happen.py`) give every shot events
  that move something across the picture or change its light. Each is worked
  out against that picture's own layout, so it fits or is not planned:
  - **arrive:** somebody walks in from the edge and sits down;
  - **leave:** somebody gets up and walks out;
  - **feed:** somebody brings wood or reaches in with a stick, and the fire
    flares and throws sparks;
  - **serve:** somebody brings bread or a cup and hands it across, then the
    other eats or drinks;
  - **light / snuff:** a lamp is lit or blown out, and the room brightens or
    dims in steps;
  - **child:** a child runs to a parent and sits close;
  - **passer:** out of doors, somebody goes by on the far side, a lantern in
    hand after dark;
  - **animals:** a dog trots in and curls up by the fire; a cat; hens
    pecking; birds or bats across the sky; a fish jumping; a mouse along the
    floor; a moth round a flame.
  `ori_sleep.happenings` takes what the words say first (adds a log, lights
  the lamp, a dog), then fills to at least one person-happening and one
  living thing that fit. The Greek script comes out at 2-3 in every one of
  its 273 shots.
  - Bodies blend between poses (standing up, sitting down) and hands reach a
    given point (`people.draw(pose_to, blend, reach)`); walking feet are
    clocked from the distance actually travelled, so they never slide.
  - The first sample found three faults: a dog trotting across a man in bed;
    walkers indoors floating up the wall; walkers by the river strolling on
    the water. Animals now never cross a person, the far lane exists only
    where there is ground behind the people, and the cast's own walkers
    cross at the people's depth indoors and by water.

- **The first full render with happenings (9, BLOCK before the watch;
  Kokoro).** 61 identical frames at 3:50: a candle blown out (`snuff`) in a
  wide room where it was the only thing alive. A happening that takes
  something away (a lamp out, somebody leaving) is now planned only where
  the picture still passes the motion rule without it
  (`happen._alive_without`, the same `is_living` that validate asks). The
  test renders a lamp going out and measures the frames after it. Somebody
  may also walk over to blow the lamp out, not only whoever sits beside it.

- **The Greek film with happenings (74, BLOCK; Kokoro; longest still
  0.67 s).** No motion complaint this time (temporal_craft 2, pace 2), but
  no gain in score either. Every note is about matching the words:
  - "boats pulled up on the sand" shows three people by the sea;
  - a stream is drawn as the open sea again;
  - "a child asleep on a low bed" shows three adults awake;
  - no table, bread or cup for the meal; no couches for the symposium;
  - an indoor spindle line is drawn as an outdoor rooftop;
  - pillar candles and a kettle-grill brazier are out of period.
  Its own fix: make every place-setting noun in a sentence a REQUIRED prop
  for that shot, and refuse a backdrop without it.
  Seen on my own look: the mouse turns up in too many interiors, and a cart
  floats over the forum (a back prop at the horizon).

- **The operator on that one, 2026-10-04:** *"This is shit fix it don't stop
  until I say."* The judge's notes, every one made a rule with a test
  (`tests/test_the_words_are_drawn.py`):
  - **The kit draws what the words name.** A `couch` (a kline) and a
    `recline` pose for the Greek dinner, propped on one elbow along it; a
    `spindle` in the hand and the act of spinning; a `boat` drawn up on the
    sand with its sail furled; a `stream` setting (a brook across open
    ground) and a `spring` (a pool at the foot of the town wall, fed from a
    spout — both measured alive with the gate's own probe); the brazier is a
    bronze bowl on a slender tripod, not a kettle grill; a wax candle no
    longer exists in a Greek or Egyptian room (`ERA_STAND_IN` turns it into
    an oil lamp).
  - **The author puts it in the scene.** `NAMED_PROPS` (one table for the
    author and the shot planner) grew boats, couches, jars, lamps, fires;
    when the named thing has no room, what the words do NOT name gives way,
    biggest first (the harbour's cart went for the boat). `mend_recline`
    lays the diners on couches when the words say so; `mend_doing` has
    whoever a clause names do what it says ("a man breaks bread" eats, with
    the bread). "In a smaller house" is indoors now; "a few streets away" is
    a distance, not a street; "at the water's edge" beside a spring is the
    spring.
  - **The shot keeps it.** `_choose` takes the sentence's named things as
    `needs` and picks only among shots that carry them; a repeated angle
    beats a wrong picture. A sentence about someone asleep is the shot of
    the sleeper. A long sentence is still cut at its commas, so "a man
    breaks bread ..., and a woman lifts a cup" is his shot and then hers,
    each at the table.
  - **Happenings grew:** a sleeper turns over (`turn`); the mouse and the
    moth never two shots running; a lamp is lit as filler only at dusk;
    a lamp with nobody near it is left for one somebody can reach.
  - A cart no longer stands across the bay: only buildings and trees take
    the far shore (`scene.FAR_SHORE`); everything else stays on this bank.

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
- 11,000–16,000 narrated words, 8–20 chapters (the author asks for 10–13 chapters sized from a 14,500-word target, about 110 minutes, with a per-chapter cap that keeps the total under 16,000 whatever the brain writes), 20–190 words a beat; the
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
