# The data machines

> Speed becomes motion. Imbalance becomes weight. Progress becomes distance.
> Capacity becomes fill. Rank becomes position. A gap becomes literal space.
> ... data has physics.
>
> — operator direction, 2026-09-07

This is the registry of every picture the explainer channel can draw, what
each one CLAIMS, and how the router decides which one a beat gets.

The one-line version: **the channel picks its picture from what the data is
SAYING, not from a chart name.** A chart is the fallback, not the default.

```bash
python3 -m unittest tests.test_data_has_physics -v   # the whole contract
```

## How a beat gets its picture

```
insight ──▶ relationships.classify()  ──▶ a RELATIONSHIP (or OTHER)
                                              │
                    studio_render._MACHINES ──┘
                                              │
                     ┌────────────────────────┴──────────────┐
                     ▼                                       ▼
              a MACHINE that fits                  nothing fits: OTHER
        (viz_scene.<name>_scene builds it)        ──▶ draw an honest chart
                     │
                     ▼
        viz_scene._MACHINE_DRAW[kind] draws every frame
```

Three files, and each does exactly one thing:

| file | job |
|---|---|
| `data_learning/relationships.py` | reads the insight, returns ONE relationship. Pure, no rendering, never raises. |
| `data_learning/studio_render.py` | `_MACHINES` maps a relationship to machines, best first. |
| `data_learning/viz_scene.py` | `_MACHINE_DRAW` draws them. One dispatch table, so registering without dispatching is impossible. |

`scripts/story_forge.py` publishes the same list to the story brain as the
ELEMENT KIT, so what the brain can compose and what the renderer can draw
cannot drift apart.

## The four rules every machine obeys

**1. The relationship is a CLAIM, drawn at 200pt.** `share` says these are
parts of one whole. `bottleneck` says one step is the culprit. `forecast`
says nobody measured this. Getting it wrong does not make an ugly picture, it
prints a confident wrong sentence — this channel once shipped "2019 IS 9% OF
THE WHOLE" over a run of mortgage rates. Every classifier refuses when
unsure, and OTHER is always an acceptable answer.

**2. Where the shape is ambiguous, the CLAIM decides — not the numbers.**
A set of stages that shrink is a funnel, a ranking, a bottleneck, a supply
chain and a set of sorting bins all at once by shape alone. A probability and
a share are both "23%". A projection and a measurement are both a point on a
line. Every classifier for those requires the language and falls through to a
plain ranking without it.

**3. Motion has to be MEASURED, not asserted.** The cadence gate samples the
finished video at 24fps and takes the max over 12×12 blocks of the mean
absolute change; a run of 45 near-identical frames fails it. A slow glide
across a whole visual is a sub-pixel change per frame and reads to the gate as
a freeze — the hurdle, the tower, the bottleneck, the chain and the chairs all
measured as frozen while being geometrically perfect. `MotionMustBeVISIBLE`
in `tests/test_data_has_physics.py` renders 120 frames of every machine and
diffs them with the gate's own detector. Ceiling 35.

**4. One easing curve.** `viz_scene.settle()` — `0.72r + 0.28(1-(1-r)²)`, end
slope 0.75. Four machines rolled their own ease-out and all four asymptoted
into a still frame at the end. No machine may define another.

## The registry

## How a machine reaches the screen

Built is not the same as used. On 2026-09-07, with all 42 machines wired,
documented and tested, they were reaching almost no beats — the wiring was
right and the path was blocked three times over. What the path is now, and
what each gate was doing:

1. **The authored scene, if it can actually be DRAWN.** `validate` asks
   whether a scene is well formed; that is not the same question. Of the 933
   configured explainer beats, 550 carried a scene that validated, was
   honoured, and then bailed at draw time to a fallback chart because it was
   image-only and the channel runs with images off. `viz_director._renders_here`
   asks the second question.
2. **...and only ONCE, if it is a generic one.** A bespoke scene is distinct
   by construction; a lone `timeline_axis` is the same line with different
   numbers, and 122 beats are authored that way. The first keeps the author's
   choice, the rest fall through — which is the showrunner's own 2026-08-24
   finding ("three near-identical chart layouts stretched over 96 seconds",
   scores 26-52) fixed at the source.
