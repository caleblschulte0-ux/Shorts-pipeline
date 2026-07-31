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
and scores seven dimensions. Weighted total, plus hard auto-fail triggers.

| # | Dimension | Weight | What "good" looks like |
|---|-----------|:------:|------------------------|
| 1 | **Hook (first ~2s)** | 18 | Frame 1 is motion + a reason to stay. NOT a slow chart build, NOT a plain title card. Something happens immediately. |
| 2 | **Data demonstration** | 22 | Each number is shown the *most interesting way it can be* — a physical/visual metaphor (things stacking, filling, racing, shrinking, crushing), not a bare number on a blob. Would a smart friend say "oh, that's a cool way to show it"? |
| 3 | **Mascot as performer** | 18 | Data is IN the scene DOING a real bit tied to the content (setup → action → payoff), and he MOVES / changes position. NOT a static sticker parked in a corner. NOT gliding aimlessly. He has a reason to be where he is. |
| 4 | **Visual craft** | 12 | Clean, intentional, "professional YouTube channel" — not empty black voids, not crude splatter graphics, not amateur layout. Composition uses the frame. |
| 5 | **Pace & motion** | 8 | Always something moving with purpose. No dead holds, no 4+ seconds of the same static frame. |
| 6 | **Payoff / retention** | 8 | Builds to a punchline or "whoa" and lands it; earns the swipe-through to the end. |
| 7 | **Temporal craft (cadence)** | 14 | Motion is genuinely smooth at the export rate — no judder, no low-fps source duplicated into a 30fps timeline, no frozen tails. **Graded in CODE, not by the model:** the reviewer measures the effective unique-frame rate (a block-max cadence detector that tells a smoothly-but-locally animating frame apart from a held one) — a laggy video cannot score its way to a pass on pretty stills. |

**Passing score: ≥ 70.** Below that, the video is **blocked**.

> The numeric total is computed IN CODE from anchored per-dimension grades — the
> model grades what it SEES on each dimension's small ceiling and never sees the
> passing threshold, so the score can't quietly compress to a safe ~72. The
> separation (weak < baseline < strong, bar in the gap) is pinned by
> `data_learning/tests/test_showrunner_scoring.py` and checked in CI before any
> render.

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
  "dimensions": {"hook": n, "data_demo": n, "mascot": n, "craft": n, "pace": n, "payoff": n, "temporal_craft": n},
  "problems": ["specific, concrete, per-scene"],
  "fixes": ["specific, actionable — what to change to pass"]
}
```

`verdict: "block"` (score < 70 OR any auto-fail) stops the upload. The problems
and fixes are logged so the pipeline (or a human) can act on them. The bounded
self-repair loop (`scripts/repair_loop.py`) closes that loop autonomously:
render → judge → make ONE whitelisted render-time nudge at the weakest thing →
re-render → keep whichever cut the gate scored higher, stopping after 2 attempts.
It never ships a worse cut and never edits code — the gate stays sovereign.

---

## Why this exists

The pipeline had a headless Claude "brain" that *invented* per-scene visuals but
never *judged the whole video*. So boring, sloppy videos shipped unchallenged —
there was no editor with a veto. This rubric + `showrunner_review.py` is that
editor. Tune this file to raise or steer the bar; the showrunner reads it live.
