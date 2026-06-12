# History & Mystery — Operating Manual

> **The goal is not to build a history channel.**
> The goal is to build the internet's largest library of *"That can't be real…
> wait, that's actually true"* stories.
> **History is the setting. Wonder and disbelief are the product.**

This north star governs every decision below it. Before you greenlight a topic,
write a line, pick a visual, or read a metric, ask: *does this serve the moment
where the viewer goes "wait, that's REAL?"* If it doesn't, cut it.

This is the strategy + standards document. The day-to-day execution steps live in
[`DAILY_ROUTINE.md`](DAILY_ROUTINE.md); the repeatable templates and style guides
live in [`CONTENT_ENGINE.md`](CONTENT_ENGINE.md); the topic inventory and scoring
data live in [`templates/`](templates/).

---

## 0. How this fits the existing pipeline

This is a **third channel** bolted onto the Shorts-pipeline repo, mirroring the
isolated-subsystem pattern of `data_learning/`. It rides the **existing v8
package schema** and renderer (`make_explainer_stacked.py`) — a package authored
here is the same JSON shape the news channel ships, so it renders and uploads
with zero new pipeline code. The only differences are *editorial*: what we pick,
how we write it, and how we hold the credibility line.

| | News channel ("baller bro 2.0") | **History & Mystery** |
|---|---|---|
| Topic source | RSS, last 24–48h | Evergreen topic bank (`templates/topic_bank.json`) |
| Selection bias | Quirky / freshness | Wonder + credibility + visual potential |
| Tone | Loud, fast, anchor | Measured, ominous-curious, "let the facts hit" |
| Music vibe | `hiphop` / `dark` | `cinematic` / `dark` |
| Bottom half | Minecraft / Subway gameplay | Calm atmospheric motion (see §9 Scope) |
| Mascot | "baller bro" anchor | Restrained / none |
| Credibility | Cross-outlet wire check | **Hard fact-vs-theory gate** (§6) |

---

## 1. Channel concept — pick one to launch, hold the other two in reserve

We recommend three concepts. **Launch on Concept A.** Concepts B and C are your
A/B lanes once you have data (see §7 testing plan).

### ⭐ Concept A (ANCHOR) — *"Sounds Fake — But It Happened"*

- **Positioning:** Impossible-sounding historical events that are 100% real.
- **Target viewer:** The curious scroller who loves "no way that's real" facts
  and screenshots them for friends. Not a history buff — a *wonder* junkie.
- **Tone:** Awe + disbelief, delivered straight. The facts are wild enough; we
  don't oversell. Credibility *is* the entertainment — the moment they believe
  it, the payoff lands.
- **Why it wins:** Highest shareability (the "wait, that's real?" reflex is a DM
  trigger), and it's the **safest for credibility** because the whole brand is
  "we only tell you true things that sound fake." Lying once kills the format.
- **Risk:** Topic discipline. The temptation is to drift into "creepy unexplained"
  clickbait. Stay on *verifiable* events. Mysteries are welcome; fabrications are
  brand death.

### Concept B — *"The Dark Side of Forgotten History"*

- **Positioning:** Eerie, ominous, true-crime-adjacent corners of history.
- **Tone:** Dread + curiosity. Lower lights, slower voice.
- **Why it's a reserve lane:** Higher retention ceiling (dread holds), but
  higher credibility risk and a narrower ad-friendliness band. Use as a second
  content pillar / A-B test, not the launch identity.

### Concept C — *"Breaking News From History"*

- **Positioning:** Historical mysteries reported like an urgent present-tense
  news bulletin ("This just in: an entire town can't stop dancing").
- **Tone:** Anchor-style urgency. Reuses the pipeline's news DNA most directly.
- **Why it's a reserve lane:** Easiest to produce with existing muscle memory,
  but the framing can feel gimmicky and undercut the "credible" goal if overused.

**Decision:** Anchor on **A**. Everything below (voice, captions, scoring
weights) is tuned for A. When you test B or C, you're testing a *lane within the
same channel*, not rebranding.

---

