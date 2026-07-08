# SCHULTE MEDIA — brain playbook

This file is the channel. The scout, sandbox, validators, render tools, uploader
and token are shared infrastructure; what makes Schulte Media *Schulte Media* is
the doctrine below. The brain (headless Claude, run in CI before render) reads
this file first and treats it as law. Operator feedback gets written back INTO
this file so it becomes permanent doctrine, not a one-off fix.

---

## 1. Identity (one swipe)

**Schulte Media shows the single most visually compelling thing hidden inside
what everyone is already talking about.**

We are NOT "today's headlines explained." A large share of people actively
avoid raw news, especially in an entertainment feed. We use current events as
raw material and publish the *vivid, picturable, curiosity-led* thing inside
them. The viewer isn't asking for information — in under a second they're asking
**"why should I care?"** Every video answers that instantly, visually.

## 2. The iron gate (a story may not enter the queue unless…)

> It can be pitched as a **vivid question** with **at least three concrete
> visual beats** (things you can literally show: a real animal, a map, a scale
> comparison, a physical object, a before/after).

If a story needs prior knowledge to care, or its beats are abstract
(policy, procedure, a ruling, a memo, a finance angle) — **reject it**, even if
it's trending. Trending is a *sourcing input, not an identity.*

## 3. Angle-first, never topic-first

The scout pool (`state/scouted_sources.json`, refreshed daily) is RAW MATERIAL.
For every candidate, do not ask "what happened?" — ask:

- **What is the one alarming, emotional, or physically imaginable thing inside
  this?**
- **What changed that a normal person can immediately picture?**
- **Who is affected, by how much, and what does that look like in real life?**

Then publish THAT, not the headline.
- Shark sighting trends → not "Shark seen off beach." → **"How close sharks
  actually get to shore."**
- Space update trends → not "NASA releases X." → **"How big this thing really
  is / what would actually happen if…"**

## 4. Editorial pillars (what qualifies)

| Pillar | Qualifies | Rejected |
|---|---|---|
| **Visual current-interest explainers** | animals & wildlife encounters, disasters, extreme weather, space, science discoveries, bizarre internet phenomena, infrastructure failures, unusual tech | parliamentary process, policy memos, regulatory minutiae, court procedure, abstract finance |
| **News-adjacent evergreen** | "why this keeps happening," "what this really means," "the scale behind the headline" | one-cycle recaps that die with the headline |
| **Prestige hard-news exception** | only if renderable through concrete visuals + a strong human-scale question | anything needing heavy prior knowledge to care |

**Proven by our own analytics:** animal / wildlife-encounter content retains
**74–102%** (a giraffe hit 102% = rewatches; golden retriever 75%); dry
policy/process dies at **31–41%**. Animals & vivid-danger stories are the
spine of this channel. Lead with them.

## 5. Retention doctrine (platform truth — non-negotiable)

- **The first second must contain proof, not setup.** No branding, no
  "here's what happened today," no throat-clearing. Open on the most surprising
  image or the most dramatic clause.
- **Every 1–1.5 seconds introduces new information OR a new visual state.** If
  the 50% frame equals the 100% frame, the shot is coasting — fix it.
- **Context never arrives before intrigue.** At most ONE sentence of context in
  the whole video, and only after the hook has earned the stay.
- **The final line must escalate, invert, or resolve** the premise — never
  restate a fact already shown. On Shorts, relative watch time dominates; every
  extra second must earn itself.

## 6. The three retention failures (diagnose from the shot-aligned map)

Every upload saves a timeline (hook start/end, each punch timestamp, each visual
swap, each caption event, gameplay-strip changes, payoff line, CTA). Once
YouTube returns retention segments we JOIN them to these timestamps and classify:

1. **Packaging failure** — decent *shown-in-feed* but weak *viewed-vs-swiped*.
   → Fix the first frame / first clause / first promise. Nothing else matters
   until this is fixed.
2. **Body failure** — they stay past 1s but leave mid-video.
   → Cut filler: throat-clearing context, generic stock, gameplay that's masking
   a weak top frame. Add a purposeful change where they drop.
3. **Payoff failure** — competent but the ending underperforms.
   → The last line adds nothing new. Make it escalate/invert/resolve.

## 7. Production rules the brain enforces

1. **The opening frame is already content** — the most surprising image, the
   most dramatic phrase, or the clearest proof object. Never branding/setup.
2. **Noun-heavy script** — the viewer must be able to *picture the sentence
   while hearing it.* Abstract institutional language is a defect unless
   immediately translated into something physical.
3. **Proof-of-relevance media** — don't ship the commodity look (stock + AI
   voice + subtitles). Put real proof in-frame: **maps** when geography matters,
   **labeled images** when identity matters, **source-like imagery** for
   novelty, **bold scale references** for magnitude.
4. **Gameplay strip is CONDITIONAL, not permanent** — three allowed states:
   full split-screen / intermittent strip / none. Which one is chosen is driven
   by shot-aligned retention data, not blanket doctrine. Default to *none* on
   strong-visual stories; only add it if data shows it creates a rewatch pocket,
   not a confusion pocket.
5. **One clean master, three wrappers** — export platform-clean and
   watermark-free; YouTube/TikTok/Instagram get different captions/covers, not
   different videos.

## 8. Package output schema (what the author must produce per story)

For each queued story the brain outputs:
- `cold_open` — the proof promise that is the literal first frame + first clause.
- `proof_frame` — the concrete image/object that first frame shows.
- `beats` — **exactly 3+ concrete visual beats** (each: what's shown + the say
  line, noun-heavy, speaks any number shown).
- `payoff` — the final line that escalates / inverts / resolves.
- `context` — at most ONE sentence, allowed only after the hook.
- plus the render fields (shots/punches/hashtags/pinned media) the pipeline
  already consumes.

## 9. Eye-QA loop (the thing that separates us from lazy pipelines)

After baking decisions, render each beat's final frame + 25/50/75% samples and
**LOOK at them**. Judge against §5 and §7:
- Would a professional channel proudly post this frame?
- Does the first second earn the view?
- Does something visibly change every beat (25 ≠ 50 ≠ 75 ≠ 100)?
- Real subject shown & recognizable; photos on-topic & label-matched; text legible
  in the safe area; reads muted; survives platform UI over the bottom.
Fix → re-render → re-look until every frame passes. This is mandatory.

## 10. Invariants no brain may break

- Trend is raw material — **never publish the raw headline form.**
- The iron gate (§2) is absolute — no ungated stories reach render.
- Every on-screen claim is spoken and labeled honestly; illustrative media is
  labeled as such.
- **AI-content disclosure stays ON** for every upload.
- **The eye-QA loop is non-negotiable.**
- The brain may only modify its target slugs' fields — state, dedupe, caps and
  channel guards are outside its blast radius. It can improve a video; it can
  never block or break one.

## 11. Weekly cadence (trend-guided, not trend-led)

| Track | Share | Goal |
|---|---:|---|
| Visual evergreen explainers triggered by current interest | 50% | reach + shelf life |
| Current-event explainers with obvious visual hooks | 35% | relevance + discovery |
| Pure hard-news tests | 15% | learn what breaks through, without diluting identity |

Most posts should have a shelf life beyond one news cycle. Only a minority are
truly perishable.
