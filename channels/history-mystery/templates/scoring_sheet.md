# Idea Scoring Sheet — History & Mystery

Score every candidate **1–10** on seven axes. Multiply by the weight, sum for the
**weighted total (max 130)**. The topic bank ships pre-scored; use this sheet for
new ideas before they enter the bank.

## Rubric

| Axis | Weight | 1–3 (weak) | 4–7 (ok) | 8–10 (strong) |
|---|---|---|---|---|
| **Hook strength** | ×3 | No 2-second stopper | Decent angle | Instant "wait, WHAT?" |
| **Mystery factor** | ×2 | Fully explained, flat | Some intrigue | Genuinely unsolved / unbelievable |
| **Shareability** | ×2 | Nobody DMs this | Mildly cool | "I HAVE to send this" |
| **Visual potential** | ×2 | Nothing to show | Some images | Maps + photos + docs + diagrams |
| **Credibility** | ×2 | Shaky / mythical | Mostly solid | Primary/academic sources |
| **Search interest** | ×1 | Anonymous event | Loosely named | Strong named search term |
| **Series potential** | ×1 | One-off | Fits loosely | Anchors a series |

**Weighted total** = `3·hook + 2·mystery + 2·share + 2·visual + 2·cred + 1·search + 1·series`

## Decision

- **Greenlight:** total **≥ 85**.
- **Credibility hard-floor:** credibility **< 6 → KILL** (→ `topic_graveyard.json`,
  reason `credibility_issue`), regardless of total. Protects the brand (Manual §6).
- **Visual hard-floor:** visual **< 7 → not a Short.** Deprioritize, or route to
  **long-form** where narration can carry thinner visuals.
- Anything that fails → `topic_graveyard.json` with a reason, so we don't
  re-evaluate it later.

## Blank scoring table

| slug | hook | mystery | share | visual | cred | search | series | **total** | verdict |
|------|:----:|:-------:|:-----:|:------:|:----:|:------:|:------:|:---------:|---------|
| `` | | | | | | | | | |
| `` | | | | | | | | | |
| `` | | | | | | | | | |

> Quick check on the worked example (Dancing Plague of 1518):
> hook 9, mystery 9, share 9, visual 8, cred 9, search 8, series 8 →
> `3·9 + 2·9 + 2·9 + 2·8 + 2·9 + 8 + 8 = 27+18+18+16+18+8+8 = 113` → **greenlight**.