## 2. The winning video formula (built for retention, not information)

Every Short is engineered around the v8 schema's hook/kicker rules so it stays
**validator-legal** (`scripts/validate_packages.py`) AND maximally retentive.
Target length **45–50s**, 110–140 words.

| Time | Beat | Job | Rule it must satisfy |
|------|------|-----|----------------------|
| **0–2s** | **HARD HOOK** | Stop the thumb. State the impossible claim in a ≤5-word line that ends in `?` or `!`. | Validator: first sentence ≤5 words, ends `?`/`!`. |
| **2–8s** | **SETUP** | Anchor it in reality — name the **year, place, people**. Specificity *is* the credibility. | "In 1518, in Strasbourg…" |
| **8–35s** | **ESCALATING FACTS** | 6–9 facts, each more "no way" than the last. The escalation is the retention engine — every line raises the disbelief. | Digits, named entities, no filler. |
| **35–50s** | **TWIST / REVEAL** | The detail that flips it — the part that makes it *sound* fake but proves it real, OR the unsolved core. | The emotional peak. |
| **final** | **PAYOFF / QUESTION** | Land the wonder, then a kicker that ends in `?` AND names something specific from the story. | Validator: last sentence ends `?`, names a story entity. |

**The hook problem, solved.** The strongest "sounds fake" hook is a flat
declarative ("An entire town danced to death"), but the validator wants ≤5 words
ending `?`/`!`. Resolve it by making the hook a *disbelief beat*, then dropping
the claim immediately in the setup:

- ✅ `"This actually happened?!"` → *"In 1518, hundreds of people in Strasbourg
  danced for days — some until they died."*
- ✅ `"History faked this?"` → *"It didn't. The Dancing Plague is in the city
  records."*
- ✅ `"No one survived this?!"`
- ✅ `"They weaponized BEES?"`

The hook sells the disbelief; the next sentence cashes it with the real claim.

**Retention rule of thumb:** if any line doesn't either (a) raise disbelief or
(b) prove the claim, cut it. No throat-clearing, no "let me tell you about."

---

## 3. Success metrics — what we optimize, in priority order

Optimize for the algorithm's actual reward function, not vanity. For each metric:
the *one lever* that moves it.

1. **Retention / Average View Duration (AVD)** — the master metric.
   *Lever:* the hook + fact escalation (§2). Front-load the wildest, never
   back-load. Kill any video under the retention floor (§7).
2. **Rewatchability** — Shorts loop; a tight loop multiplies watch time.
   *Lever:* end on the kicker question so the loop back to the hook feels
   seamless; keep it ≤50s.
3. **Click-through rate (CTR)** — for long-form especially.
   *Lever:* title formula + thumbnail formula (`CONTENT_ENGINE.md`). For Shorts,
   the first frame IS the thumbnail — make it a wonder-frame, not a logo.
