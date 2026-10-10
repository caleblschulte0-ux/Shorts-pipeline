# Shorts-pipeline — notes for Claude sessions

## Rule zero: if you can fix it, fix it — do not just name it

Operator ruling, 2026-08-01. An audit that lists a problem you were capable
of fixing, and then does not fix it, is worse than no audit: it converts a
bug into a bug PLUS a false sense that someone is handling it. The finding
gets read as progress.

So, in this repo:

- **Found it, can fix it, fix is in scope → fix it in the same change.**
  Not a ticket, not a "recommendation", not a follow-up.
- **Genuinely cannot fix it** — it needs a credential you do not have, an
  operator decision, a destructive action (history rewrite, deleting remote
  branches, anything outward-facing) — then say so **plainly, with the exact
  command or decision required**, and say WHY you stopped. "Needs your call"
  is a fix handed over; "worth considering" is litter.
- **Never build a capability and leave it unwired.** `shared/video_qa.py`
  sat imported-by-nothing for weeks while `CLAUDE.md` told every session to
  "run it before uploads". Five modules were in that state at the
  2026-08-01 audit. A capability nothing calls is not a capability, and a
  doc claiming otherwise is a lie the next session inherits.
  All five are now wired or honestly demoted, and the usual reason one was
  "missing" turned out to be that a channel had already grown its own copy
  privately — **look for the duplicate before you write the caller.** When
  you consolidate copies, the test is EQUIVALENCE against the originals
  (`tests/test_captions.py` is the pattern: the old implementations kept
  verbatim as oracles, compared over generated input). A cleanup that
  quietly re-cuts every video is not a cleanup.

The standing audit record — what was found, what was fixed, what is
deliberately left and why — is `docs/SYSTEM_AUDIT.md`.

Multi-channel automated YouTube pipeline (trending/daily, explainer,
curiosity, third "Proof Mode"). Channels are defined by orchestrator +
config + posted-log + token env, not by folders — see
`docs/STORAGE_AUDIT.md` §2 for the full map.

## The showrunner is the permanent, autonomous quality authority — DO NOT WEAKEN IT

The explainer channel fails CLOSED (see `docs/EDITORIAL_RESET.md`), and as
of 2026-08-01 **so does trending**. The headless-Claude SHOWRUNNER
(`scripts/showrunner_review.py`) is the standing editor-with-a-veto and it is
**load-bearing** — treat it like the posted logs, never as something to trim:

- **The policy lives in ONE place: `shared/showrunner_gate.py`.** Both
  publishing channels call it; `decide()` is pure, so the fail-closed rules
  are testable without rendering anything. Never re-implement it inline in a
  channel — that is how trending went six months shipping 6 unwatched videos
  a day while explainer was gated. The evidence that settled it is in
  `docs/SYSTEM_AUDIT.md` §B: explainer 1/day gated, best video 1,063 views;
  trending 6/day ungated, best video 45.
- **A fail-closed gate with no judge holds everything.** Any workflow that
  publishes MUST carry `CLAUDE_CODE_OAUTH_TOKEN` (or `GEMINI_API_KEY` as the
  fallback judge) on the render step, and say so in its preflight. Without
  that check the run renders a full slate and publishes none of it, green
  the whole way.

- It judges via the **Claude HEADLESS BRAIN** (the `claude` CLI on the
  `CLAUDE_CODE_OAUTH_TOKEN` subscription), NOT the paid Anthropic API. Keep
  it headless. It WATCHES the rendered video (samples frames, Reads them).
- Its BLOCK is **sovereign**: the brain judges what it SEES with full
  latitude, and code may only ever ADD blocks (a low-score / auto-fail floor),
  never flip a brain BLOCK to ship. Do not add any bypass.
- On a **publish** run it fails CLOSED (no verdict / infra error / timeout ⇒
  hold). `SHOWRUNNER=off` is refused on a publish run. Do not "fix" a failing
  gate by disabling it — fix the gate (or the video).
- Every verdict is appended to `state/showrunner_verdicts.jsonl` (its durable
  memory). The rubric it judges against is `docs/DIRECTOR.md`.

If a future task asks you to make the channel ship more / faster, the answer
is better videos, never a weaker gate.

