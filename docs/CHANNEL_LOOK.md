# The channel's LOOK — one design system, held by tests

Operator ruling, 2026-09-10: *"the whole look of the thing is cheap and
shit ... we need a large scale rehaul of how the channel looks"*, and after
the first pass, *"closer but it can be even more sharp and clean and more
professional YouTuber looking"*.

The design system is `shared/look.py` and it is the ONLY place a colour, a
type weight or a mark thickness is decided. `data_learning/charts.py`
derives its tokens from it (`TEXT`, `SUBTLE`, `HIGHLIGHT`, `REST`, `GRID`,
`NAME_REST`); nothing else in the repo may name a hex for a chart.

## The rules, and the frame each one came from

1. **There is no card.** A rounded panel with a 2px border floating on a
   gradient is a UI widget, not a shot — `repair_planner` has a defect code
   for it (`UI_WIDGET`). The data sits on `look.ground`, full bleed.
2. **ONE accent per story, and it goes on the subject.** Supporting marks
   are `look.REST`, a NEUTRAL — not a desaturated accent, which reads as
   *disabled*. A 100% stacked column that handed out six categorical hues
   was the single loudest frame the channel made.
3. **Text wears INK, never the mark's colour.** `shared/palette` has said
   this in its own module docstring the whole time; `_story_versus` and
   `_story_stack` were both breaking it.
4. **The accent follows the STORY, not the draw order.** `_story_versus`
   painted `items[0]` and decided the winner by value, so every comparison
   whose bigger side is drawn second put the accent on the wrong column —
   and then wrote the winner's number in the ink chosen to sit on the
   accent. `$942B` shipped in near-black on a slate column.
5. **A mark is capped** (`look.bar_thickness`). No composer picks its own
   number; `lw = 165` was 252 pixels of saturated capsule.
6. **Type is sized FROM the row, and every extent is MEASURED.** Character
   counts are not widths; a value column is as wide as its widest value;
   a kicker that runs long is truncated, not run off frame.
7. **The kicker leads the headline.** It was a 22pt bold all-caps line in
   full-saturation accent directly UNDER the title — two headlines stacked,
   with the machine-written one carrying the weight.
8. **Real punctuation.** `_typeset` — curly apostrophes, em dashes,
   ellipses. A display headline punctuated with `'` reads as unfinished no
   matter how good the rest of the frame is.
9. **A name and its mark are ONE unit**, so the gap between them is a
   constant number of PIXELS, never a fraction of a row.
10. **`FancyBboxPatch`'s `rounding_size` is in DATA units.** On an axes that
    is 0..1 across and 0..100 up, `1.4` is wider than the whole axis: every
    stacked segment threw a pair of faint full-width streaks across the
    card. That banding was in every share frame the channel shipped.
11. **His feet are his feet.** `align=(0.5, 0.0)` only means "standing on
    it" because `_trim_floor` crops the empty rows under the sprite. Only
    the BOTTOM is trimmed — cropping to the alpha bounding box would
    re-centre him horizontally every frame and read as jitter.
12. **A host beside the mark, never inside it.** Once the marks were capped
    the host was as wide as them, so centred he was drawn *through* three
    stack segments at once — `decorative_mascot` in its most literal form.

`tests/test_the_chart_is_a_shot_not_a_widget.py` and
`tests/test_the_channel_has_a_look.py` hold all of it. Every one of these
is a defect that was visible in a rendered frame, which is why they are
tests and not a style guide.

## Worlds: the illustrated arm (A/B test, 2026-09-23)

Operator, 2026-09-23, on an illustrated 2D style sample: *"that 2D animation,
I want to start A/B testing that on the mascot channel."* The brief is
`docs/style_samples/illustrated_2d/BRIEF.md`; the renderer is
`data_learning/illustrated.py`; the split is `style_arms` on the explainer's
`data_story` format in `config/channel_registry.json`.

The illustrated arm is a new PALETTE, not new rules. Its tokens are
`look.WORLDS` and nothing else names a colour:

| World | When (topic words, `illustrated.WORLD_WORDS`) | Reads as |
|---|---|---|
| `dusk` | the default | sunset sky over layered hills, birds |
| `city` | housing, rent, jobs, teens, retail | blue-hour skyline, lit windows, street lights |
| `ocean` | sea, shipping, water, fish | water darkening with depth, rays, fish, bubbles |
| `space` | orbit, moon, satellites | twinkling stars, a planet's limb, a meteor |
| `farm` | crops, food, coffee | golden hour, field rows to the horizon |
| `industry` | energy, emissions, waste, factories | smokestacks, drifting smoke, embers |

Each world names `sky` (gradient stops), `glow`, `far`/`mid`/`near`
(terrain, back to front), `form` (lit, shadow — the NEUTRAL data marks),
`rim` and `mote`. The rules above still hold, applied to a world:

