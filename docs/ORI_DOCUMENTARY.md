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
  setting and shot (`ori_author.SAME_LOOK_SHARE`), and the last chapter's
  outdoor scenes are asked for at dawn — a campfire at dawn in a close shot
  measured 0.06-0.10 held frames, alive; in a wide shot 0.52-0.63, not.

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
- Two eras are drawn (`stone_age`, `medieval`); a topic outside them waits
  for its settings and props to be added to the kit, with the tests that
  say they resolve and move.