3. **Otherwise the MACHINE, chart after it.** `_deterministic_candidates` now
   leads with `_machine_candidates`, which asks the same router this document
   describes and asks each builder whether it can serve this data. Appending
   them after the beat's chart — which is where they started — made them a
   tie-breaker on a repeated line chart, not a library.
4. **`bubbles` terminates the list**, so a beat is never left without a
   depiction.

Measured over the same 933 beats after the change: **77% lead with a machine**,
16% keep an authored scene that genuinely renders, 7% are charts and maps
(place data is always better as a map).

Three things that only broke once a machine was a beat's FIRST visual, all
now held by tests:

- **The anchor contract.** Machines return the charts art-spec tuple
  `(value, "art", x, y)`; the scene kit's anchors are dicts. Invisible while
  machines were a second visual, because that path does not resolve anchors.
  Normalised in `_as_anchor`, at the one place anchors are collected.
- **Two mascots.** Every machine draws the host itself. `render_scene` named
  `timeline_axis` alone as host-baked, so the travelling overlay would have
  put a second one beside every machine. `_SELF_HOSTING` is the set, checked
  against the source in both directions.
- **The sprite was 55% padding.** `scene_host` returns a 300x300 raster with
  the host occupying 134x210 of it. Machines size him by height and anchor to
  that box, so he came out a third small and `burden` drew its load floating
  in clear air above his head. Cropped to the content bbox — one fix for all
  forty.

### What the LIVE QUEUE actually classifies as

Measured, not guessed, over all 1,089 datasets in `data_learning/data/` on
2026-09-07 (`relationships.classify` on each; baselines are not loaded by the
sweep, so `threshold` and `gap` are undercounted here and fire normally in
production):

```
duel          429  39.4%      probability    10   0.9%
rank          201  18.5%      reversal        7   0.6%
growth        135  12.4%      retention       6   0.6%
dominance     108   9.9%      spread          6   0.6%
before_after   47   4.3%      density         4   0.4%
decline        39   3.6%      buying_power    3   0.3%
burden         28   2.6%      in_out          2   0.2%
volatile       27   2.5%      routing         2   0.2%
other          16   1.5%      acceleration / duration / dropoff /
share          13   1.2%      stable / bottleneck / scarcity   1 each
```

Two things worth reading off that. **The base set carries the channel** —
duel, rank, growth and dominance are 80% of it, which is why those four have
the most machines and why `_ROTATABLE` covers them. And **the long tail is
real but thin**: a relationship at 0.2% still fires several times a year, and
when it does it gets the picture that says the thing rather than the sixth
ranked bar chart in a row.

Nothing in the tail is dead code. Every machine below is reachable two ways:
the router when the data says so, and the story brain composing directly from
the ELEMENT KIT, which lists all of them. `forecast`, `correlation`,
`tradeoff`, `chain`, `scale` and `record` do not appear in the sweep because
the World Bank queue does not phrase claims that way — they are reachable
today through the brain, and through the router the moment a source does.

### Trend and comparison — the base set

| relationship | machines, best first | says |
|---|---|---|
| `rank` | `race_scene`, `units_scene`, `orbit` | rank is position, the gap is distance |
| `duel` | `balance_scene`, `race_scene`, `units_scene` | two things, weighed |
| `before_after` | `tower_scene`, `fill_vessel`, `balance_scene` | one subject, then and now |
| `growth` | `staircase_scene`, `tower_scene`, `timeline` | it rose, and the rise is the point |
| `decline` | `elevator_scene`, `timeline`, `fill_vessel` | it fell, past labelled floors |
| `volatile` | `spotlight_scene`, `coaster_scene` | it moved around and claims NO direction |
| `share` | `rate_scene`, `pipes_scene`, `fill_vessel` | parts of one countable whole |
| `rate` | `gauge_scene`, `rate_scene` | a needle, not a quantity |
| `burden` | `burden_scene`, `staircase_scene`, `balance_scene` | a cost, as weight he carries |
| `dominance` | `skyline_scene`, `units_scene`, `balance_scene` | one dwarfs the rest |
| `threshold` | `hurdle_scene`, `balance_scene`, `units_scene` | a line it has to clear |
| `dropoff` | `funnel_scene`, `race_scene`, `units_scene` | stages, each smaller |
| `frequency` | `conveyor_scene`, `gauge_scene` | a count PER unit of time |

### Batch 1–2 — shape of a series

