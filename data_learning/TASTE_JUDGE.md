# THE TASTE JUDGE — the arbiter that watches the pixels and refuses soulless

The metric gates (novelty, dull, variety, cool) are **necessary, not sufficient**.
They measure whether pixels *change* — not whether the video has a *soul*. A reel
of clean infographic cards on a starfield passes every metric and is still dead
on arrival. This judge exists because that shipped, and it never should have.

The TASTE JUDGE is a **ledger-blind vision judge**: it sees only the rendered
pixels (a timestamped contact sheet + begin/mid/end frames + the low-res clip),
never the code, the story, the intent, or the beat names. It answers one
question a human answers in one second: **would anyone actually watch this, or is
it a soulless automated infographic?** It runs as the **TOP gate** — above every
metric — and its REJECT overrides any metric PASS.

## The one-second test

Show the contact sheet to someone with no context. If their honest reaction is
"that's a chart / a slideshow / a data widget / boring / empty / lifeless," it
**FAILS**, no matter how much the pixels technically move.

## Automatic REJECT labels (any one = fail)

- **INFOGRAPHIC_REEL** — the video is mostly (or entirely) data-cards: counters,
  bar charts, box grids, stat plates, title/quote cards. This is the #1 killer.
- **NO_CHARACTER / NO_SOUL** — nothing on screen has personality: no character,
  no living scene, no acting, no point of view. Just shapes and type.
- **SAMENESS** — the same background / composition / register for most of the
  runtime (e.g. everything on the same dark starfield; one layout held 10s+).
- **EMPTY_COMPOSITION** — vast dead space, a few small elements floating; reads
  as a template with the content not filled in.
- **BORING / LOW_ENERGY** — nothing makes you want to keep watching; no escalation,
  no surprise, no wit, no motion that *means* something.
- **CARDS_OVER_BUDGET** — clean data-cards exceed ~35–40% of runtime (see the
  composition budget). Cards are the seasoning, not the meal.
- **CHEAP_TYPOGRAPHY / UI_WIDGET** — looks like a slide deck, a dashboard, or a
  default motion-graphics template.

## Required to PASS (all of them)

- A clear **primary subject with personality** in most beats — a character, a
  living scene, a real place/thing in motion — not a chart.
- **Variety of register** — the video does not look like one template repeated;
  backgrounds, framing, and treatment change with the story.
- **Data-cards are the minority** (≤~35–40% of runtime) and land as punctuation,
  not as the spine.
- **≥1 memorable frame** — a shot you'd stop scrolling for.
- Every beat earns its place: if a beat is a card that just states a number, ask
  "why isn't this a scene?" — a bare stat plate must be the exception.

## The palette the personality comes from (author these, not more cards)

1. **Character vignettes** — a figure (the channel mascot or a clean pictogram
   person) *acts the idea out*: sleeps as years tick by, hunches at a desk, gets
   pulled into a glowing phone, walks toward a horizon. Character = soul.
2. **Animated scenes / objects** — a bedroom, a desk stacking up, a phone
   swallowing a life, a candle burning down, a room that reacts. Environment with
   motion and mood, not a chart.
3. **Real footage & photos** — cinematic real-world imagery of people/life,
   full-frame with a matched move, as a deliberate cut (never a pasted rectangle).
4. **Data-cards** — the counters/grids/bars/statements. Excellent, but a *minority*
   treatment that punctuates the scenes above.

## How it runs

`scripts/visual_judge.py <render.mp4> --out <pkg>` builds the blind package (this
also runs automatically inside `pro_render`, writing to `<out>_pkg/`). The verdict
is rendered by a **fresh vision subagent** given ONLY the package and this rubric
(no code, no intent). It returns:

    {"pass": bool, "reject_labels": [...], "card_fraction_estimate": 0.0-1.0,
     "personality": 0-5, "one_line": "...", "worst_beat": "…", "fix": "…"}

`pass` is true only with **no reject label** and **personality ≥ 3**. The director
loop treats a REJECT as a hard stop (like a stale span): it is an **authoring**
failure — re-author the beats toward the palette above, do not tweak a metric.

The subagent's object is serialized by **`scripts/judge_verdict.py <out.mp4> -`**,
which validates it against this contract (known labels only; personality 0-5; a
supplied `pass` must agree with the rule) and writes `<out>_pkg/verdict.json`.
`scripts/produce.py` reads that file and **fails closed** when it is absent — a
film is never promoted unjudged.

## Why this is the top gate

Retention and reputation are decided by whether the thing has a soul, before any
metric matters. A video that passes every metric and fails taste is exactly the
failure this document exists to prevent. Taste first. Metrics second.
