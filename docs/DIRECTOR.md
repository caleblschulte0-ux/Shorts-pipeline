# DIRECTOR.md — the showrunner's taste bar

This is the rubric the headless Claude **showrunner** (`scripts/showrunner_review.py`)
scores every rendered video against **before it is allowed to post**. It is the
written definition of "good" for this channel. Nothing boring or sloppy ships —
if a video fails this bar, the showrunner blocks it and says why.

The rule the whole channel exists to satisfy:

> **High-class, genuinely entertaining short animation whose job is to
> demonstrate data in the most interesting way possible.** The data
> demonstration is the star. The mascot (Data) is a real performer woven into
> it. Photos/AI images appear ONLY when they earn their place.**

If a video is not something a stranger would stop scrolling to watch and enjoy,
it does not ship. "It rendered" is not a passing grade.

---

## How the showrunner scores (0–100)

It samples frames across the video (and reads the script + the per-scene plan)
and scores six dimensions. Weighted total, plus hard auto-fail triggers.

| # | Dimension | Weight | What "good" looks like |
|---|-----------|:------:|------------------------|
| 1 | **Hook (first ~2s)** | 20 | Frame 1 is motion + a reason to stay. NOT a slow chart build, NOT a plain title card. Something happens immediately. |
| 2 | **Data demonstration** | 25 | Each number is shown the *most interesting way it can be* — a physical/visual metaphor (things stacking, filling, racing, shrinking, crushing), not a bare number on a blob. Would a smart friend say "oh, that's a cool way to show it"? |
| 3 | **Mascot as performer** | 20 | Data is IN the scene DOING a real bit tied to the content (setup → action → payoff), and he MOVES / changes position. NOT a static sticker parked in a corner. NOT gliding aimlessly. He has a reason to be where he is. |
| 4 | **Visual craft** | 15 | Clean, intentional, "professional YouTube channel" — not empty black voids, not crude splatter graphics, not amateur layout. Composition uses the frame. |
| 5 | **Pace & motion** | 10 | Always something moving with purpose. No dead holds, no 4+ seconds of the same static frame. |
| 6 | **Payoff / retention** | 10 | Builds to a punchline or "whoa" and lands it; earns the swipe-through to the end. |

**Passing score: ≥ 70.** Below that, the video is **blocked**.

---

## Hard auto-fails (block regardless of score)

Any one of these blocks the video outright — they are the "we can't let this
slide" list:

- **Irrelevant / junk imagery.** A photo or AI image that doesn't match the
  topic (e.g. a photo of a *car* behind "egg prices"). This is the sloppy
  auto-grabbed stock/AI garbage we removed the channel from — it must never
  reappear.
- **Boring floating mascot.** Data stands/floats in the same spot doing nothing
  for most of the video. He is decoration, not a performer.
- **Bare-number card.** A stat presented as just a number on a plain
  shape/blob with no interesting demonstration.
- **Dead air.** A stretch of 4+ seconds where nothing meaningfully moves.
- **Empty void.** Large dead black space with one tiny element and nothing
  else going on.

---

## The verdict the showrunner returns

```json
{
  "score": 0-100,
  "verdict": "ship" | "block",
  "one_line": "the single most important thing",
  "auto_fails": ["..."],
  "dimensions": {"hook": n, "data_demo": n, "mascot": n, "craft": n, "pace": n, "payoff": n},
  "problems": ["specific, concrete, per-scene"],
  "fixes": ["specific, actionable — what to change to pass"]
}
```

`verdict: "block"` (score < 70 OR any auto-fail) stops the upload. The problems
and fixes are logged so the pipeline (or a human) can act on them — and, in the
self-healing phase, so the pipeline can regenerate the weak scenes and re-check.

---

## Why this exists

The pipeline had a headless Claude "brain" that *invented* per-scene visuals but
never *judged the whole video*. So boring, sloppy videos shipped unchallenged —
there was no editor with a veto. This rubric + `showrunner_review.py` is that
editor. Tune this file to raise or steer the bar; the showrunner reads it live.
