# VISUALIZED (curiosity channel) — brain playbook

Faceless, **evergreen**, AI-assisted visual-curiosity channel. Operator playbook
v1 (2026-07-08), adapted from the operator's source playbook (ChatGPT) to run on
this repo's pipeline — see §13 for every deliberate deviation and why.

The channel slug is `curiosity`; the YouTube channel is
**OpenRangeInteractive (@OpenRangeInteractive)** — "ORI". Config:
`data_learning/curiosity.config.json`. Posted log:
`state/curiosity_posted_log.json`. Token: `YOUTUBE_TOKEN_JSON_CURIOSITY`
(alias `YOUTUBE_TOKEN_JSON_ORI` accepted). Workflow: `curiosity.yml`.
Wiring in §12. "Visualized" is the on-video brand label
(`channel_name` in config), same as Data Minute is the brand riding on
short_explainer67; rename either if the operator wants them unified.
Operator doctrine (permanent): a library of videos that are still worth
watching in five years; growth by catalog compounding, not by news cycles.

---

## 1. Identity — one swipe

> **Visualized turns one broad, evergreen question into a short, visually
> dense story with one memorable reveal — a museum exhibit in motion, never
> a lecture.**

The operating idea, per video: **one question → one tension → one memorable
reveal → one visual experience.** The winning subject is not "interesting
information" — it is **information that becomes more compelling when seen**
(motion, scale comparisons, maps, layers, transformations, journeys).

How this differs from the siblings (this is load-bearing — see §13.1):
- **baller bro 2.0** = fresh quirky NEWS. Visualized never touches news.
- **Data Minute (explainer)** = chart-first "X in 3 charts" data breakdowns.
  Visualized is **question-first**: the premise is a curiosity question a
  10-year-old would ask ("how deep can we dig?", "how fast am I moving?"),
  the charts exist only to land the reveal. If a pitch reads naturally as
  "here's a dataset," it belongs to Data Minute; if it reads as "wait,
  what IS down there?", it belongs here.
- **third** = streamer clip desk. No relation.

## 2. The iron gate — a story may not enter the queue unless…

> It is (a) a question a stranger understands **instantly** with zero prior
> knowledge, (b) still true and still interesting in **2–5 years**, and
> (c) scores **≥ 24/30** on the topic scorecard below.

| Dimension (1–5 each) | What a 5 looks like |
|---|---|
| Broad appeal | Almost anyone grasps the question immediately |
| Evergreen half-life | Still relevant in 2–5 years |
| Visualizability | Maps, scale, motion, layers, or simulation carry it |
| Compression | One clear thesis fits the format |
| Surprise | At least one "I didn't expect that" turn |
| Asset reuse | Reuses an existing template, dataset shape, or style |

Anything time-stamped ("this week," "just announced," an election, a product
launch) is auto-rejected — that is the news channels' food, not ours.

## 3. Angle-derivation rule for the shared scout pool

The scout pool (`state/scouted_sources.json`) is **optional inspiration only**
for this channel — the primary source is the topic bank (§14).

> From the shared pool, extract **the timeless question hiding under the
> headline** — never the event. Volcano erupts → "what's actually inside a
> volcano?" Bridge collapses → "why don't bridges collapse every day?"
> Heat wave → "how hot can Earth actually get?"

If the derived question would still make sense had the headline never
happened, it qualifies. Otherwise it's news — route it away.

## 4. Editorial pillars (the six)

| Pillar | Qualifies | Rejected |
|---|---|---|
| **Impossible scale** | giant numbers made visible ("how much concrete is in one city?") | numbers with no physical referent |
| **Hidden systems** | everyday infrastructure ("what happens after you flush?") | org charts, policy plumbing |
| **What-if scenarios** | cascading physical consequences ("what if gravity doubled?") | political / speculative-fiction what-ifs |
| **Extreme comparisons** | rankings you can SEE ("fastest objects ever built") | listicles with no visual spine |
| **Process journeys** | a thing through a system ("how a package crosses a country") | abstract workflows |
| **Maps & layers** | geography / stacked structures ("what lies beneath a city?") | maps as decoration for a non-spatial story |

