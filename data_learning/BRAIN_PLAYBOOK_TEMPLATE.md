# BRAIN PLAYBOOK TEMPLATE — copy this to spin up (or update) a channel's brain

**How to use.** Copy this file to `data_learning/<CHANNEL>_BRAIN.md`, fill every
`<< … >>` placeholder, and point that channel's workflow "brain" step at it. The
brain (headless Claude in CI, run before render, authed by the operator's
subscription token) reads its playbook FIRST and treats it as law.

**A new channel's brain = 3 things** (everything else is shared infrastructure —
scout pool, sandbox, validators, render tools, uploader, token, LEARNING_LOOP):
1. **This playbook**, filled in — the channel's identity, laws, taste, and its
   angle-derivation rule for the shared scout pool.
2. Its own **config + credentials** — story/queue config, posted-log, analytics
   dir, an expected-channel guard, and its OWN YouTube token secret.
3. A **cloned workflow** — clone the reference `explainer.yml`/`daily.yml` brain
   step, point it at this playbook, give it its own concurrency group and a cron
   offset AFTER the 05:00 UTC scout.

Sections marked **[SHARED]** are platform/system truth — copy them verbatim, do
not weaken them. Sections marked **[FILL]** are what makes the channel itself.

---

## 1. Identity — one swipe **[FILL]**
> **<< In one sentence a cold viewer understands instantly: what does this
> channel show, and why should they care in under a second? >>**

Example (Schulte Media): "The single most visually compelling thing hidden inside
what everyone is already talking about."

## 2. The iron gate — a story may not enter the queue unless… **[FILL]**
> **<< The one hard filter. A story is rejected if it fails this, even if it's
> trending. >>**

Guidance: the strongest gates are visual + concrete. e.g. "pitchable as a vivid
question with ≥3 concrete visual beats"; or for a data channel, "reduces to one
number a viewer can feel."

## 3. Angle-derivation rule for the shared scout pool **[FILL — most important]**
The scout pool (`state/scouted_sources.json`) is channel-agnostic RAW MATERIAL.
State exactly how THIS channel derives its angle from it:
> **<< From the shared pool, extract ______ (never the raw item itself). >>**

Examples: data channel → "extract the underlying DATA story (4th of July →
firework cost/physics)"; news channel → "extract the one alarming/emotional/
physically-imaginable thing inside the event, and publish that, not the
headline."

## 4. Editorial pillars **[FILL]**

| Pillar | Qualifies | Rejected |
|---|---|---|
| << pillar 1 >> | << … >> | << … >> |
| << pillar 2 >> | << … >> | << … >> |
| << pillar 3 (prestige exception) >> | << … >> | << … >> |

Seed these from the channel's OWN analytics once available (what its audience
actually retains on), not from taste alone.

## 5. Retention doctrine **[SHARED — platform truth, keep verbatim]**
- First second = **proof, not setup**. No branding/throat-clearing.
- New information OR a new visual state every **1–1.5 seconds** (the 50% frame
  must not equal the 100% frame).
- **Context never before intrigue** — at most one context sentence, after the
  hook earns the stay.
- The final line must **escalate, invert, or resolve** — never restate a shown
  fact. Short form rewards relative watch time; every extra second must earn
  itself.

## 6. The three retention failures **[SHARED]**
1. **Packaging** (good shown-in-feed, weak viewed-vs-swiped) → fix first frame /
   first clause. Nothing else matters until this is fixed.
2. **Body** (stay past 1s, leave mid) → cut filler; add a change where they drop.
3. **Payoff** (competent but weak ending) → last line must add something new.

## 7. Production rules **[FILL — the channel's house style]**
> **<< The concrete media/format laws: what the opening frame must be, how the
> script must read, the proof standards for imagery, and any format-strip policy
> (e.g. gameplay strip = conditional, not permanent). >>**

Keep these two SHARED regardless of channel: **the opening frame is already
content** (never branding); **the script is picturable** (abstract language is a
defect unless immediately made physical).

## 8. Package output schema **[FILL]**
> **<< The exact fields the author must produce per story >>** — e.g. cold-open
> promise, proof frame, ≥3 concrete beats (each: shown + say line), payoff line,
> ≤1 context sentence, plus the render fields the pipeline consumes.

## 9. Eye-QA checklist **[SHARED loop + FILL specifics]**
After baking, render each beat's final frame + 25/50/75% samples and **LOOK**.
Shared checks: would a pro proudly post this frame; does the first second earn
the view; does something visibly change every beat (25 ≠ 50 ≠ 75 ≠ 100); text
legible in the safe area; reads muted; survives platform UI. Then add:
> **<< channel-specific frame checks (e.g. "the real subject is recognizable",
> "every number shown is spoken", "no two segments share a layout"). >>**
Fix → re-render → re-look until every frame passes. **Non-negotiable.**

## 10. Invariants no brain may break **[SHARED]**
- Trend is raw material — never publish the raw item form.
- The iron gate (§2) is absolute.
- Every on-screen claim spoken + labeled honestly; illustrative media labeled.
- **AI-content disclosure stays ON** for every upload.
- **The eye-QA loop is non-negotiable** — it's what separates this from every
  pipeline that ships lazy frames.
- The brain edits only its target slugs' fields; state, dedupe, caps, and channel
  guards are outside its blast radius. It can improve a video; it can never block
  or break one.

## 11. Learning loop **[SHARED — see LEARNING_LOOP.md]**
The brain reads `state/brain_context.json` (staged scorecard + shrinkage-safe
winners/losers + retention cliffs) and makes **bounded, reversible** edits only.
**Do not auto-adapt on sub-~100-view samples.** Operator feedback gets written
back INTO this playbook so it becomes permanent doctrine, not a one-off fix.