| relationship | machines | says |
|---|---|---|
| `stable` | `road_scene` | it barely moved, and that IS the finding |
| `delta` | `tape_scene`, `tower_scene` | the SIZE of a change, as distance |
| `gap` | `bridge_scene`, `hurdle_scene` | how far SHORT of a line it falls |
| `centre` | `centre_scene`, `race_scene` | where the middle of a spread sits |
| `acceleration` | `staircase_scene`, `tower_scene`, `coaster_scene` | it is compounding, not merely rising |
| `reversal` | `coaster_scene`, `spotlight_scene`, `elevator_scene` | it turned, and stayed turned |
| `spread` | `darts_scene`, `units_scene` | they are all basically the same |
| `cycle` | `wheel_scene`, `coaster_scene` | it REPEATS — stronger than volatile |
| `queue` | `queue_scene`, `units_scene` | a backlog, growing |
| `uncertainty` | `spotlight_scene` | the range it lived in |

### Batch 3 — the flow family

Every one of these is a plain ranking by shape alone. All five require the
claim language.

| relationship | machines | the picture |
|---|---|---|
| `bottleneck` | `bottleneck_scene`, `funnel_scene` | a pipe that PINCHES at the one step doing the damage, marked "here". Free to widen again after the pinch — the shape a funnel cannot draw. |
| `retention` | `leaky_scene`, `funnel_scene`, `rate_scene` | a bucket that starts FULL and drains to what was kept. Filling up to the retained share animates the wrong event: nobody joined. |
| `in_out` | `inout_scene`, `balance_scene` | two pipes and a tank; the LEVEL is the surplus or the shortfall, a third number neither bar shows |
| `routing` | `sorter_scene`, `pipes_scene` | parcels dropped into labelled bins — where it WENT, not what it is made of |
| `chain` | `chain_scene`, `conveyor_scene`, `funnel_scene` | links thick as their value, the weakest a thread marked "it breaks here" |

**Funnel vs bottleneck is decided on per-stage SURVIVAL RATES, not raw drops.**
A hiring funnel's biggest drop is its first one (1,000 → 380 → 95 → 41) and it
is a funnel, because every stage bleeds. A bottleneck is the shape where the
others do not: 12,000 → 9,800 → 2,100 → 1,700 → 1,500 keeps ~80% at every step
but one, which keeps 21%.

### Batch 4 — the uncertainty family

| relationship | machines | the picture |
|---|---|---|
| `probability` | `spinner_scene`, `doors_scene` | a wheel whose lit slice IS the chance. It never LANDS — landing shows an outcome nobody measured. The doors are the same claim told long, for a real "1 in n" up to 50. |
| `forecast` | `fan_scene` | measured points solid, then a widening cone, with the line where the data stops drawn and labelled. The x axis is spaced by YEAR. |
| `correlation` | `gears_scene`, `balance_scene` | two meshed gears. The caption is "they move together" and never "drives" — a gear train looks like causation if you let it. |
| `tradeoff` | `slider_scene`, `balance_scene` | one track, two ends, one handle: every unit of one is a unit of the other you did not get |

A chance is not a share. `dot_field` lights 23 figures in 100 and asserts a
population you could count out; "a 23% chance" is one trial. Same number,
different claim, and only the words separate them.

A forecast needs BOTH the word and a tail dated well past the measured points.
Forecast language over a run of measurements is just a writer being loose.

### Batch 5 — the physical comparisons

| relationship | machines | the picture |
|---|---|---|
| `density` | `density_scene`, `rate_scene` | the SAME square twice, packed differently. The box never scales — scaling it as well as the packing double-counts the difference. |
| `scale` | `nest_scene`, `skyline_scene` | the small thing tiled inside the big one until it fills it. The tile COUNT is the ratio, never the full grid: filling the square exactly draws 81 tiles for "76 times over". Refuses below 1.5× and above 150×. |
| `scarcity` | `chairs_scene`, `queue_scene` | more people than seats, with somebody always walking up and being turned away |
| `duration` | `hourglass_scene`, `tape_scene` | sand, and the PILE LEFT AT THE BOTTOM is the number. Draining the short wait faster is true of a real hourglass and useless: both end empty, so the final frame shows no difference. |
| `record` | `trophies_scene`, `units_scene` | one cup, one title. Refuses above 30 — too many to count is not a shelf. |
| `buying_power` | `basket_scene`, `units_scene` | two baskets filled from the same note. The price is never the story; what is left in the basket is. |

