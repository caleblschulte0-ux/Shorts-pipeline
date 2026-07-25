# quality_memory/ — the Showrunner's persistent memory

This directory is the **spine that makes each video better than the last**. Every
render is judged (interest, cool, motion-first, continuity); this is where those
verdicts are *remembered* so recurring failures get fixed once, not re-discovered
every time.

## Files

| File | What it is |
|---|---|
| `ledger.jsonl` | Append-only. One JSON line per render: its slug/label, interest metrics, per-beat cool-judge rows (job + suspect flags + motion/appeal/hold), motion-first fallbacks & wins, continuity. This is the raw history — never hand-edit, only append via the Showrunner. |
| `rules.json` | Derived. Rebuilt by `showrunner learn` from the whole ledger: the recurring per-job failure rules, the subjects that keep failing to find motion (access needs), and the quality trend (dead-time / appeal / bland over time). This is what `advise` reads. |

## The loop (see `data_learning/showrunner.py`)

```
render ─▶ quality_gate.py ─▶ interest_judge + cool_judge
                                     │
                                     ▼
                          showrunner.record  (append to ledger.jsonl)
                                     │
                                     ▼
                          showrunner.learn   (rebuild rules.json)
                                     │
   next story ◀── showrunner.advise ◀┘   (warn BEFORE the next render burns)
```

- **After a render:** `python scripts/quality_gate.py <render.mp4> --beatmap <bm> --slug <s> --label <v>`
- **Before authoring the next one:** `python -m data_learning.showrunner advise <story.beats.json>`
- **Anytime:** `python -m data_learning.showrunner report`

## Why it's committed

`ledger.jsonl` and `rules.json` are tracked in git on purpose: the memory has to
survive the ephemeral render container, or "over time" resets to zero every
session. The judge-output image/clip dirs are scratch and are **not** committed —
only the distilled verdicts.

A rule graduates from `soft` (bit some renders) to `hard` (bit *every* render that
had that beat). Hard rules are the ones the next author must not repeat.
