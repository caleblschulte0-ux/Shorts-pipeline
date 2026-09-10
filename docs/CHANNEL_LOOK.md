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