### Batch 6 — the unit says what kind of quantity this is

Measured over the 1,104 live datasets on 2026-09-08, **`duration` classified
exactly one of them** — while 106 are published in years, hours or days, 60 in
miles or feet, and 30 in mph. The hourglass was built, wired, documented and
tested, and it was leading roughly one beat in a thousand. Meanwhile 80% of
the queue came back `duel` / `rank` / `growth` / `dominance`: four
relationships sharing five machines.

The cause was that every specialised relationship was detected from the CLAIM
alone, and a dataset title says *"Maximum recorded lifespan by animal
(years)"*, not *"how long"*. **A unit is not an inference about the data the
way a claim is — it is a declared property of the measurement, published by
the source.** A pair of numbers whose unit is HOURS is a comparison of
durations whatever the headline calls it.

| relationship | machines | the picture |
|---|---|---|
| `speed` | `race_scene` | a speed is ALREADY motion, so it is run rather than drawn: the lanes are the encoding and the fastest is furthest |
| `distance` | `race_scene`, `tape_scene` | a distance is ALREADY a span, and the race encodes value AS distance travelled — the one picture that needs no translation. The tape is second because "how far apart" is a different sentence from "which is further". |

The unit rules run LAST among the specialised checks, so an explicit claim
still wins: "for every opening" still reaches scarcity and "what it buys"
still reaches the basket, whatever the numbers are measured in.

Four refusals hold them honest, and each one is a case that was on screen:

- **A date is not a duration.** "Deadliest pandemics" is published in years
  and its values are 1350 and 1918. Whole numbers that all sit inside the
  range people write dates in are treated as dates.
- **A height is not a journey.** "Tallest buildings" and "deepest point" are
  also measured in feet, and a tape laid out flat is the wrong picture for
  both. Vertical claims are left to the skyline, which `dominance` and `rank`
  already reach.
- **A runaway leader is not a race.** Lightning at 270,000 mph against a
  peregrine at 240 is the broken chart `race_scene` warns about in its own
  docstring, so dominant sets keep the skyline. `_dominant` is defined once
  and used by both.
- **Durations route in PAIRS only.** The hourglass draws two glasses and the
  tape has two ends; a six-item duration ranking sent there would silently
  drop four rows.

Concentration in the top four relationships: **80.3% → 70.7%.** `duration`
1 → 54, `speed` 0 → 27, `distance` 0 → 32.

### A machine may not accept rows it will not draw

Every draw function slices its items — the hourglass takes two, the sorter
four, the chain five — and the builders accepted any number, so the extras
went to a slice that dropped them silently. **Two of six waits drawn as "the
comparison" is not a rough picture of the data, it is a different
comparison**, and nothing downstream could see it happen.

`_machine_scene(kind, need, cap)` now carries the range a machine can honestly
draw, and it is set only where the picture claims to show the WHOLE set:
pairs, funnels, chains, routes, compositions. A ranking machine like the
skyline is left uncapped on purpose — the top seven of twelve cities is an
editorial trim every ranking makes, and it reads as one.

`_spread_ok(insight, limit)` is the other half: a machine that encodes value
as SIZE refuses a ratio it cannot show. "Distance to the Boomerang Nebula vs.
the ISS" is 2.94e16 miles against 250, and any machine that draws a length
draws the second at zero pixels — a frame that says the ISS is nowhere. The
race stands down past 500:1, the hourglass past 60:1. A genuine zero is
allowed through the race (a runner on the start line is readable and is what
the number says) and refused by the hourglass (an empty glass is
indistinguishable from a finished one).

## Staging: the same machine, arranged differently

The router fixed WHICH picture a beat gets. It did not touch HOW that picture
is composed — and `race_track` alone is 195 of the 930 configured beats, drawn
with the identical layout every time until 2026-09-07. A library of 42 rigid
pictures is a bigger template than a library of six, not a smaller one.

`viz_scene.stage(insight, kind)` returns every staging choice for one machine
on one story, keyed on the topic so it is deterministic (a re-render is
identical) and different per story. Machines read it in a line.

