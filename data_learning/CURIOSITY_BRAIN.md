# VISUALIZED (curiosity channel) — brain playbook

Faceless, **evergreen**, AI-assisted visual-curiosity channel publishing
**4–5 minute LONG-FORM 16:9 videos on the main YouTube watch feed — NOT
Shorts** (operator ruling, 2026-07-08: the portfolio already has plenty of
Shorts channels; this one is the long-form play). Operator playbook v2,
adapted from the operator's source playbook (ChatGPT) to run on this repo's
pipeline — see §13 for every deliberate deviation and why.

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

> **Visualized turns one broad, evergreen question into a visually dense
> 4–5 minute story with one memorable reveal — a museum exhibit in motion,
> never a lecture.**

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

## 5. Retention doctrine [platform truth, long-form calibration]
- First seconds = **proof, not setup**. No branding/throat-clearing; the
  hook states the premise, the tension, and the promised payoff inside
  the first 15–20 seconds.
- New information OR a new visual state every **1–3 seconds** (camera,
  object, label, scale, crop, or motion — the 50% frame must not equal the
  100% frame).
- **Context never before intrigue** — context sentences come after the
  hook earns the stay.
- The final line must **escalate, invert, or resolve** — never restate a
  shown fact. Watch time is the currency; every extra second must earn
  itself, and long-form's advantage is that earned seconds compound into
  watch-hours.

## 6. The three retention failures [SHARED]
1. **Packaging** (good shown-in-feed, weak viewed-vs-swiped) → fix first frame /
   first clause. Nothing else matters until this is fixed.
2. **Body** (stay past 1s, leave mid) → cut filler; add a change where they drop.
3. **Payoff** (competent but weak ending) → last line must add something new.

## 7. Production rules — the house style

**Format: 1920×1080 16:9, 30fps, MP4/H.264, AAC-LC 48kHz, −14 LUFS,
4–5 minutes, ~550–800 spoken words** — the source playbook's spec, rendered
by the channel's own long-form renderer
(`python -m data_learning.longform_render --slug <slug>`). Documentary
pacing: calm narration (no Shorts-speed voice), one "exhibit" frame per
beat with a slow Ken Burns push, a ducked music bed, a title card open and
a takeaway card close.

**Chapters are mandatory** (auto-emitted to `<out>.meta.json` and written
into the description): first at 00:00, at least 3, each ≥10 seconds —
beats run 20–40s so this holds by construction. **Thumbnail** is
auto-emitted at 1920×1080 (claim + biggest on-chart number in the video's
theme palette); once the channel earns advanced features, A/B test
titles/thumbnails on the back catalog.

**Tools doctrine (operator ruling, verbatim):** *"Desktop tools are allowed
only if they support reliable, fully headless operation through a stable
CLI or scripting API and integrate cleanly into the CI pipeline without
requiring human interaction."* In practice: ffmpeg, matplotlib/Pillow,
ONNX TTS, ImageMagick, Graphviz, and Blender (`blender -b`, Python API)
are all fair game when a story needs them; Inkscape/Kdenlive/Resolve/
Premiere/After Effects are not — they're GUI-first. Blender is the
sanctioned path if a story ever needs true 3D (a fly-through, an exploded
view); build reusable scene templates before reaching for it.

- **The opening frame is already content** (never branding); **the script is
  picturable** (abstract language is a defect unless immediately made
  physical). [SHARED]