Seed re-weighting from the channel's OWN analytics once ~100-view samples
exist (LEARNING_LOOP.md) — pillars earn their slate share, taste doesn't.

## 5. Retention doctrine [SHARED — platform truth, keep verbatim]
- First second = **proof, not setup**. No branding/throat-clearing.
- New information OR a new visual state every **1–1.5 seconds** (the 50% frame
  must not equal the 100% frame).
- **Context never before intrigue** — at most one context sentence, after the
  hook earns the stay.
- The final line must **escalate, invert, or resolve** — never restate a shown
  fact. Short form rewards relative watch time; every extra second must earn
  itself.

## 6. The three retention failures [SHARED]
1. **Packaging** (good shown-in-feed, weak viewed-vs-swiped) → fix first frame /
   first clause. Nothing else matters until this is fixed.
2. **Body** (stay past 1s, leave mid) → cut filler; add a change where they drop.
3. **Payoff** (competent but weak ending) → last line must add something new.

## 7. Production rules — the house style

**Format (launch): vertical Shorts, 45–60s, ~110–160 spoken words**, rendered
by the shared studio renderer (`data_learning/studio_render.py --config
data_learning/curiosity.config.json`). The source playbook's 4–5-minute
16:9 long-form is **phase 2**, built as weekly compilations (§13.2).

- **The opening frame is already content** (never branding); **the script is
  picturable** (abstract language is a defect unless immediately made
  physical). [SHARED]