- **One accent, on the subject.** The subject's column, ridge or liquid is
  the story's accent (`charts.HIGHLIGHT`, the same one the current arm
  uses), two-tone: lit face and a shadow face at `ILLU_SHADE`. Everything
  else wears the world's `form` tones.
- **Text wears INK** (`INK`, `INK_2`), with a soft drop shadow so it reads on
  any sky. Numbers are Anton, labels Inter — registered with fontconfig by
  the module itself.
- **Nothing is ever still.** Each world carries ambient drift plus one
  strong mover (birds, fish, embers, a meteor), and Data keeps performing
  after the build lands. Measured with the machines' still-frame detector in
  `tests/test_the_illustrated_arm.py`, not asserted.
- **Every number drawn is the data's.** Decoration moves; it never adds a
  quantity. The test reads back every string the final frame prints.

### Subject scenes: the picture IS the subject (2026-09-23)

The operator, on the first illustrated renders: *"It's not just a chart on a
gradient background ... you need to be far more throwing the mascot on top
of this video than trying to drag this video into what we already have."*
So each beat is a drawn scene of the subject itself — the forest felled one
tree per 1,000 km², France dropped into the clearing, coins piled on a
scale — in `data_learning/subject_scenes.py`. Hand-drawn TEACHERS cover
three stories; for any other beat the headless brain draws one
(`data_learning/scene_author.py`) and code verifies it before it is used.

Every rule below is a check the verifier runs on a brain scene AND a test
every teacher passes (`tests/test_subject_scenes.py`,
`tests/test_the_brain_draws_the_scene.py`), and each came from a render:

- **No held frame.** temporal_craft is 3/3 only at 24 effective fps, and the
  gate samples at 24 — so 3/3 means none. A sine walk crawls into each
  turn; `walk()` is a constant-speed walk that turns sharply, and lifts
  each step fastest exactly at the turn. A Data who holds a spot (riding,
  hanging on, tracing) gets `sway()`, a circle, whose speed never drops to
  zero. Measured the way the real render is made — a 30fps clock, his pose
  looping over 120 frames, sampled at the gate's 24 — over a whole stride
  (`scene_author.held_ratio`, ceiling `MAX_HELD`): 71 held frames across
  the teachers became 0. (A 24fps harness said 2 while the real render of
  the same scenes held 11; measure on the render's own clock.)
- **Data has a BIT.** At least two acts over the beat and 150px of travel
  that is his own, not pacing (`bit_problems`). The rubric asks for
  "setup → action → payoff"; the story whose teachers failed this is the
  one the judge called decorative.
- **No repeated gesture in one video.** A role resolves to the act this
  video has used least (`act_for`), so "shock" is not the same
  hands-on-head pose in three scenes.
- **Nothing is said twice.** A subject scene prints its own readout, so the
  renderer draws no punch number on its beats (the "faded ghost 6,288"),
  and a typed `--` is a dash on screen.
- **A number stays up long enough to read** (`MIN_DWELL_S`, measured as
  its longest unbroken stretch at the scene's real length): a hook that
  cycled values every few frames was "a number that flickers too fast to
  register".
- **A readout's number and its label are the same row** — "$1.05" over
  "2025 · $4.41" is refused — and a derived number only contradicts the
  narration in the SAME unit ("4.2x" is a ratio, not a misprint of $4.41).
- **Data never covers text.** Text drawn before him must lie clear of
  everywhere he can be — his body, widened by his walk. "Text is covered in
  the hook" held an 83.
- **The captions read over any scene.** Every scene darkens softly toward
  its foot (`caption_scrim`), under the narration — a fade, not a card.
  "Subtitles lost in clouds and bricks" held a 79.
- **Full bleed.** A scene is the whole shot. Scenes inherited their
  segment's chart kind and were shrunk into the chart region with a
  border — the "inset" the judge named.
- **Data stays in frame**: his centre never comes nearer an edge than
  `EDGE`.
- **The hook and the closing are scenes of their own.** The hook states the
  story's surprise from frame 1 (not the first beat's picture); the closing
  shows the last line HAPPENING (the Amazon scar growing one ring per year,
  each ring thinner — "fewer trees fall, the bill still grows"), full bleed,
  with the line on its sky and no bordered card. Payoff went 1/2 → 2/2 on
  the same story.

**The channel aims at 90, not at the pass bar.** `quality.target` in the
registry: a cut that ships below it is still repaired — for this arm the
brain redraws the scene the judge named, from the judge's own words
(`scripts/scene_redraw.py`) — re-judged, and kept only if it scores
higher, ranked (ships, score). The gate's bar and its sovereignty do not
move. Held by `tests/test_the_channel_aims_at_90.py`.