- **The explainer AIMS AT 90** (operator, 2026-09-23: *"We need to be
  building a system that consistently puts out 90s ... Don't ask if you can
  post a 74. Make a system that makes better videos."*). `quality.target`
  in the registry: a cut the gate SHIPS below it is still repaired and
  re-judged, `polish_rounds` times within `polish_budget_min`, keeping the
  best cut ranked (ships, score). The illustrated arm's repair is the brain
  redrawing the scene the judge named, from the judge's own words
  (`scripts/scene_redraw.py`). The judge's `segN` ids count WINDOWS —
  [hook, beat 0, …, closing] — not beats (`scene_repair.judged_window`).
  Rules every subject scene meets are in `docs/CHANNEL_LOOK.md`.

- **A beat is about 8 seconds, and the budget is the registry's**
  (operator, 2026-10-05: *"15 seconds per beat is far too long"* — posted
  beats ran 26 words at 130 spoken words a minute). `pacing` under the
  explainer's format in `config/channel_registry.json`, read by
  `shared/pacing.py`: a SAY is one sentence of at most `say_words`, with
  caps for hook, closing and question, and `tempo` is the narration's
  playback rate. The forge writes to it and feeds an over-length draft
  back; the takeover brief and the rewrite mailbox state it; the editorial
  gate HOLDS a story over it as a `pace:` word reason (so the mailbox asks
  for a rewrite); `post_stories` has the brain `tighten()` a queued story
  BEFORE the gate, validated by the mailbox's own rules and persisted once;
  the renderer retimes every line per engine and writes `beat_s` to the
  sidecar, which the posted log carries as `beat_s_max`. Never write a word
  count anywhere else. Held by
  `tests/test_fifteen_seconds_a_beat_is_too_long.py`.

- **The judge of last resort is a MAILBOX ChatGPT answers**
  (`docs/REVIEW_MAILBOX.md`, ruling 2026-09-21). When neither the headless
  brain nor Gemini can watch a render on a publish run, the gate still
  holds it — and the render is KEPT (workflow artifact), its frames go to
  `preview-renders`, and `exchange/reviews/<date>/<id>.request.json` is
  filed with the verbatim prompt. ChatGPT grades into `<id>.verdict.json`;
  `scripts/claim_reviews.py` runs those grades through the SAME
  `assemble_verdict` + `showrunner_gate.decide`, verifies the artifact's
  sha256 against the request, and only then uploads. ChatGPT grades, code
  decides; nothing in the mailbox can ship what the gate did not approve.
  The same mailbox idea ends the text chain: `shared/llm_mailbox.py` files
  a question no backend could answer into `exchange/asks/` and returns the
  committed answer on the next run. **Aletheia is authorised to answer
  all three mailboxes** (ruling 2026-09-30, after ChatGPT answered none of
  them for nine days: *"let Alethea answer the mailbox ... We're not
  posting bad stuff"*). This repo accepts `"by": "aletheia:<route>"` and
  records her as the grader; her answers go through the same code as
  anyone's. Her worker is NOT BUILT yet (its write grant awaits the
  operator's direct approval) — see `docs/REVIEW_MAILBOX.md`. This repo
  still never writes into her intercom.
- **A held explainer story is RE-AUTHORED, not parked** (ruling
  2026-09-22, `shared/rewrite_mailbox.py`). The deterministic gate held
  312 of 337 stories that morning, nearly all for WORD reasons, and
  nothing ever asked anyone to rewrite them. Every story a run holds for
  word reasons or the judge blocks goes to `exchange/rewrites/` with its
  data, the rules and the reasons; ChatGPT rewrites; code validates
  (numbers derivable from the beat's data via `shared.beat_match`, no new
  entities, the same gate must pass) before `niche.config.json` changes.
  The gate does not move; the story does.

## Data (the mascot) performs a bespoke pose PER SCENE

`data_learning/mascot_director.py` renders **any** pose from parameters
(`_a_pose`: hand targets + lower body + props + expression + motion). WHAT he
does is regenerated per beat via `author_performance(...)` — brain-authored
when `MASCOT_BRAIN=1`, else a distinct preset rotated by scene index so no two
beats reuse the same act (two "sitting" beats can be totally different:
spooning soup off a can vs. gripping a bird mid-flight). Add new acts as
`POSE_PRESETS` entries; never regress him to one static reused pose.

**He is the CAUSE of the data's motion, not a reaction to it** (operator,
2026-10-01, on a tank filling while Data sat on a raft: *"Why doesn't he have
a thing of water in his hands? And he's pouring water into it. And he's the
one that's making the water rise ... a race car thing ... he would be the one
driving the race car."* — the principle, not the example). The jar fills
because he pours, the tower rises because he stacks, the needle sweeps
because he pushes it. `mascot_director.AGENT_ACTS` is the vocabulary (acts
keyed on the moving part's VERB, each with the anchor his hands are at),
`viz_scene.place_agent` puts that anchor on the part (on a ladder when it is
above his reach), and `viz_scene.AGENCY` makes every machine say which of
three things he is to it — agent, the moving part itself, or the thing the
data acts on. Point/strain/cheer beside the part is `decorative_mascot`, 203
auto-fails in a fortnight. `tests/test_data_is_the_cause.py` MEASURES it:
his anchor has to land on pixels that move. Docs: `docs/DATA_MACHINES.md`
§"Data is the CAUSE".

**Work is done WITH THE TOOL, in one arc** (operator, 2026-10-02: Data
"breaking the iceberg ... just flailing his arms around. Give him like a
pick axe"). `mascot_director.TOOL_ACTS` (swing_pick, chop, hammer, dig,
pump, broom, paddle, plus the agent acts) are one-shot wind-up → strike →
hold, no sine anywhere; a subject scene lands one per `beat=` and the
verifier refuses a `CAUSE:` whose verb has a tool when Data performs it
empty-handed (`VERB_TOOLS`, `scene_author.tool_problems`). `strain` is
for bearing a load, never for doing work. Add a tool act with its verb,
its anchor at the business end, and the test that it RESOLVES.

The RIG (how he is drawn) lives in `scripts/build_mascot_svg.py` and is the
single source of truth; `assets/mascot/host/*.svg|png` are generated from it
(`python scripts/build_mascot_svg.py --png`). Changing it changes the
character, so change it only on an explicit request — and regenerate the
assets in the same commit.

## The explainer picks its picture from what the data SAYS (docs/DATA_MACHINES.md)

Operator direction, 2026-09-07: *"speed becomes motion, imbalance becomes
weight, progress becomes distance ... data has physics."* The channel used to
pick its visual from the chart KIND — a `rank` insight got bars, a `trend` got
a line — which is a rendering decision dressed as an editorial one, and it is
why every video looked like the last.

`data_learning/relationships.py` asks the editorial question first and returns
ONE relationship; `studio_render._MACHINES` maps that to the pictures that say
it; `viz_scene._MACHINE_DRAW` draws them. **A chart is the FALLBACK, not the
default.** 42 machines, 38 relationships, all offline and host-baked.

Four rules, all of which were learned the hard way and are held by
`tests/test_data_has_physics.py`:

- **A relationship is a CLAIM, drawn at 200pt.** `share` says these are parts
  of one whole; this channel once shipped "2019 IS 9% OF THE WHOLE" over a run
  of mortgage rates. Every classifier refuses when unsure, and OTHER — draw a
  chart — is always an acceptable answer.
- **Where the shape is ambiguous the CLAIM decides, not the numbers.** Stages
  that shrink are a funnel, a ranking, a bottleneck, a supply chain and a set
  of sorting bins all at once by shape alone. A probability and a share are
  both "23%". A projection and a measurement are both a point on a line.
- **Do not edit a source file while the suite is running.** `inspect.getsource`
  resolves a function by its line number and re-reads the file from disk, so an
  edit mid-run makes a dozen source-reading tests assert against whatever now
  sits at those lines — they report failures in functions nobody touched. It
  looks exactly like a real regression and it cost this session two ten-minute
  runs before it was recognised.
- **Motion must be MEASURED, not asserted.** The cadence gate reads a 45-frame
  near-identical run as a freeze, and a slow glide across a whole visual is a
  sub-pixel change per frame. Five machines were geometrically perfect and
  measured as frozen. `MotionMustBeVISIBLE` renders 120 frames of every
  machine and diffs them with the gate's own detector.
- **One easing curve** — `viz_scene.settle()`. Four machines rolled their own
  ease-out and all four asymptoted into a still frame.
- **A NAME LOOKED UP WITH A SILENT DEFAULT IS A CAPABILITY THAT DOES NOT
  EXIST.** `ANIMATORS.get(act, _a_carry)`, `PROPS.get(prop, price_tag)`,
  `key in label.lower()` — three lookups, and between them they cost
  `decorative_mascot` 147 of this channel's 228 recorded verdicts and the
  FATAL `junk_imagery` 63 more. Data stood in every scene holding a blank
  price tag because `"none"` was not a prop and `"point"` was not an
  animator; a chart put a HOUSE on "cur-RENT-record". The showrunner
  described all of it precisely, for weeks, with every test green. When you
  add a name to any of these tables, add the test that says it RESOLVES, in
  the same change.

A new machine goes through the checklist at the bottom of
`docs/DATA_MACHINES.md`, which also records what is deliberately NOT built
(a network map needs edge data no source returns) and why.

- **A bespoke mechanic is TIER 1 only if it is MADE OF the subject**
  (operator, 2026-09-21, on a sheet of six brain mechanics: a track with a
  dog, a seesaw with a cat, two tubes, a timeline cross — *"everything in
  this image should be considered a non-chart, not a video-specific
  animation"*; of the fusion bolt grid: *"those were sick"*). The
  showrunner grades every depiction 0-3 on exactly that (`depictions` in
  the verdict, a learning signal, never a gate input), `grade_mechanics`
  writes the grade onto the scene and the library entry, and
  `_mechanic_examples` ranks by it ahead of `starred`. Four HAND-AUTHORED
  tier-1 teachers sit in `data_learning/viz_mechanics.json` flagged
  `exemplar: true`, seeded by `scripts/seed_exemplars.py`, which renders
  and verifies each on every data shape through the real sandbox before it
  will write. **Edit a teacher in the script, re-run `--write`** — the test
  holds the shelf copy byte-for-byte to the source. The method the brain is
  given (name the subject's verb, draw the number as that verb, swap test,
  keep it arriving) is in the kit prompt and `data_learning/VIZ_BRAIN.md`;
  the retro brief's `depictions` section measures whether tier 1 actually
  earns more watch instead of asserting it.

## The LOOK is `shared/look.py`, and it is held by tests (docs/CHANNEL_LOOK.md)

Operator ruling 2026-09-10: *"the whole look of the thing is cheap and shit
... we need a large scale rehaul of how the channel looks"*, then *"closer
but it can be even more sharp and clean and more professional YouTuber
looking"*.

`shared/look.py` is the ONE place a colour, a type weight or a mark
thickness is decided; `data_learning/charts.py` derives every token from it
(`TEXT`, `SUBTLE`, `HIGHLIGHT`, `REST`, `GRID`, `NAME_REST`). **Never name a
hex in a composer.** The full rule list, each with the frame it came from,
is `docs/CHANNEL_LOOK.md`; the four that get broken most often:

- **ONE accent per story, and it goes on the SUBJECT** — decided by the
  story, never by draw order. Supporting marks are `look.REST`, a NEUTRAL:
  a desaturated accent reads as *disabled*, and a stacked column that hands
  out six categorical hues is the loudest frame this channel has ever made.
- **Text wears INK, never the mark's colour.** `shared/palette` has said so
  in its own module docstring the whole time, and two composers were
  breaking it.
- **There is no card.** A bordered panel on a gradient is a UI widget, not
  a shot (`repair_planner` calls it `UI_WIDGET`). The data sits on
  `look.ground`, full bleed.
- **Every extent is MEASURED.** Character counts are not widths; a value
  column is as wide as its widest value; a `rounding_size` is in DATA units
  and on a 0..1 axes `1.4` is wider than the whole frame.

`tests/test_the_chart_is_a_shot_not_a_widget.py` and
`tests/test_the_channel_has_a_look.py` hold all of it. Every one is a defect
that was visible in a shipped frame — which is why they are tests and not a
style guide, and why a source-reading test here asserts on CODE (AST, string
constants blanked), never on the prose that explains it.

- **The art is LIT, not flat, and that is MEASURED** (operator,
  2026-10-05: *"the art in general on the B clips needs to be better"*).
  `illustrated.py` has one light model — `solid`, `box`, `cylinder`,
  `disc`, `contact_shadow`, `haze`, `vignette`, `edge`, key light `KEY` —
  exported to the brain's kit and used by the teachers; prompt rule 12
  says so. `scene_author.craft_problems` counts exact-colour slabs in the
  hero band and refuses more than `FLAT_MAX` as clip art; it runs inside
  `verify` and on every SAVED scene at load, so flat scenes drawn before
  the light are redrawn, never shipped again. A subject helper that
  `cr.fill()`s one flat colour is the defect; draw the path, call
  `solid()`. `tests/test_the_art_is_lit.py`.

- **A subject scene is a SHOT, not a diagram** (operator, 2026-10-07: a
  front-on barn over an empty field was *"still very much lacking"*; the
  same beat with a low sun, far-to-near hills, the barn in three-quarter
  view and hens by the camera was *"ok now we are talking"*). The shot is
  in the kit — `landscape`, `building`, `cast_shadow`, `foreground`, `hen`
  in `subject_scenes.py` — prompt rule 13 asks for it, and
  `bird_flu_barn` is THE SHOT the brain is shown as the bar.
  `tests/test_it_is_a_shot_not_a_diagram.py`. It is CRISP, not felt (same
  day: *"I want it to be crisp and clean"*): `illustrated.GRAIN` is off and
  the edge is a clean dark line. And the SCALE is IN the shot (*"there is
  no scale or context"*, then, of a bar strip over the frame, *"boxes on
  top of the video doesn't help ... glance at it and gauge the scale"*):
  `then_mark`, `ghost`, `times_ticks` draw the earlier size ON the
  subject, prompt rule 14 asks for it, no overlay is laid over a scene.
  `tests/test_the_scale_is_on_screen.py`.
  And the CHANGE is big and the numbers few (same day, of a plastic pile
  that tripled under one number beside a bone that stood still under three:
  *"I like the pile one but the bone one no"*): `verify` refuses more than
  `MAX_HEADLINES` big numbers in a frame and any label on top of Data, and
  the glance refuses a change a viewer calls "barely" and a picture they
  call a diagram. `tests/test_one_number_and_a_big_change.py`.
  A scene that passes also gets ONE look again (`scene_author.look_again`):
  the drawing brain READS its own frames beside THE SHOT and redraws what
  looks cheap, told why and given one more go if a redraw fails; the
  redraw replaces it only if it passes every same check. THE PILE
  (`subject_scenes.recycling_pile`, brain-drawn, kept verbatim) is the
  second bar beside THE SHOT, in the prompt and in the look again.
  And the payoff LANDS IN TIME TO READ IT (operator, same day, of the
  bird flu fence ending: *"we only have it on screen for like a second
  ... whiplash ... I'm not saying we necessarily need to be sitting on
  beats longer but we need to fix this"*). A scene is on screen as long
  as its narration — `scene_author.SCENE_SECS`, hook 4s / beat 6s /
  closing 4s from the posted log, never the 10s the checks once assumed —
  and `payoff_problems` refuses any number it ends on that arrives after
  `land_by(secs)`, in `verify` and on every SAVED scene at load. A
  readout steps through at most `READOUT_SHOWS` values (`landed`). After
  the payoff the world moves, the story holds; prompt rule 16.
  `tests/test_the_payoff_lands_in_time_to_read.py`.
  And the BUILD FILLS THE BEAT (operator, 2026-10-09: *"some animations
  hold too long at the end after all the cool stuff has already
  happened"*): `PAYOFF_BY` is 0.72, so a beat holds its finished picture
  about `READ_S`, and `subject_scenes._render_frames` PACES every scene
  (`scene_author.landed_at` + `paced`) — one that finishes early is
  stretched to land by `land_by`, saved scenes included. And the picture is
  WHAT THE NARRATION SAYS HAPPENS (same message: *"by the end it's just
  stacking boxes"*): the glance's judge is given the beat's narration and
  refuses a generic stack, tower or bar (`story_fit`), prompt rule 17.
  `tests/test_the_build_fills_the_beat.py`.
  And the OPENING IS THE SHOCK (operator, 2026-10-08: *"our hook and first
  10 seconds need to be better ... we need to be really hooking the
  audience"*; 55-70% of viewers swiped in the first seconds). Rendered,
  posted openings began on the smallest state of their picture — an empty
  frame under "Your kid's", a knee-high pile that became the mountain at
  second five. `studio_render.flash_forward` lays the opening picture's
  FINISHED frame over its first `FLASH_S`, the first picture never fades
  in from black, and the WHOLE hook line is on the plate from frame one
  with the said word lit (`hook_karaoke`). `tests/test_the_first_frame_is_the_shock.py`.
  And the hook is said the way a PERSON says it (operator, same day:
  *"our word hooks are trash"*). A keyword score — points for "you" and
  for a verb off a list, with the forge refusing anything under 7 — had
  taught the brain "your garden vanished 94% of milkweed" and "...shocking
  everyone", and bought nothing (posted hooks scoring 7+ kept 31% of
  viewers, 0-2 kept 36%). It is gone. Code holds a FLOOR only
  (`hook_doctrine.floor`: quiz, hedge, vague size, formula tag, length,
  garbled) plus the numbers-and-names `problems`; a LISTENER (`listen`)
  hears the current hook beside the rewrites as a scrolling viewer, fails
  the untrue and the unsayable, and ranks the rest. Never put a keyword
  score back in. And it is a TABLOID line, not a lab result (same night,
  of "...allergies went from 0.4% to 1.4%": *"thinking like a TMZ/youtube
  click bait type shit not nerd ass"*): the writer and the listener both
  look for the twist, the villain, the loss, the comeback or the secret,
  and the floor refuses two numbers, a "from X to Y" or a decimal in a
  hook. The video reads the numbers; the hook says what they MEAN.
  `tests/test_the_hook_is_an_ad.py`.
  And the VOICE is handed WORDS (operator, same day: *"everything and
  anything it could mis read ... needs to be in word format"*).
  `shared/spoken.say` is the one speller: units, °F, decades, ordinals,
  fractions, ranges, acronyms ("US" is "U S"), shouting, every number.
  The explainer's `_tts_text` is it; trending's `normalize_for_tts` is its
  `shorthand` (trending times cues off a digit transcript, so it keeps
  digits). `tests/test_the_voice_reads_words.py` runs every queued line.
  And the NARRATION TELLS A STORY, not the data (operator, 2026-10-09:
  *"this whole thing is just us reading off numbers to people ... we can
  just say the experts, unless it's a really famous one, like WHO"*).
  `shared/narration.py`: `problems` flags a beat reading off more than
  `MAX_NUMBERS` numbers or naming a group outside `FAMOUS`; `retell` has
  the brain retell it before the gate (next to `pacing.tighten` in
  `post_stories`), validated by the mailbox's own rules, then heard
  against the old words by a listener that may keep them; persisted once
  (`retold`). It never holds a story. The forge and the mailbox carry
  its `DOCTRINE`. Then, of the first retell: *"take it a step further ...
  the less numbers we just throw at them in a row, the better. And
  obviously we want it to be entertaining"* — so `MAX_NUMBERS` is ONE, a
  change is said in words ("it nearly doubled"), and the listener picks
  the simpler, more fun story. `tests/test_the_narration_tells_a_story.py`.

- **A brain-drawn subject scene has to pass a VIEWER, not just the code**
  (operator, 2026-10-01: a coffin he "couldn't tell was a coffin", an urn
  of blue "ash" that read as water, a rope "pulling a liquid up"). Every
  scene declares `HERO:` / `SUBSTANCE:` / `CAUSE:` in its docstring, and
  `scene_author.glance` shows two wordless, Data-less, PHONE-SIZED frames
  to a brain that is not told the subject; it must name the hero from the
  object's own shape (not its setting) and agree with all three before the
  scene is used. Keep it: it is
  the only check that sees what the code cannot. `docs/CHANNEL_LOOK.md`
  §"A VIEWER has to recognise it".

## `config/channel_registry.json` is the ONLY place channel policy lives

How many videos a channel ships, in which formats, which formats are retired,
what ChatGPT is responsible for, queue minimums, media requirements, where
output goes — **all of it is in one JSON file**, resolved through
`shared/channel_registry.py`:

```bash
python -m shared.channel_registry            # every channel, one line each
python -m shared.channel_registry --mix trending
python -m shared.channel_registry --validate
python -m shared.channel_registry --markdown # the table docs embed
```

Change that file and everything inherits: the Routine prompt, Phase A's
bundle, ChatGPT's authoring brief, media requests, Phase B validation,
promotion, the package validator, and the no-bundle takeover. **No scheduled-task
prose ever needs editing.** Never write a count or a mix anywhere else —
`tests/test_no_second_source_of_truth.py` runs in the auto-merge gate and
fails the PR if a second copy grows back. That test exists because the
2026-07-31 graph-led ruling landed in one of five places that stated the mix,
and the takeover went on asking for a retired format with everything green.

- **A day's bundle FREEZES the registry** into `bundle.json.contract`
  (revision, sha256, `source_commit`, resolved plan per channel, doctrine
  hashes). That snapshot governs that date; a registry change starts with the
  next bundle. `--rebuild-contract` is the deliberate migration.
- **Precedence**: the date's snapshot → the registry → the doctrine files it
  names (read at `source_commit`) → docs, which are explanatory only.
- **A missing or invalid registry fails CLOSED.** Falling back to a
  historical mix is how a retired format gets authored on a day nobody is
  watching.
- Deep editorial doctrine stays in its own files (voice, topic banks,
  per-format writing rules). The registry says WHAT and HOW MANY; those say
  HOW. Verify the whole chain offline with
  `python scripts/registry_acceptance.py`.
- **The registry only governs REGISTERED channels — two publishing crons sit
  outside it.** `curiosity.yml` and `longform.yml` each have their own weekly
  schedule and their own uploader, and long-form posts to *explainer*, which
  is enabled — so nothing in the registry looks wrong while a switched-off
  format ships. Turning a channel off therefore means the registry **and**
  the workflow. `tests/test_disabled_channels_stay_off.py` holds both ends
  together: a cron for an off channel may build, never upload; publishing
  hangs off a manual dispatch a schedule cannot supply. This was found live
  on 2026-08-06 — long-form was three days from uploading a video the
  2026-08-05 ruling had switched off everywhere except that one file.

Trending's formats are `reddit_story` (gameplay + post card + TTS) and
`graph_race` (animated chart); `text_card` is retired. **Those are the
current values, not a rule — read the registry.** It is NOT the old single
stacked/gameplay format, which is a fallback shape only. Per-format writing
specs: `CLAUDE_ROUTINE_INSTRUCTIONS.md` and
`shared/authoring_brief.py:FORMAT_SPECS`. It regressed to 6-of-one on
2026-07-30 because the spec lived only in the Routine's prompt; if you ever
see a slate of one format, that is the bug.

## Repo layout: the funnel (reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md)

Top-of-funnel media in **`funnel/`** (media_funnel, topic/entity image
finders, stock search, gemini_images AI-gen, usage ledger, og_scrape,
gameplay_scanner). Cross-channel utilities in **`shared/`** (fsutil,
uploaders, localize, script_generator, themed_bottom). Render capabilities
in **`engines/`**. Channels are thin consumers: daily renderers at root
(`make_*.py`), explainer/curiosity in `data_learning/`, third in
`third_capture/`, orchestrators in `scripts/`.

- Import canonically: `from funnel import media_funnel`,
  `from shared import uploaders`. **The 18 root shims are GONE** (deleted
  2026-08-01) — `import fsutil` is now an ImportError, not a deprecation.
  `tests/test_repo_layout.py` keeps the root clean and stops them growing
  back.
- New shared capability → `funnel/` (media), `engines/` (render engine),
  `shared/` (everything else). Never copy shared logic into a channel.
- The 2026-07-30 sprint's five capabilities are all WIRED as of 2026-08-01
  (they spent a day as the exact thing rule zero forbids):
  `shared/video_qa.py` runs on every trending render; `shared/captions.py`
  is the single caption grouper for `make_reddit_story`,
  `make_explainer_stacked` and `third_capture/clip_edit` (each delegating
  with parameters that reproduce its old output EXACTLY — see
  `tests/test_captions.py`, which holds that against the original
  implementations); `funnel/feeds.py` backs `scripts/discover_topic.py`;
  `funnel/article_extract.py` fills `topic.snippets` so the writer works
  from the real article instead of a headline. `engines/svg_motion.py` sat
  `experimental` and consumerless past two decision dates and was DELETED
  on 2026-10-03 — the deadline test did its job.
- **The engine registry has to tell the truth.** `active` + not `gated`
  means something really imports it; `tests/test_engine_registry_honesty.py`
  checks the metadata against the code in both directions, because it was
  once wrong in both at the same time.

## The story forge keeps the queue full of REAL data

`scripts/story_forge.py` discovers indicators from the live World Bank WDI
catalogue, fetches world trends / country rankings, and writes datasets with
honest provenance (publisher, url, access_date, officiality=official). The
brain writes only the WORDS and the SCENE; every number comes from the
source. Run by `story_forge.yml` (twice daily) and by every posting run.
Never refill the queue with LLM-invented numbers — the editorial gate
refuses them, so a queue full of them still ships nothing.

## Engines: the shared capability layer — USE IT

`engines/` is the top-of-pipeline capability library any channel, script,
or Claude session can call. Before building a rendering/media capability
from scratch (animating a still, depth effects, future physics/maps/audio),
check whether an engine already exists or is ticketed:

```bash
python -m engines list            # every engine + availability (offline, fast)
python -m engines info <engine>   # metadata, license, pinned models, sample cmd
python -m engines doctor          # health-check all engines (no network)
python -m engines install <name>  # provision deps + checksum-verified models
python -m engines demo kenburns --image X --out Y
```

Full registry, triage verdicts, and the ticket backlog (E1–E14):
`docs/ENGINE_REGISTRY.md`. Contract: `maybe_*()` functions return a result
or `None`, never raise — safe to call best-effort from any renderer.

Rules:
- **`parallax` is active but GATED** (E2 verdict 2026-07-10: photos pass,
  flat art/text refused by the input suitability gate). First adoption in
  any channel still requires a preview render before flipping a default.
  `still_motion.kenburns` is always the fallback.
- New engines follow the checklist at the bottom of the registry doc
  (headless, CPU-viable, commercial-safe license, pinned models, `maybe_*`
  contract). One at a time, each earning its slot with a better video.
- Models/caches live in `cache/` (gitignored) — never commit binaries.

## ChatGPT exchange (docs/EXCHANGE_PIPELINE.md)

The daily run splits so ChatGPT contributes BEFORE any render: Phase A finds
media and judges every shot against its script line, writes one bundle of gap
requests + scripts, and stops. ChatGPT answers (images to Drive, punch-ups to
git) and writes a DONE marker, which fires Phase B: verified media pull,
self-fill for anything unfulfilled, guarded punch-up, then render.

- **Pollinations is retired as the AI-image path** — all AI images come from
  ChatGPT; gaps it misses get filled with real media by the self-fill pass.
- **Policy A**: a ChatGPT no-show never costs the day (self-fill + Phase B's
  08:30-Central backstop crons). A weaker shot beats no video.
- `shared/punchup_guard.py` is not advisory: a rewrite that changes any
  number/date/entity or the beat structure is rejected and the original ships.
- **ChatGPT is TWO workers now** (2026-07-31): a **06:00 Central MEDIA worker**
  (generate + upload + verify images, checkpoint each one, never writes
  `response.json` or `DONE`) and a **07:00 Central FINALIZER** (recover, fill
  gaps, punch up, author, then `response.json` and `DONE` as separate commits).
  They cannot see each other's context, so the repo is their shared memory:
  `exchange/bundles/<date>/media-progress/<safe_request_id>.json`, contract in
  `shared/media_checkpoint.py`. **`DONE` is the only thing that fires Phase B**
  — a checkpoint push must never start a render, or the day renders at 06:05
  with nothing authored and every check green. Filenames are deterministic
  (`<date>__<safe_request_id>.png`) and published in the bundle BEFORE either
  worker starts, which is what makes an orphaned upload recoverable. Verify the
  contract offline with `python scripts/exchange_dry_run.py`.
  Three rules that are not negotiable: **a DONE run REQUIRES checkpoints**
  (only the no-DONE emergency backstop may accept media without them); a
  pointer must match its checkpoint on **every** field (filename, file_id,
  folder_id, sha256, bytes, format, width, height, link-visible sharing), not
  just the hash; and **one Drive file may back exactly one request** — a
  file_id under two request_ids refuses BOTH, identical hashes included.
- **Phase B's backstop is 08:30 CENTRAL, from two UTC crons** (`30 13` and
  `30 14`), gated in-code by `zoneinfo` — never a single UTC cron. The old
  12:45 UTC one was 6:45 Central in WINTER, fifteen minutes before the 07:00
  finalizer starts, so for half the year it would have rendered an unfinished
  day with everything green. If the ChatGPT finalizer ever moves, move
  `FINALIZER_HOUR_CENTRAL` in `scripts/exchange_phase_b.py`, not the crons.
- **The chain is LIVE and automatic** (2026-07-30): Routine authors packages ->
  auto-merge -> **Phase A** -> ChatGPT -> DONE -> **Phase B** -> daily.yml
  renders. `daily.yml` NO LONGER fires on auto-merge or on a
  `state/trending_packages/**` push — those would render with pre-ChatGPT media
  and defeat the exchange. Phase A took that slot; daily.yml now fires only on
  Phase B completing (or a manual `.github/triggers/daily` touch).
- Never dispatch `daily.yml` as the step after authoring — it is the LAST step.
- Clock: Routine ~09:19 UTC -> Phase A (auto, 09:45 cron backstop) -> ChatGPT
  6:00 AM Central -> Phase B (auto on DONE, 08:30-Central backstop) -> render.
  Posts land 8:00/9:30/11:00/12:30/2:00/3:30 Central. Phase B's backstop is
  DELIBERATELY late (08:30 Central, held by the in-code zoneinfo gate no
  matter which of the two UTC crons fires): ChatGPT's task is local-time and
  shifts an hour at DST while crons do not, so a UTC-anchored backstop would
  render pre-ChatGPT media for half the year with everything green. (This
  paragraph once said "12:45 UTC" and an earlier one said "06:15" — both
  were stale copies of retired schedules; the doctor caught the drift on
  2026-08-22. The crons are `30 13` and `30 14` in exchange_phase_b.yml and
  the hour lives in `FINALIZER_HOUR_CENTRAL`, nowhere else.)
- **GitHub's cron is NOT a clock — `clock.yml` is** (2026-09-22). Every
  scheduled run that day landed two to five hours late or never came: the
  explainer's 13:40, Phase B's 13:30 backstop and two dead-man slots did
  not fire, the hourly claim cron ran three times in fourteen hours. The
  clock is a `workflow_dispatch` CHAIN (`scripts/clock.py`): each tick reads
  every cron in the repo, gives GitHub `GRACE_MIN` to honour a slot, then
  dispatches what was missed with the inputs the cron path uses
  (`DISPATCH_INPUTS` — an empty `mode` on the explainer posts nothing; Phase
  B gets `backstop=true`), sleeps to the next quarter hour and dispatches
  itself. A dispatch is an API call, honoured immediately, and the one
  event GITHUB_TOKEN may raise. Its own cron is only a bootstrap. Stop it
  with `state/clock/OFF`. `tests/test_the_clock_does_not_trust_cron.py`
  holds that every cron is covered or excused with a reason — a new cron
  is not scheduled until that test says the clock will fire it.
- A Phase A that finds no packages exits 0 — so this bug class is INVISIBLE in
  the Actions tab. To confirm the exchange ran, check for
  `exchange/bundles/<date>/bundle.json`, not a green checkmark.
- Third/explainer chain off "Daily Shorts", so they now run ~1.5h later too.

## Third channel: story arc system (docs/STORY_ARC_SYSTEM.md)

The third channel's `story_count` daily slots auto-detect narrative arcs
and compile them into multi-clip stories — quality-gated by a showrunner
brain, falling back to a normal clip when no genuine arc exists.
Compilation dedupe rides `story_key` (member-set hash), never member
`source_url`s. Content standard: docs/THIRD_INTERNET_PLAYBOOK.md.

- **The BRAIN finds the story — across a month, across streams**
  (operator, 2026-09-22: *"Twitch isn't gonna hand them to you on a silver
  platter ... more than one stream sometimes. Sometimes they'll be from one
  stream. The thing needs to use its brain"*). `storyline.build_catalogue`
  writes the whole lookback window as one line per clip — every POSTED clip
  across the month plus the freshest discovery — and
  `story_director.scout_stories` reads it and proposes stories. It goes
  FIRST; same-broadcast VOD arcs (`find_vod_arcs`, from helix's `video_id` +
  `vod_offset`) second; word-matched people clusters last. Measured on that
  week's own log, the old word matcher cut the payoff off Kai Cenat's
  Wolverine arc and split Lang's Brickbois story and Buddha's rug pull into
  singletons. **The scout proposes, it never decides:** a proposal only buys
  scene analysis, then `plan_story` gets it labelled as a HYPOTHESIS with
  the transcripts and frames, §8 unchanged. What it proposed is recorded
  per slot in `judges.story_director.supply` in `state/third_qa_stats.json`
  — read that before tuning anything.
- **A story can be ONE moment and the stream around it** (2026-10-08,
  after four backtests in which the director refused ~150 grouped
  candidates as "two unrelated moments" and every rendered cut failed on
  the setup or payoff the clipper cut off). `storyline.find_moments`
  offers the hottest unposted clips with VOD coordinates; `run_third`
  fetches the BEFORE and AFTER from the VOD as sources of their own
  (`_moment_segments`, `clip_edit.maybe_vod_segment`) and the director and
  the critic judge them like any story, same 80. No VOD, no story — never
  padded. They take turns with the scout and the arcs.
- **The scout reads what the clips SHOWED, not just their titles**
  (2026-10-02: all three of the 10-01 proposals were refused because "the
  boar snipe never appears" — built from titles, while the run held the
  footage). `third_capture/clip_memory.py` keeps what every transcribed or
  analysed clip says and shows, and every story the director refused with
  its reason; the catalogue prints the evidence beside the title, the scout
  is told what was refused, a retold refusal is skipped before download.
  The director may tell the smaller story a padded proposal really holds —
  from two or more sources, which `validate_edl` now enforces.
- **A rendered story is REPAIRED before it is dropped** (operator,
  2026-10-03: *"Post a story."*). Up to `story_revisions` (2) repairs from
  the critic's own problems, same `publish` bar; two story slots a day;
  and every way a candidate dies is a recorded verdict with its reason —
  the two stories that reached a render that week died with nothing
  written down.
- **A story ships at `story_min_score` (80), not at the critic's "publish"**
  (operator, 2026-10-05, of a 74 that shipped with no payoff: *"This needs
  to be better ... it's also the story"*). The critic had passed every story
  it saw (66-80); only the 80 held viewers. It must also retell the story in
  a sentence and name the payoff second, or its pass is a fail.
- **A plan is READ before it is rendered, and a near-miss KEEPS ITS EDIT**
  (2026-10-08, backtests 7-8). The critic reads the words a plan would
  hold (`story.plan_ledger`, held equal to the render's ledger) and the
  director repairs on paper; only what reads as no story at all
  (`story_table_read_min`) is skipped — the words alone score ~10 below
  the cut. Every judge is a brain that never answers twice the same way
  (the same Lacy story: 82 one run, "not a story" the next), so an edit
  rated >= `clip_memory.KEEP_MIN` is kept and repaired on the next try,
  `KEEP_RETRIES` times. The repair is told which beat and source second
  each critic note lands on (`story_director.locate`). Same 80 throughout.
- **A story has NO narrator — a line of text on screen** (operator,
  2026-10-08: *"No narrator but like any clip your allowed like a line or
  2 of text on the screen"*, with three reposts as the look). The hook is
  one sentence-case line in the bottom third, white with a black outline, no box,
  there the whole video (`story.beat_captions`: one caption at a time; a
  time-jump overlay or a line of context replaces it long enough to read).
  The line may say who someone is when the footage never does, from
  `story_director.known_people`: one model proposes, a DIFFERENT model
  must confirm, events and accusations never qualify.
  `tests/test_a_story_has_no_narrator_only_a_line_of_text.py`.
- **A clip is edited like the reposts, not by an effects engine**
  (operator, 2026-10-09: *"That weird slowdown thing we do never works,
  and then we speed up randomly after it ... do a gray overlay and do that
  specific sad song whenever something sad happens ... the dead rose with
  the crying face ... don't put captions over the captions of the
  video"*). No slow-mo, replay, speed-up, slam word or sticker emoji (the
  auto-editor's Stage 1 is retired; stories drop every effect). The hook
  is ONE sentence-case line with its emoji, drawn by
  `third_capture/caption_line.py` in the bottom third for the whole
  video; the word captions sit above it (`SPEECH_Y`) and are skipped when
  the stream already shows what is said (`clip_edit.own_captions`, OCR
  against the transcript). The author marks a sad turn (`edit.mood`,
  `mood_at`) and `third_capture/mood.py` greys the picture and brings in
  a synthesised piano from that second — not a commercial song, which
  Content ID would claim. Grey is one move of a kit (same day: *"you have
  to add stuff other clippers do ... we can't just do the sad grey
  thing"*): `third_capture/moves.py` — a punch-in with a boom, a shake, an
  awkward push-in with crickets, the hype colour and 808 beat, a second
  line at the turn — each on the second the author names (`edit.moves`,
  `edit.line2`), rebased onto the cut, every sound synthesised. None
  changes the clip's speed. A dry run with `clips_only` publishes its renders
  to `preview-renders:third-dry/<run id>/`.
  `tests/test_a_clip_is_edited_like_the_reposts.py`.
- **A story is a CHAIN, and the edit SHOWS what it talks about**
  (operator, 2026-10-09, after backtest 17: *"it's not a collection of
  clips or like 4 moments in a stream played in a row"*; of xQc on a rug
  pull: *"put a picture of the stock he is talking about as a layover for
  a few seconds so they can get it. Internalize what [we're] going for"*).
  Every beat after the first carries `link` "so" (it happens because of
  the beat before) or "but" (it turns against it); `validate_edl` refuses
  "and then", and the scout, director, critic and reviser are all told.
  A clip (`edit.show`) or a beat (`show`) names a thing that is said but
  not seen; `third_capture/show_it.py` cuts in its picture for `SHOW_S`
  at that second: a price chart around the clip's date for a coin or a
  stock, else the lead image of the Wikipedia article whose title IS the
  thing. No exact match, no picture. And sex sells, with dignity (same
  night: *"we have the green light to goonbait not to much let's keep our
  dignity"*): the picker and the writer lean into flirting and thirst,
  adults only, nothing a platform would age-restrict.
  `tests/test_a_story_is_a_chain_and_shows_what_it_talks_about.py`.
- **Slots follow `_learned_prior()`, and it had no tests** until the day it
  was found inverted: kaicenat and buddha (median 5 and 8 views) at the
  maximum boost, jynxzi (1,355-view top video) below them, because flops and
  hits were scored in different units. Every video is now a percentile on
  one scale. `tests/test_third_streamer_prior.py` includes a direction check
  against the committed analytics — if it fails, the prior disagrees with
  the channel's own view counts.
- **The channel is a SEARCH channel** — ~89% of views are YouTube search.
  `_search_guidance` hands the title author the real queries for that
  streamer ("lang buddha", "jasontheween news"), with an honesty rule and
  every other streamer's name and aliases filtered out.

## Media acquisition (docs/MEDIA_ACQUISITION.md)

Every visual carries a `source_class` + license (recorded in the audit
sidecar). Copyrighted media is NOT auto-rejected — it enters through the
transformative-evidence lane when the script directly engages with it,
the amount is proportionate, and the use is documented. Never bypass
DRM/paywalls/rate limits. The funnel pulls from 18 providers; new source
adapters are tickets M1–M9 in the doctrine doc.

## Fallbacks (docs/FALLBACKS.md)

Every fallback path is traced top-to-bottom in `docs/FALLBACKS.md`. The
three things worth knowing without opening it:

- **Authoring is the only Claude-dependent stage.** Media, render, and
  upload have no Claude dependency; `_call_llm` has always preferred
  Groq → Gemini → Anthropic. The showrunner is the exception and it fails
  CLOSED — no Claude *and* no `GEMINI_API_KEY` means the explainer channel
  publishes nothing (`post_stories.py` refuses `SHOWRUNNER=off` on a
  publish run).
- **A dead brain is covered by the ChatGPT whole-pipeline takeover**
  (`shared/authoring_brief.py` + `scripts/ingest_authored.py`): Phase A
  normally puts the live registry plan and any `authoring_request` into the
  bundle. If Phase A itself is missing, the 06:00/07:00 workers read the
  registry directly; no bundle is the takeover signal, not permission to
  stop. ChatGPT writes the missing content, supplies/verifies media, and
  supervises every enabled channel's registered worker through QA and
  verified upload outcomes. Nothing it authors is trusted — promotion runs
  the same structural gates as normal production and quarantines failures.
  `response.json`/`DONE` mean the handoff is ready to render; they do **not**
  mean production completed. Registry role `production_supervisor` is the
  durable statement of this whole-pipeline ownership. Trending is authored
  as packages; Explainer's sourced datasets retain their numbers while
  ChatGPT repairs words; Curiosity receives queue stock; Third still
  captures its own real clips, while ChatGPT invokes/monitors that
  specialized workflow rather than fabricating a clip recipe.
- **A slot the GATES emptied is RE-AUTHORED, not lost.**
  `run_trending_daily._backfill` discovers a fresh topic (excluding every
  posted title), writes it, renders it, and sends it through the identical
  QA + showrunner path — capped at `MAX_BACKFILL` attempts. It is not and
  must never become a bypass: `_backfill` mentions the showrunner nowhere,
  and `tests/test_backfill.py` fails if it ever does. A replacement the gate
  also refuses stays refused, and a day with nothing fresh to author stays
  honestly short.
  **A replacement is a reddit_story, and a reddit_story is FICTION on a
  universal premise — never the news** (2026-09-22: four backfills told
  "a fabricated first-person 'cousin sold missiles' story laid over a real
  geopolitical headline", all blocked at 18-22). `shared/script_generator`
  builds its prompt from the registry's own reddit_story spec, refuses a
  topic about death, violence, war, crime or politics before a word is
  written (`unfit_for_fiction`; `_backfill` skips those before a render),
  and rejects a story that names anything the headline capitalises
  (`real_entities`). The trend only chooses the setting. Held by
  `tests/test_a_backfill_story_is_fiction_on_a_universal_premise.py`.

  **There is no reserve bank.** `shared/package_buffer.py` +
  `scripts/package_reserve.py` were retired 2026-08-05 on the operator's
  ruling — *"if something doesn't run properly, it goes through and tries
  again."* A shelf covers only as many failures as somebody remembered to
  stock it for (ours held two against a low-water mark of twelve) while
  reading like a safety net in every report. Its structural validator moved
  to `shared/package_schema.py`, which was never about banking: it is the
  one "is this package well formed" gate every producer runs through — the
  Routine, the in-CI brain, and a ChatGPT takeover alike.

## WHO MAY EDIT THIS PIPELINE — Claude, and only Claude

Operator ruling. **Claude is the only agent that edits this repository.**
ChatGPT can run quarterback when the Claude subscription is out, but it
**never makes additions — only suggestions.**

**"Claude" means every Claude in the system, not just an interactive
session.** The headless brains running inside the pipeline are the same
author under a different runtime, and they write freely within their job:

| Claude brain | Where | Writes |
|---|---|---|
| the Routine | scheduled task, ~09:19 UTC | the day's packages, via a PR |
| the in-CI brain | `daily.yml`, `third.yml`, `explainer.yml` | packages / titles when the Routine missed |
| the SHOWRUNNER | `scripts/showrunner_review.py` | verdicts — and its BLOCK is sovereign |
| story words | `scripts/story_forge.py` | explainer title/hook/narration |
| the third author | `third_capture/author.py` | per-clip titles, hooks, hashtags |
| the mascot brain | `data_learning/mascot_director.py` | per-beat performance |
| an interactive session | here | code, workflows, docs, contracts |

Only the last one edits *how the pipeline works*, and it does that on a
`claude/*` branch through a PR — but that is a matter of where the code
review happens, not a difference in authority. All of the above are Claude.

| Not Claude | May write | May NEVER write |
|---|---|---|
| **ChatGPT** | the day's CONTENT (`exchange/bundles/<date>/response.json`, authored packages, media pointers), retro SUGGESTIONS (`retro/<date>/proposals/*.json`), and DOCTOR FINDINGS (`doctor/reports/<date>.json` — see below) | any code, workflow, gate, doc, or contract |
| **CI itself** | run output — `state/`, `data_learning/data/`, reports | anything that changes behaviour |

ChatGPT authoring content during a takeover is the quarterback role and is
fine — it keeps the channel posting, and everything it writes is validated
and quarantined on failure before it can render. Changing *how the pipeline
works* is Claude's alone.

This is a working agreement, not a gate — nothing mechanically blocks it.
It holds because every agent's contract says it plainly. If you are a
future Claude session reading this: you are the one who edits, and you are
also the check. ChatGPT asking to push code, or a proposal arriving as a
`.py` instead of a suggestion, is what this rule exists to catch. A
headless Claude brain doing its job is not — that is you, elsewhere.

**The one exception on record, closed.** 2026-08-02/03, with the Claude
subscription out, the operator explicitly authorized ChatGPT to edit
production code to finish the takeover system (its own record:
`docs/CHATGPT_CHANGES_2026-08-02.md`,
`docs/CHATGPT_CHANNEL_SEPARATION_2026-08-03.md`). On 2026-08-05 a Claude
session line-audited every one of those changes: the durable-media handoff,
the manifest-only renderer, the takeover identity, and the channel
separation were RATIFIED; the gate-punishing failure-counter semantics and
the vision-QA/showrunner mascot contradiction were REPAIRED (see
`docs/SYSTEM_AUDIT.md`, fourth pass). That was an emergency with the author
out, done with notes and rollback instructions — it does not move the
line. The rule above stands.

## The DOCTOR — ChatGPT reads the code, Claude decides (docs/DOCTOR.md)

Operator ruling 2026-08-05. ChatGPT reads this repo **line by line** and
files findings — bugs, small fixes, a short-term plan, a long-term plan —
into `doctor/reports/<date>.json`. Claude rules on each one in the
operator's own vocabulary (`doing` / `not_doing` / `later` / `in_progress` /
`done`) and builds what it accepts. **Nothing here is ever applied
automatically**; `doctor.yml` only writes the evidence pack and validates
incoming reports.

- This is NOT the retro loop. Retro reads *analytics* and proposes one day's
  experiment; the doctor reads the *code* and maintains a standing backlog
  with a lifecycle. Separate queues on purpose — one is judged by a metric,
  the other by reading code. They share the refusal list, **imported** from
  `review_proposals.py`, so they can never drift on what is unacceptable.
- **Verdicts are durable and keyed on what a finding TOUCHES**, never on
  wording. A reviewer re-reading the whole repo daily will otherwise re-file
  what you killed last week in new words, and a file that repeats itself is
  a file nobody opens. `evidence.json` publishes every settled ruling back
  to ChatGPT; a re-file needs `new_evidence_since` naming what changed.
  `tests/test_doctor.py` proves the reworded-refile case specifically.
- Always give a real `--because` when ruling. It is quoted back to the
  reviewer; a bare "no" just gets re-argued.

```bash
python scripts/doctor.py backlog --state new     # waiting on a decision
python scripts/doctor.py next                     # what to build
python scripts/doctor.py rule <sig> doing --because "..."
```

## Self-repair — the daily session that fixes recurring defects (docs/SELF_REPAIR.md)

Operator, 2026-09-26: *"we can't be babysitting every little video."* A
Routine starts a fresh Claude session every afternoon (after the day's posts)
that reads the verdicts, groups them into CLASSES of defect, fixes the most
frequent one in code with a test that fails on the old code, and ships it
through an auto-merging `claude/self-repair-<date>` PR, with a note in
`self_repair/<date>.md`. It never touches the protected and operator-review
files named in `scripts/review_proposals.py`, and never lowers a bar. If you
are an interactive session, read the last few `self_repair/` notes before
starting on the same verdicts.

## The retro loop — self-review that PROPOSES, never applies (retro/README.md)

Daily at 23:15 UTC (`retro.yml`), `scripts/build_retro.py` writes an
evidence pack to `retro/<date>/brief.json`: every video posted today scored
as a **percentile against videos of the same age** (raw views flatter a
2-hour-old short), 7/30-day windows, pipeline health, and recent commits.
A reviewer (ChatGPT) reads it and writes proposals into
`retro/<date>/proposals/`.

- **Nothing in `retro/` is ever applied automatically.** No workflow reads a
  proposal and edits code. That separation IS the safety model — a test in
  `tests/test_retro.py` fails if a workflow ever touches proposals without
  going through the triage.
- `scripts/review_proposals.py` **hard-refuses** the whole class of "make
  the numbers go up by lowering the bar": weakening the showrunner, pruning
  a posted log, relaxing the punch-up guard / placement gate / media
  verification, more volume via a lower bar, deleting a test, fabricating
  data. A refusal is policy, not a score — a well-argued, well-evidenced
  violation is still refused. Proposing STRONGER gates is always allowed.
- Load-bearing files land in `requires_operator`; the rest are ranked by
  evidence strength. A human decides what ships.
- The brief is deliberately honest about noise: `thin_bands`, "too young to
  judge", and "this channel is small — single-digit views are mostly
  noise". A retro that launders noise into a mandate is worse than none.

## Storage rules (from the audit — docs/STORAGE_AUDIT.md)

- Never commit media (mp4/png renders) or files >256KB to git; `state/` is
  for small JSON only. Renders die with the runner; previews go to the
  `preview-renders` orphan branch or artifacts.
- Posted logs (`state/*_posted_log.json`) are sacred append-only dedupe
  state — losing an entry means a duplicate upload.
- **An upload is claimed ON MAIN before the API call, or it does not
  happen** (2026-10-02, operator: *"why do we keep reposting the same
  videos?"* — seven trending titles were live twice). Both channels push
  a claim before `videos.insert`; if that push fails the upload is
  REFUSED (`ClaimNotDurable`), never attempted on a ledger a queued run
  cannot see. What those days left on the channel is listed and, only on
  an explicit DELETE, removed by `scripts/youtube_duplicates.py` (the
  manual-only "YouTube duplicates" workflow). Run it dry after any day
  with two daily runs.
- **The same STORY under a new title is a repeat too** (same ruling:
  *"those landline videos"* — mobile-vs-fixed-lines shipped as four titles
  on two channels). `shared/near_duplicate.py` is the ONE guard: the
  explainer's near-duplicate title check (moved there, held equivalent),
  two shared subject nouns, and a text brain shown the posted titles
  ("the same story, or NONE"; fails open and says so). The corpus is
  every DATA channel's uploads inside the registry's
  `no_repeat_subject_days`; it runs at promotion, in the brief's
  `do_not_repeat`, at the renderer's package load and before an
  explainer render. Refusals name the video they repeat.
- Do NOT open PRs from `claude/*` branches casually: `auto-merge.yml`
  squash-merges any non-draft `claude/*` PR with no review.
- **A session that keeps working on one branch must REBASE before every PR.**
  Auto-merge SQUASHES, so the commit that lands on `main` is a different
  object from the one on your branch. Keep committing on the same branch and
  the next PR carries the already-merged commit as well, `mergeable_state`
  comes back `dirty`, and the conflict is in a file you never touched twice.
  It has cost this repo several cycles under three different names. The fix
  is the same every time and takes ten seconds, so do it as a habit rather
  than as a diagnosis:

  ```bash
  git fetch origin main
  git checkout -qB <branch> origin/main && git cherry-pick <your new commits>
  git merge-tree --write-tree HEAD origin/main >/dev/null; echo $?   # 0 = clean
  git push -f -u origin <branch>
  ```

  Force-with-lease is safe here precisely because what you are dropping is
  history `main` already has. If the branch carries UNMERGED commits beyond
  it, keep them — cherry-pick them onto the new base instead of discarding.