- **Thesis before script.** One sentence stating the surprising truth
  ("GPS feels instant, but it depends on a fragile chain of clocks moving
  above the Earth"). If you can't write the thesis, kill the topic.
- **Story shape = the source playbook's arc, compressed to 3 beats:**
  hook (≤10 words, curiosity gap) → **setup → escalation → REVEAL** →
  closing line that zooms out (≤12 words). Each beat picks up where the
  last left off; if the beats could be shuffled, it's a list, not a story.
- **Hook formulas** (pick one, then make the title PAIR with it, not repeat it):
  - Hidden reality — "You use X every day, but no one sees Y."
  - Extreme scale — "X sounds small until you see how much there is."
  - Counterintuitive what-if — "If X changed, Y would fail first."
  - Journey — "This ordinary thing crosses a stranger system than you think."
  - Ranking tension — "The biggest X is not what you think."
- **Title patterns** (accurate, front-loaded, 45–65 chars): "What Happens If …",
  "The Secret Journey of …", "How Much X Actually Exists", "What's Really
  Under …", "The Biggest X Humans Ever Built", "Why X Doesn't Collapse
  Every Day". Never misleading — the title is a promise the reveal keeps.
- **Every number is REAL and traceable** — dataset `notes` names the figure,
  the rounding, and the source. `officiality: "reference"` for encyclopedic
  constants (NASA/USGS/NOAA/records); never ship an invented number, and
  never attribute an illustrative one to a real agency. Accuracy is the
  moat of a faceless channel.
- **Numbers must SPEAK cleanly** — digits + unit in every `say` line, the way
  they should be heard ("12,262 meters", "180 degrees Celsius", "828,000
  km/h"). [same tenant as the explainer channel]
- **Vary chart types** within a story (≥2 of rank/comparison/trend/share) and
  prefer VIZ-scene depictions (fill_object / stack / timeline / orbit over
  real photos) once the viz director runs on this config — a bare chart is a
  fallback, not the goal.
- **The muted test [the final operating rule]:** if the narration were muted,
  would the visual story still feel worth watching? If no, it's drifting
  back toward a generic faceless explainer — rebuild the visuals.

## 8. Package output schema

Stories live in `data_learning/curiosity.config.json` → `"stories"[]`, the
exact schema the explainer uses (slug, title, hook, closing, question,
caption, hashtags 10–15 most-specific-first, 3 segments each with a
`data_learning/data/curio_*.json` dataset, insight_type, topic, role, say
≤35 words). Dataset filenames are prefixed `curio_` so the two channels'
data never collides. Worked examples: `kola-deepest-hole`,
`sitting-still-speed`.

## 9. Eye-QA checklist [SHARED loop + channel specifics]

After baking, render each beat's final frame + 25/50/75% samples and **LOOK**.
Shared checks: would a pro proudly post this frame; does the first second earn
the view; does something visibly change every beat (25 ≠ 50 ≠ 75 ≠ 100); text
legible in the safe area; reads muted; survives platform UI. Then:
- The QUESTION is unmistakable within the first 2 seconds.
- The reveal beat is visually the biggest moment of the video (not beat 1).
- Every on-screen number is spoken, and every spoken number is on screen.
- No two segments share a layout.
- Title + thumbnail pair honestly with the reveal (the thumbnail is
  auto-emitted by the renderer; check it reads at small size).

## 10. Invariants no brain may break [SHARED]
- Trend is raw material — never publish the raw item form.
- The iron gate (§2) is absolute.
- Every on-screen claim spoken + labeled honestly; illustrative media labeled.
- **AI-content disclosure stays ON** for every upload.
- **The eye-QA loop is non-negotiable.**
- The brain edits only its target slugs' fields; state, dedupe, caps, and
  channel guards are outside its blast radius.

## 11. Learning loop [SHARED — LEARNING_LOOP.md is law]

`fetch_analytics.py --channel curiosity` snapshots to
`state/analytics_curiosity/latest.json`. Track per upload: pillar, hook
formula, title pattern, first-30s retention, avg % viewed, CTR (when
exposed), subs/1k, traffic mix. Bias future slates toward what retains;
**no auto-adaptation below ~100 views/video.** Operator feedback gets
written back INTO this playbook.

Growth roadmap (targets, not guarantees): first 90 days = prove one
repeatable pillar + aesthetic consistency; months 4–6 = back-catalog
title/thumbnail refresh + tighten openings on first-30s data; months 6–12 =
YPP thresholds (early access 500 subs + 3M Shorts views/90d; full share
1k subs + 10M/90d), then monetize in layers: ads → affiliates (books, maps,
science kits, globes) → digital products (poster/map packs, template packs)
→ sponsors → course, in that order, each only after the previous is earning.

## 12. Wiring & isolation (zero shared-pipeline impact)

- **Token:** `YouTubeUploader(channel="curiosity")` → reads
  `YOUTUBE_TOKEN_JSON_CURIOSITY`; the workflow also accepts the
  operator-created secret name `YOUTUBE_TOKEN_JSON_ORI` (mint with
  `setup_youtube.py` signed into the OpenRangeInteractive account).
  Guard: `YOUTUBE_EXPECTED_CHANNEL` defaults to `OpenRangeInteractive`;
  repo var `CURIOSITY_EXPECTED_CHANNEL` overrides if the channel renames.
- **Config/log/analytics:** `data_learning/curiosity.config.json` ·
  `state/curiosity_posted_log.json` · `state/analytics_curiosity/`.
- **Render + post:** `scripts/post_stories.py --config
  data_learning/curiosity.config.json --log state/curiosity_posted_log.json
  --channel curiosity` (the explainer's defaults are untouched).
- **Workflow:** `.github/workflows/curiosity.yml` — cron 14:00 UTC daily +
  chained off "Daily Shorts", concurrency group `curiosity-shorts`,
  schedules un-posted stories **24h apart** (1/day cadence).
- **Dedupe:** `python3 scripts/topic_guard.py --config
  data_learning/curiosity.config.json --check "<title>" tag1 tag2` — and ALSO
  run the same check against the default config to avoid re-telling a
  Data Minute subject (cross-channel near-dupes split the same audience).
- **Authoring:** the daily Claude routine, Part 3 of
  `CLAUDE_ROUTINE_INSTRUCTIONS.md` (1 story/day).
- `daily.yml` / `explainer.yml` / `third.yml` are never touched by this
  channel.

## 13. Deviations from the source playbook (operator pushback log)

The source playbook's **strategy layer is adopted wholesale** (pillars,
scorecard, hook/title formulas, thesis-first scripting, QA, analytics
fields, monetization order, the muted test). Its **production layer is
not** — it was written for a human with a desktop, not for this pipeline:

1. **A fourth channel overlaps Data Minute.** Both are curiosity + numbers.
   We ship anyway because the operator asked, but the §1 differentiation
   rule (question-first vs chart-first) and the cross-channel topic-guard
   check (§12) exist precisely to keep them from cannibalizing each other.
   If after ~60 days the two channels' audiences look identical in
   analytics, fold this doctrine into Data Minute instead of running both.
2. **4–5 min 16:9 long-form weekly → 45–60s vertical Shorts daily, long-form
   as phase 2.** The repo renders vertical; the proven in-repo hybrid is
   Shorts daily + `build_longform.py`-style weekly compilations. A
   zero-subscriber channel posting one long video a week starves the
   algorithm of signal; Shorts-first compounds, and the long-form
   compilation lands the watch-hours later (also how YPP's 3M/10M Shorts
   thresholds are actually reachable). The playbook's 1080p/H.264/AAC/48kHz
   spec, chapters, and 3840×2160 thumbnails apply when phase 2 starts.
3. **Blender/Inkscape/Manim/Glaxnimate/Kdenlive → the studio renderer.**
   Those are human-in-the-loop desktop tools; CI can't art-direct Blender.
   The pipeline's viz engine (real-photo scenes: fill, stack, orbit,
   timeline, pictorial races) already implements the playbook's actual
   goal — deterministic, reproducible, visually dense scenes — headlessly.
4. **Piper/Audacity → Kokoro.** Same reasoning (local, free, reproducible);
   Kokoro is already cached in CI with per-video voice theming.
5. **ComfyUI → `gemini_images.py`**, already wired with graceful fallback.
   Generative art stays the last resort, as the playbook says.
6. **1 video/week → 1/day.** The weekly cadence priced in 6–11 human-hours
   per video; the pipeline's marginal cost is ~zero, and an evergreen
   catalog compounds with size. Quality is enforced by the gate (§2) and
   eye-QA (§9), not by scarcity.
7. **550–800 words → ~110–160.** Scaled to the Shorts format; the full
   word budget returns in phase-2 long-form.
8. **Noto Sans/Sora → the renderer's existing type system.** Consistent
   tooling across channels beats a per-channel font swap; revisit if the
   channel earns a bespoke look.
9. **Google Drive/OneDrive/Dropbox storage plan → this git repo.** Projects,
   sources, analytics, and templates already live here versioned; no new
   storage accounts.

## 14. Topic bank (seed — score before greenlighting, §2)

Status: `kola-deepest-hole` ✅ authored · `sitting-still-speed` ✅ authored.

| Pillar | Question |
|---|---|
| Impossible scale | How much rain falls on Earth every second? |
| Impossible scale | How much concrete exists in one city? |
| Impossible scale | How much of the ocean have we actually seen? |
| Impossible scale | How many satellites are over your head right now? |
| Impossible scale | How much gold has ever been mined (it fits where?) |
| Hidden systems | What happens after you flush? |
| Hidden systems | What it actually takes for GPS to work |
| Hidden systems | Where your tap water was 30 days ago |
| Hidden systems | Why the power grid doesn't collapse every day |
| Hidden systems | What's inside an undersea internet cable? |
| What-if | What if Earth stopped spinning? |
| What-if | What if gravity doubled tomorrow? |
| What-if | What if all ice on Earth melted? |
| What-if | What if the Moon disappeared? |
| Extreme comparisons | The fastest objects humans ever built |
| Extreme comparisons | The deepest holes ever dug vs the tallest towers |
| Extreme comparisons | The loudest sound in recorded history |
| Extreme comparisons | The biggest machine humans ever built |
| Process journeys | How a package crosses a country in 48 hours |
| Process journeys | The journey of a raindrop to your faucet |
| Process journeys | How electricity reaches your outlet in milliseconds |
| Process journeys | Where a recycled bottle actually goes |
| Maps & layers | What's really under a city street? |
| Maps & layers | How deep the ocean's layers actually go |
| Maps & layers | What's between you and Earth's core? |
| Maps & layers | The tallest mountain isn't Everest (measure it right) |

Add new ideas here with pillar + a one-line thesis; retire anything the
topic guard flags or that fails the 24/30 gate twice.