**The rule that makes it safe: staging may change how a machine is ARRANGED,
never what it CLAIMS.** The value-to-geometry mapping, every number, every
label and every caption are identical across variants. What varies is framing
— which lane the leader runs in, which side the host watches from, whether
there is a ground line, what shape the moving product is.
`tests/test_machines_are_pliable.py` renders the same insight at every variant
and fails if a single drawn number moves.

Two things it must never touch, and a test holds each: a machine that walks
through TIME ignores `flip` (time runs one way), and an ordering that IS the
ranking is not free to reverse — a race's lanes are arbitrary, a sorter's bins
are not.

## Looking at a machine: use the real path

Two things cost an hour each on 2026-09-07 because a preview harness lied,
and both lies pointed the same way — at a machine that was fine.

- **Draw onto a TRANSPARENT layer and composite it over the background**, the
  way `render_scene` does. Drawn straight onto an opaque canvas every
  semi-transparent fill looks solid: the wheel's A-frame read as a bright
  white wedge and is actually a 24% wash.
- **Go through `render_scene`, do not call a draw function directly.** The
  icon-bearing elements get their cut-out loaded by the renderer, so calling
  `draw_unit_figures(..., cutout=None)` renders 24 plain discs — which is
  exactly what "the isotype has no object" would look like if it were real.
  The machine was drawing houses the whole time.

Both times the harness said a good machine was broken. Check the harness
before changing the machine.

## What the reviewer keeps blocking, as numbers

The showrunner watches every video and its notes are consistent enough to be
turned into deterministic checks. Each of these was one cause, not a hundred:

| its words | the cause | now |
|---|---|---|
| `empty_void` — "the entire lower two-thirds blank blue gradient" | `RBOT` was 1180 of 1920, "above the game strip", a layout this channel has not had for years. 158 configured scenes have >1 element and every one drew in the top 61%. | `RBOT` 1560; `shared/frame_occupancy.py` measures coverage and the largest empty band; `tests/test_the_frame_is_used.py` holds every machine under a 34% ceiling |
| `bare_number_card` — "a giant '51,863' on an empty dark field with a decorative unlabeled arc" | `draw_gauge` set its full-scale value to `abs(v) * 1.35`. That is not a scale, it is the reading scaled — so 51,863 and 3 and 0.02 all put the needle at 74% of the sweep, the arc carried no information whatever, and the picture was a number with a ring behind it | the scale must be REAL: an explicit baseline, else 100 for a percentage, else the machine declines the beat. Both ends and the quarter ticks are drawn. `gauge_scene` refuses exactly what `draw_gauge` refuses; `tests/test_a_dial_needs_a_scale.py` renders three readings and asserts the needle lands in three places |
| `bare_number_card` — "the number is stated, not demonstrated" | `draw_timeline` reached its rising filled area only when every item carried a `period` field, and fell back to a hairline ruler without one. The items were labelled 2007..2025. | the label IS the period when it is a year — coverage 5.4% → 35.5% on the blocked data |
| `junk_imagery` — "a cartoon HOUSE icon sits on the 'Current record' bar" | `icons.emoji_codepoint` matched `key in label.lower()`, so cur-**RENT**-record picked up the housing key and "intensive **CAR**e" the vehicle one. This is the ONE fatal check — it blocks at any score on any policy — and it took six renders of `f1-pit-stop-vanishing-act` in a week plus `melatonin-kids-er-surge`, every one a story that did not post | a key must be a prefix of a whole TOKEN with only a plain inflection left over (a key of six or more may be a deliberate stem: `vaccin`, `immuniz`, `agricultur`); `tests/test_the_icon_must_be_about_the_label.py` pins the quoted verdicts as named cases |
| `decorative_mascot` — "the same arms-out pose in five beats" | `viz_director` already picks a different performance per beat; the renderer's `_act()` threw it away and asked a map keyed on CHART KIND, where bars/comparison/rank all mean `push_bar` — and `scene`, which is every machine beat, was absent entirely | `_act()` honours `perf_spec`; `scene` has its own default |
| `decorative_mascot`, still — "in every scene Data only stands ... holding a clipboard and slides a few pixels" | the SCENE kit was not directed at all. `compose_anim` does `ANIMATORS.get(action, _a_carry)`, and of the six names the kit used only `cheer` and `climb` were animators — `point` (18 machines), `strain` (9), `think` (3) and `shock` (1) all fell through to one carry pose, **31 of 41 call sites rendering a pixel-identical sprite** whose whole motion is a 4px sway. `"prop": "none"` was not a key in `PROPS` either, so `PROPS.get(name, price_tag)` gave him a blank yellow price tag to hold — the "clipboard" in the verdict | `viz_scene.SCENE_ROLES`: a machine names a ROLE (a contract about the silhouette its layout was built around), `scene_act` picks the performance inside it, rotated per story so five beats are five acts. `PROPS["none"]` draws nothing. `tests/test_the_mascot_is_actually_directed.py` renders the roles and compares arrays |