4. **Comments per view** — the algorithm reads comments as "this provoked them."
   *Lever:* the kicker question must be *answerable and divisive* ("Was it mass
   poisoning, or something we still can't explain?"). Never "comment yes."
5. **Subscriber conversion** — turns a hit into a channel.
   *Lever:* series identity (§ Series Engine in `CONTENT_ENGINE.md`). People
   subscribe to a *bucket* they want more of, not a one-off.
6. **Repeat viewers** — the compounding asset.
   *Lever:* recognizable series + consistent voice/format so the next video
   *feels* like "more of that thing I liked."

**Ignore** raw view counts, impressions, and follower vanity *unless* they
predict the six above. A 100k-view video with 20% retention and no comments is a
worse asset than a 10k-view video with 70% retention and a full comment section.

---

## 4. Make it feel human (anti-AI-slop toolkit)

The fastest way to read as "AI slop" is to be *generically smooth*. Real media
has texture. Use these deliberately:

| Technique | Do | Don't |
|---|---|---|
| **Curiosity gap** | "And the strangest part wasn't the dancing." | "There are many interesting facts about this." |
| **Pattern interrupt** | A one-word line. A hard stop. Then a pivot. | Uniform sentence rhythm for 45 seconds. |
| **Specific detail** | "5:45 a.m. on Old Quarry Road." | "early one morning somewhere." |
| **Pacing change** | Three fast facts, then one slow reveal. | Same cadence start to finish. |
| **Twist** | The fact that recontextualizes everything. | A flat list that just ends. |
| **Attitude / humor (sparingly)** | A dry aside once per video, max. | Constant quips that bury the wonder. |
| **Strong narration** | Verbs, present tense, second person. | "It is believed that it was thought…" |

**Banned AI-slop tells** (auto-rejected by the slop gate, §6 / `slop_check.py`):
`Imagine…`, `What if I told you…`, `You won't believe…`, `In a world where…`,
`Little did they know…`, `Buckle up`, `Let that sink in`, generic hype
("absolutely insane", "mind-blowing") with no fact behind it, repeated facts,
and vague descriptors where a specific would fit.

**The specificity test:** every script must contain real **dates, places,
people, and concrete numbers**. If you can't name them, you don't understand the
story well enough to script it — go back to sources.

---

## 5. (moved) — see §6

---

## 6. Credibility & safety charter — this is a GATE, not a guideline

History/mystery is a misinformation minefield. Our entire brand ("sounds fake
but is TRUE") collapses the first time we present a fabrication or a conspiracy
as fact. These are hard rules; a script that violates them does not ship.

1. **Separate confirmed fact from theory.** Use the language deliberately:
   - Confirmed: "It happened." / "Records show." / "X died on this date."
   - Theory: **"One theory says…" / "Historians still debate…" / "The leading
     explanation is…"** — never "this proves," never "the truth is."
2. **Never invent a historical fact, number, date, name, or quote.** If you're
   unsure, leave it out. A vaguer-but-true line beats a vivid-but-fabricated one.
3. **Flag weak claims in the script itself.** If a detail rests on a single shaky
   source, either cut it or frame it as contested ("some accounts claim").
4. **Conspiracies are framed as claims, not truth.** "Some believe X" is fine;
   asserting X is not. We can *cover* a conspiracy; we don't *endorse* one.
5. **Log sources internally** for every video using `templates/fact_check_template.md`.
   The fact/theory split note in the topic bank is the first pass; the fact-check
   template is the per-video record. No sourced fact-check file → no ship.
6. **The mystery stays a mystery.** When something is genuinely unsolved, say so.
   Don't manufacture a fake resolution for a clean ending — the unsolved-ness is
   the product. "We still don't know" is a *stronger* kicker than a made-up answer.

This charter is enforced in the scoring system as a **Credibility hard-floor**
(§8): a topic that can't clear the credibility bar is killed regardless of how
good its hook is.

---

## 7. 30-day launch plan

**Cadence:** 1–2 Shorts/day, every day. Consistency > volume — a young channel
that firehoses gets throttled and can't read its own signal.

**First long-form: between day 7 and day 10.** Don't wait. Pull it from your
**highest-performing early topic cluster** (the series or subject your first
week's Shorts retained best). A single strong long-form builds channel identity
and converts higher-quality subscribers faster than dozens of Shorts — it tells
the algorithm and the viewer "this is a real channel about *this*."

**Shorts ↔ long-form relationship:** Shorts are the *discovery + testing* engine;
long-form is the *identity + retention-time* engine. Use Short performance to
pick long-form topics, and use long-form to deepen the winning series.

| Phase | Days | Focus |
|---|---|---|
| **Launch** | 1–6 | 2 Shorts/day across ≥4 series. Establish the look + voice. Pure data-gathering. |
| **First long-form** | 7–10 | Ship long-form #1 from the best early cluster. Keep 1–2 Shorts/day. |
| **Read & lean** | 11–20 | Double down on the winning series/hook styles; start B vs A lane test. |
| **Consolidate** | 21–30 | 2nd long-form; kill the weakest series; lock the format that's working. |

**First 30 video ideas:** drawn directly from `templates/topic_bank.json` — pick
the 30 highest `total` scores that also clear the visual-potential floor (≥7),
spread across ≥4 series so the channel reads as a *library*, not a one-trick feed.

**Testing plan:**
- **Lane test (A vs B):** after ~day 10, run a block of Concept-B ("dark side")
  Shorts against the Concept-A baseline. Compare retention + comments.
- **Hook-style test:** alternate hook shapes (disbelief question vs. flat number
  vs. "no one survived") and tag each in `winning_patterns.json`.
- One variable at a time. Tag every video's hook_type / series / title_style so
  the analytics memory can actually attribute the win.

**Data to track per video** → logged in `templates/winning_patterns.json`:
retention, AVD, rewatches, CTR, likes, comments, shares, subscriber conversion,
plus its `topic_category`, `hook_type`, `title_style`, `series_id`.

**Double-down / kill rules:**
- **Kill a format/series** after **5 videos** averaging below the **retention
  floor** (set it from your own first-week median; a reasonable starting line is
  **<55% average view** for Shorts). Move its topics to the graveyard or to
  long-form.
- **Double down** on any series or hook style beating both the CTR and retention
  targets — give it 2× the slots and make it the next long-form.
- **Re-score quarterly:** feed `winning_patterns.json` back into the topic bank
  scores (the analytics loop in `CONTENT_ENGINE.md`).

---

## 8. Idea scoring system

Score every candidate topic 1–10 on **seven axes**. The topic bank
(`templates/topic_bank.json`) ships pre-scored; `templates/scoring_sheet.md` has
the full rubric and a blank table for new ideas.

| Axis | Question | Weight |
|---|---|---|
| **Hook strength** | Can the first 2 seconds make someone stop? | ×3 |
| **Mystery factor** | How strong is the "wait, what?" pull? | ×2 |
| **Shareability** | Will someone DM this to a friend? | ×2 |
| **Visual potential** | Are there maps/photos/docs/diagrams to show? | ×2 |
| **Credibility** | Is it verifiable from solid sources? | ×2 (**gate**) |
| **Search interest** | Will people search this / does it have a name? | ×1 |
| **Series potential** | Does it fit/extend a recurring bucket? | ×1 |

**Weighted total** = Σ(score × weight), max 130. **Greenlight ≥ 85.**

**Two hard floors (override the total):**
- **Credibility floor:** Credibility **< 6 → killed**, no matter the total. This
  enforces §6. Send to `topic_graveyard.json` with `credibility_issue`.
- **Visual-potential floor:** Visual **< 7 → not a Short.** Deprioritize, or route
  to **long-form** (where narration can carry thinner visuals). Tag accordingly.

Everything that fails goes to `templates/topic_graveyard.json` with a reason, so
we never burn cycles re-evaluating the same weak idea.

---

## 9. Scope boundary — the one honest gap (read before you blame the renderer)

The hybrid look you chose is **cinematic top + calm atmospheric bottom**. The top
half works **today** (archival imagery + maps via the schema's `image_url` +
`query` Wikimedia mechanism — see `CONTENT_ENGINE.md` §Visual). The ideal
**bottom half** (drifting fog / embers / parchment / slow maps) **does not exist
as a `bottom_theme` yet** — the current themes (`themed_bottom.py`) are all
gameplay-style.

Until a dedicated atmospheric theme is added, approximate the mood with the knobs
we have:
- `music_vibe`: **`cinematic`** or **`dark`** (never `hiphop` here).
- `bottom_theme`: **omit it** (or pick the calmest existing fit) and let the slow
  cinematic top + music carry the atmosphere. Do **not** use `runner`, `fight`,
  `moto`, etc. — they shatter the tone.

**Recommended follow-up (out of scope for this manual):** add one atmospheric
`bottom_theme` (e.g. `parchment` / `embers` / `drift`) to `themed_bottom.py`
following its DESIGN CHARTER. That's the single renderer change that would make
the hybrid format first-class.

**Also a prerequisite you own:** a new `channel` routing slug for this channel in
the uploader. Once it exists, every package sets
`"channel": "<your-history-mystery-slug>"`. Until then, packages route to the
default channel.