- **Thesis before script.** One sentence stating the surprising truth
  ("GPS feels instant, but it depends on a fragile chain of clocks moving
  above the Earth"). If you can't write the thesis, kill the topic.
- **Story shape = the source playbook's five-part arc over 6–8 beats:**
  hook (2–3 sentences, 15–20s: premise fast, tension, promised payoff) →
  why it matters → build the system → escalate → **REVEAL (the biggest
  visual moment, around beat 5)** → zoom out to one memorable implication →
  closing + engagement question. Each beat picks up where the last left
  off; if the beats could be shuffled, it's a list, not a story.
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
same schema shape the explainer uses (slug, title, hook, closing, question,
caption, hashtags 10–15 most-specific-first) but long-form sized:
**6–8 segments**, each with a `data_learning/data/curio_*.json` dataset,
insight_type, topic, a `role` that becomes the chapter name ("2 · TWENTY
YEARS DOWN" → chapter "Twenty Years Down"), and a **`say` of 50–90 words
(3–5 sentences)** — total spoken words 550–800. Dataset filenames are
prefixed `curio_` so the two channels' data never collides. Worked
examples: `kola-deepest-hole`, `sitting-still-speed`.

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
YPP thresholds via the long-form path (early access 500 subs + 3,000 public
watch hours/12mo; full share 1,000 subs + 4,000 watch hours — a 4.5-min
evergreen catalog earns watch-hours while it sleeps), then monetize in
layers: ads → affiliates (books, maps, science kits, globes) → digital
products (poster/map packs, template packs) → sponsors → course, in that
order, each only after the previous is earning.

## 12. Wiring & isolation (zero shared-pipeline impact)

- **Token:** `YouTubeUploader(channel="curiosity")` → reads
  `YOUTUBE_TOKEN_JSON_CURIOSITY`; the workflow also accepts the
  operator-created secret name `YOUTUBE_TOKEN_JSON_ORI` (mint with
  `setup_youtube.py` signed into the OpenRangeInteractive account).
  Guard: `YOUTUBE_EXPECTED_CHANNEL` defaults to `OpenRangeInteractive`;
  repo var `CURIOSITY_EXPECTED_CHANNEL` overrides if the channel renames.
- **Config/log/analytics:** `data_learning/curiosity.config.json` ·
  `state/curiosity_posted_log.json` · `state/analytics_curiosity/`.
- **Render:** `data_learning/longform_render.py` (1920×1080 watch-page
  video + `<out>.jpg` thumbnail + `<out>.meta.json` chapters). Tiered
  beat treatments, best available wins: **Blender Cycles hero shot**
  (`blender_hero.py`, the segment marked `"hero": true` — one per video,
  `"hero_invert"` hangs the monoliths downward for depth stories) →
  **Manim motion scene** (`curiosity_scenes.py`: rank/comparison/trend,
  TeX-free) → Pillow still + Ken Burns (loud fallback — a missing tool
  degrades the look, never kills a video). Stories MUST set
  `"keep_order": true` (treatments map config order to story order, and
  a hand-authored arc must never be reshuffled). Kokoro voice primary,
  edge-tts loud fallback.
- **Post:** `scripts/post_curiosity.py` — builds the description
  (caption → chapters block → sources → hashtags → music attribution),
  dedupes on the posted log, refuses videos under 2 minutes, `--max 1`
  for the weekly cadence.
- **Workflow:** `.github/workflows/curiosity.yml` — weekly cron
  (Saturdays 15:00 UTC) posts at most ONE un-posted story; manual modes
  verify / canary / schedule / all / preview; concurrency group
  `curiosity-longform`.
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
2. **~~Shorts-first launch~~ — OVERRULED by the operator (2026-07-08).**
   The original v1 doctrine launched this channel as vertical Shorts with
   long-form as phase 2. The operator killed that: the portfolio already
   has three Shorts channels, and this channel exists precisely to be the
   4–5 minute main-feed play. Long-form IS phase 1; there is no Shorts
   phase. The playbook's format spec (1080p/H.264/AAC/48kHz, chapters,
   large thumbnails, 550–800 words, weekly cadence) applies from video #1,
   implemented by `longform_render.py`. Shorts *cutdowns* of long-form
   videos remain a possible future experiment, but only as trailers for
   the catalog, never as the product.
3. **Tools rule (operator ruling): headless-capable desktop tools are IN,
   GUI-first tools are OUT.** Not "no desktop apps" — the rule is:
   *reliable, fully headless operation through a stable CLI or scripting
   API, integrating into CI without human interaction.* Approved when
   needed: ffmpeg, ImageMagick, Graphviz, Pandoc, Blender (`blender -b` +
   Python API — the render-farm path), GIMP/Krita scripting at the margins.
   Rejected: Inkscape, Kdenlive, DaVinci Resolve, Premiere, After Effects,
   Canva — scriptable at the edges but designed around a human at a GUI.
   The production renderer now runs on exactly this doctrine: Manim
   (pure-Python motion graphics) for data beats, Blender Cycles headless
   for the per-video hero shot, ffmpeg for assembly, Pillow for cards and
   overlays.
4. **Piper/Audacity → Kokoro (+ edge-tts fallback).** Same spirit (local,
   free, reproducible, headless); Kokoro is already cached in CI with
   per-video voice theming and is the pipeline's QA'd voice.
5. **ComfyUI → `gemini_images.py`**, already wired with graceful fallback.
   Generative art stays the last resort, as the playbook says.
6. **Cadence: 1/week posting, queue always ≥2 ahead.** The weekly cadence
   survives (it's a catalog play and matches the playbook), but the
   *authoring* is decoupled from it: the daily routine keeps at least two
   finished stories in the queue so a bad authoring day never creates a
   silent week.
7. **Noto Sans/Sora → the renderer's existing type system.** Consistent
   tooling across channels beats a per-channel font swap; revisit if the
   channel earns a bespoke look.
8. **Google Drive/OneDrive/Dropbox storage plan → this git repo.** Projects,
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