**Both mascot rows are the same lesson twice.** A vocabulary resolved with
`dict.get(name, default)` and never checked against its own table is a
capability that quietly does not exist. It cost `decorative_mascot` 147 of
this channel's 228 verdicts and `junk_imagery` 63 more, and in both cases the
showrunner described the defect precisely, for weeks, while every test passed.
When you add a name to any of these tables — an act, a prop, an icon key, a
machine kind — **add the test that says it resolves**, in the same change.

**A helper used for a case it was not written for is the third form of the
same bug.** `_stagger`'s `0.8` overlaps CONSECUTIVE elements so the next one
is already moving; with a single element there is nothing to overlap with, and
paying the fifth anyway truncated every scene beat to 80% of its span. A beat
IS one machine now, so that fifth was a held, finished picture — and the host
was pinned to it too, because the scene kit drives him from the element's
reveal and `charts._beat()` (which exists for exactly this) never crossed the
fence. Every one of this channel's 33 `temporal_gate` blocks is a frozen run
in the closing seconds. Longest frozen run over a 60-frame build, before and
after: gauge 14→0, funnel 12→0, staircase 8→0, tower 25→7, nest 12→7,
pipes 4→2.

**The CHART path is the other half of the render and it had none of this.**
`viz_scene` got `fit_text` and a de-collision pass; `charts.py` had no text
fitting at all, so every long label was drawn at its nominal size and simply
overlapped whatever was beside it — "axis labels truncated mid-word ('1963
(all', '2006 (yea')", two labels "printed over each other into unreadable
mush". `_fit_fontsize` + `_axes_pts` are the matplotlib-side equivalent; the
estimate is deliberate (monotonic in length, no renderer needed, and erring
small costs a point of type where erring large costs the label).

Two more came out of the same render, and both were one unaccounted-for
number. **A round cap overshoots its datum** by half a linewidth — a tenth of
the axes height on a 165pt column — so the tallest bar was drawn across the
subtitle and ate it ("MASSACH[ ] VS MISSISSIPPI"), which reads as the mascot
occluding text and is not the mascot at all. And **time must run left to
right**: `insights._comparison` sorted a pair by magnitude, so a
then-and-now was drawn newest-first and the bald eagle's 417→71,467 comeback
rendered as a collapse under the words "one of the biggest wildlife
comebacks". Two PLACES may be ordered by size; two DATES may not.

**Measure with the FURNITURE.** The studio draws the title near the top and
burns the caption near the bottom of every frame, so measuring a bare machine
over-reports the void at both ends — the first sweep flagged ten machines that
are fine in production. Only a gap still empty with the title and caption
present is real.

**And measure again WITHOUT it, inside the box.** A band is only as long as
the first thing that interrupts it, and the furniture interrupts everything.
The burnt-in caption at y≈1690 and the progress rule at y≈1860 sit inside the
bottom void of a short picture and cut it into pieces, none of which reaches
the ceiling: a machine that stops at 55% of the frame height scores 24% on the
composite while a viewer sees the bottom half as empty gradient. Measured
2026-09-09 across the whole kit, **not one machine exceeded the composite
ceiling and ten exceeded 22% inside their own box** — queue 33%, basket 32%,
spotlight 32%, bridge 26%, road 26%, trophies 26%, hurdle 26%, density 25%,
slider 25%, wheel 22%.

So there are two questions and they need two calls.
`fo.verdict(frame, max_void=0.34)` over the whole composited frame asks *is
this frame acceptable*; `fo.measure(layer, top=RTOP, bottom=MACHINE_BOT)` with
only the title composited asks *did the machine fill the space it was given*,
under a 24% ceiling. The second is the one a machine can be TUNED against,
because its answer does not depend on furniture the machine never drew.
`fo.measure` also reports `head` and `tail` separately: a tail is a picture
that stopped early, a head is one that started late, and an interior void is
two pictures with a gap between them. Three defects, three different fixes.

What the ten fixes actually were, because the pattern repeats: **the picture
grows to fill the box** (the queue sizes each person from the count the beat
ends on; the trophy shelf wraps into a grid and the cup stays a cup instead of
becoming a 22×96 tally mark), **the picture stands on the floor** (the ferris
wheel, the bridge's chasm), or **the thing the caption is about gets drawn
where it is** (the hurdle's margin as an arrow between the two lines it names,
the bridge's missing piers as ghosts in the gap). Only one needed a new
element: the spotlight's lane says "somewhere in here" and says nothing about
the wandering, so the series itself is drawn above it — value across, time
down — which is what "it never settled" looks like rather than an assertion
that it did not.

## Say the number the picture shows

`shared/beat_match.py`. Over the 858 configured beats that speak a quantity,
84.5% have their headline number on screen. The 15.5% that do not fail the
same way every time — the writer converts the measured figure into a bigger
one the data does not contain ("34 percent — 2.6 billion people" over a chart
of percentages), and the viewer hears a number they cannot find.

It is an authoring fault, so the story forge feeds it back to the brain inside
the retry loop it already has, and the prompt states the rule up front. A
difference, a percentage change, a share of the total and a unit rescale all
pass — only a number from nowhere fails, and only for the LOUDEST number in
the line.

## What is deliberately NOT built

- **A network / subway map.** It needs edge data — who connects to whom — and
  every source this channel pulls from returns a flat list of labelled values.
  A network drawn from a ranking would be inventing the edges, which is the
  one thing no machine here does. It goes back on the list the day a source
  returns pairs.
- **A correlation over two SERIES.** `gears_scene` draws two co-moving
  quantities from two values. Two full series through time would be a better
  picture and the `Insight` shape carries one list of items, so it is a data
  change before it is a rendering one.
- **`energy`, `pursuit`, `territory`** from the original list. `pursuit` is
  `race_scene` under another name, `territory` is `nest_scene`, and `energy`
  never resolved into a claim distinct from `burden`. Three names, no new
  pictures — building them would have grown the registry without growing what
  the channel can say.

## Adding one

1. **A relationship, or none.** If an existing one already says it, you are
   adding a machine to that relationship's tuple, not a relationship. Two
   names for one claim is how a registry rots.
2. **Classify from the CLAIM where the shape is ambiguous**, and add the
   false-positive test first — the one that proves a plain ranking is still a
   ranking.
3. **Write `draw_<kind>`**: `(d, canvas, box, insight, color, reveal, unit)`,
   returns `(value, "art", x, y)` or `None`. **Return `None` for data it
   cannot serve honestly** — that is how a beat falls through to something
   true instead of drawing a picture whose geometry means nothing.
4. **Register it** in `_TYPES`, `_HOLISTIC`, `_DRAWN_TYPES` and
   `_MACHINE_DRAW`, add `<kind>_scene = _machine_scene("<kind>", n)`, route it
   in `_MACHINES`, and add it to `_SCENE_TOKENS` / `_SELF_HOSTED`.
5. **Publish it in the ELEMENT KIT** in `scripts/story_forge.py`.
6. **Render a contact sheet at three reveals and LOOK at it.** Every layout
   bug in this file was found by looking, not by a test: clipped labels that
   turned "Interviewed 380" into "Interviewed 3", a gear pair centred on the
   wrong width, a bucket that never moved. Look for the word REFUSED on the
   tile too — `_guarded` catches, so a machine that dies on every input in the
   catalogue silently draws a chart instead, and that is what `draw_sorter`
   did for a day while the suite was green.
7. **Never slice a label.** `fit_text(d, text, size, max_w)` returns a
   `(font, text)` pair and BOTH halves have to be used — three machines drew
   the fitted string at a hardcoded size, which measures one thing and prints
   another. `label[:12]` shipped "1990 (pre-vacc" to the channel.
8. **Add it to the measured motion case list** and run it. Not the source
   pattern — the frames.
9. **Offline only.** No network, no generated imagery. The image provider
   returns HTTP 500 at 54–89s a call; a machine that depends on it is a
   machine that is not there on the day it is needed.
