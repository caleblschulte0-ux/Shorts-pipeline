# THIRD CHANNEL ("third") — brain playbook: PROOF MODE

**Working title:** *Proof Mode* — a proof-first, faceless software-workflow
channel. **Positioning: "One workflow. One visible result. No hype."**

The channel slug is `third`; every package sets `"channel": "third"` and the
uploader routes it to the `YOUTUBE_TOKEN_JSON_THIRD` secret. See §13 for
wiring and isolation. This playbook supersedes the earlier survival-stories
concept for this slug (preserved in git history at c364670 if ever wanted
for a fourth channel).

This file is the channel. Scout, validators, uploader, learning loop are
shared infrastructure; the doctrine below is what makes Proof Mode itself.
The brain reads this file first and treats it as law. Operator feedback gets
written back INTO this file as permanent doctrine.

---

## 0. Strategy and the honest constraint

**The bet:** intersect search intent with visible proof. Don't ask what
topic is trending — ask what task people are trying to solve, then prove a
visible result fast. Audience: students, creators, freelancers, founders,
office workers searching "can this tool do X" / "fastest way to Y" /
"A vs B". Monetization potential (sponsors, affiliates, template/prompt
packs) is structurally better than facts/news entertainment niches, and the
niche is naturally 9:16-visual.

**The honest constraint (operator-acknowledged):** this channel's iron gate
is REAL screen proof, and the pipeline today cannot produce a single frame
of it — the renderer composes stock/AI imagery and procedural games. AI
imagery standing in for software proof would violate the channel's own core
rule and make every "I tested" claim a fabrication. Therefore:

> **Phase 0 blocks everything.** No Proof Mode video ships until the
> capture harness (§10) exists: headless Claude in CI actually PERFORMS the
> task (Playwright + the preinstalled Chromium, or a CLI under asciinema/
> script), records the screen with ffmpeg, and emits a proof ledger (run
> log, timings, input/output artifacts). "I tested" must mean "CI ran it."

This also means the *entire moat is real proof*. The niche is flooded with
AI-slop listicles; the only durable differentiation is that our results are
demonstrably real — including honest FAILs, which are content, not waste.

## 1. Identity (one swipe)

**Every Short proves a real outcome on screen: the input, the steps, the
output.** Never listicles, never "top 5 AI tools", never generic AI news,
never vague promises. Skeptical, practical, fast, never guru-ish. Value
delivery is task transformation, not facts (channel 2) or events (channel 1)
— zero cannibalization.

## 2. The iron gate (a package may not enter the queue unless…)

> It answers **one plausibly-searched question** ("Can this tool do X?",
> "Fastest way to Y?", "A or B?"), the task was **actually executed by the
> harness** with a proof ledger attached, the result is **legible in
> vertical video without pausing**, and the demo needs **no private or
> risky data** (synthetic fixtures only).

Reject even if trending:
- Anything whose proof can't be shown on screen or requires trusting the
  narration.
- Trivial or visually boring tasks; tasks needing >4s of setup narration.
- Claims depending on unclear benchmarking. Time/cost/performance numbers
  appear ONLY if measured in the production run or labeled example/demo.
- Roundup/listicle framing — commoditized, monetization-fragile.
- Tools we can't actually run headless in phase 1 (see §10 scope).

## 3. Angle-derivation rule for the scout pool

From trend/search sources, extract **the underlying TASK a person is trying
to get done — never the tool announcement itself.**

- "New AI model released" → not "X launched" → **"Can it turn a messy voice
  note into a client-ready memo? Tested."**
- "Layoffs / job market trends" → **"The 15-minute workflow that makes a
  portfolio site from a resume."**

Scout stack, in priority order: YouTube Trends tab (top searches, breakout,
Shorts content gaps) → TikTok Creative Center trends (public) → Google
Trends (durability, geography) → official product release notes/changelogs
→ official help-center docs (confirm what the tool actually does BEFORE
authoring). Operator-fed inputs (TikTok Creator Search Insights) are
welcome but never assumed automatable.

**Topic score (100 pts):** search demand 30 · Shorts content-gap fit 20 ·
visual proof potential 15 · evergreen durability 15 · monetization fit 10 ·
source reliability 5 · production ease 5. Every upload logs its
trend-source lineage.

## 4. Editorial pillars

| Pillar | Qualifies | Rejected |
|---|---|---|
| **AI tool trials & workflow proofs** (spine) | "can it do X" tests, prompt iteration ladders, messy-input→clean-output | slow screen tutorials, tool-news recaps |
| **Task showdowns** | A-vs-B on the SAME task with the same fixture, stamped verdicts | vague "which is better" opinion |
| **Workflow deletions** | "this removed N clicks/steps", automation of a repetitive desk task | unmeasured time-saved claims |

Seed weights from this channel's OWN analytics once available; retrieval
overweights **format similarity over topic similarity** (the best analog
for an email-cleanup Short may be a spreadsheet-cleanup Short with the same
proof template).

## 5. Format: the four beats (master ≈ 28–42s)

1. **Pain or impossible result** — first 1–2s shows the pain, the result,
   or a before/after contrast. Never branding.
2. **Task setup** — the messy input, visibly imperfect. One sentence.
3. **Workflow proof** — the actual run, compressed. One sentence.
4. **Payoff + future-oriented CTA** — stamped verdict, never generic
   "follow for more".

One sentence of narration per beat; captions must carry the claim muted.
One master timeline; platform wrappers (when they exist, §11) change
opening card / caption density / cover only — never a re-edit.

**Retention doctrine [SHARED — platform truth]:** first second = proof, not
setup; something meaningful changes every 0.6–1.2s (cursor, card, reveal,
comparison, verdict); context never before intrigue; the final line
escalates, inverts, or resolves. The three retention failures and their
fixes are as defined in `LEARNING_LOOP.md` §1.

## 6. Visual system (proof motion, not gameplay strip)

**This channel does NOT use the stacked gameplay/themed-bottom format.**
The capture IS the visual. It needs its own render path (§10): full 9:16
clean master, no watermark/border, critical text inside x 70–1010 /
y 160–1580 (house guardrails, not platform specs).

Element kit the brain recombines:

| Element | Purpose | House rule |
|---|---|---|
| `task_card` | the task in plain English | one line only |
| `input_frame` | messy source material | must be visibly imperfect |
| `cursor_path` | action path | only when action matters, never decorative |
| `split_compare` | before/after, A/B | the default proof element |
| `stopwatch_tag` | measured task time | only if actually measured |
| `output_card` | result asset | must feel real and usable |
| `redaction_box` | privacy masking | aggressive on any sensitive screen |
| `proof_stamp` | WORKED / FAILED / PARTIAL | one-word verdict |
| `micro_chart` | tiny comparison | accent only, never full frame |

Proof-motion mechanics: click-race (compressed clicks + time delta), diff
wipe, inbox drain, prompt ladder, tab collapse, error radar (fails get red
marks, winner gets green lock-on).

**Asset doctrine:** our own screen captures are the proof layer, always.
Stock (Pexels/Pixabay/Wikimedia, license-checked) only for context shots.
AI-generated visuals are accents (transition cards, thumbnails) and may
NEVER stand in for software proof. AI-content disclosure stays ON.

## 7. Truthfulness invariants [ABSOLUTE — no brain may break these]

- Every on-screen and spoken claim maps to an entry in that video's proof
  ledger. No measured-sounding number without a measurement.
- A FAIL or PARTIAL result ships honestly framed — often outperforms, and
  it's the credibility engine.
- If the tool demo breaks, **kill the package** — never improvise claims.
- Synthetic fixture data only; redaction QA on every frame; no real
  personal data ever on screen.
- FTC-clear disclosure of any material relationship (sponsor/affiliate),
  plus platform commercial-content toggles. Never hidden, ever.
- No near-duplicate mass production (YouTube originality/monetization risk
  — and it's brand death in this niche).
- AI-use disclosure ON for TTS narration.

## 8. Package output schema

New package type (not the explainer schema — different renderer):

```json
{
  "channel": "third",
  "topic_cluster": ["email", "AI writing"],
  "search_intent": "plain-English query this answers",
  "tool_name": "…",
  "task_definition": "…",
  "proof_plan": "what the harness will execute + record",
  "measured_claims": [{"claim": "…", "source": "ledger key"}],
  "hook_options": ["3 candidates"],
  "scene_plan": ["element kit + mechanics per beat"],
  "risk_flags": ["paywall", "account", "flaky"],
  "disclosures": ["ai_tts"]
}
```

Three hooks, one body, one close per package; render only the winning
master (optionally cheap-prerender the first 4–6s to pick the hook).

## 9. QA (pre-render and render-time)

Pre-render reject: not demonstrable on screen · trivial/boring · unclear
benchmark · needs private data · illegible vertical.
Render-time verify: result visible by second two · captions in safe zones ·
zero sensitive-info leaks (automated + eye pass) · purposeful cursor ·
verdict matches the ledger (worked/partial/failed).
Then the shared eye-QA loop: render beat-final frames + 25/50/75% samples
and LOOK; fix → re-render → re-look until every frame passes.
**Non-negotiable.**

## 10. Phased build plan (each phase gates the next)

**Phase 0 — capture harness (blocks all uploads).**
`third_capture/`: Playwright + preinstalled Chromium (or `script`/asciinema
for CLI tools) performs the task; ffmpeg records; overlay compositor adds
the element kit; proof ledger (JSON: commands, timings, artifacts) saved
per run. Tool scope: **free-tier, headless-runnable tools only** — web apps
without hard auth walls, CLIs, open models. Paywalled tools wait for a
tooling budget (operator decision; accounts cost real money).

**Phase 1 — YouTube only, 1/day.** Not 2/day×3 platforms: every video costs
a real CI tool-trial, TikTok posting needs app approval (sandbox demo only
today) and IG needs Meta business tokens. Prove hook-survival and retention
on 30–50 uploads first. 10–15% of uploads are controlled experiments —
**one variable per batch** (hook archetype, first-frame, caption density,
CTA, verdict framing).

**Phase 2 — scale + affiliates.** 2/day when QA holds; affiliate links,
template/prompt vault, related-video links funneling to longer breakdowns.

**Phase 3 — TikTok/IG wrappers + sponsorships.** Only when posting APIs are
approved and the format is proven. Sponsor fit: SaaS/productivity, note
tools, email/meeting software, no-code, browser extensions, honest career
services. Never: crypto/speculation, get-rich offers, low-trust anything.

Fallbacks: scout fails → last valid scout cache · demo breaks → kill
package · upload fails → reschedule, never blind-repost · sponsor asset
conflicts with disclosure/originality → reject · a template family's
retention collapses → pause the family, expand exploration.

## 11. Learning loop [SHARED — `LEARNING_LOOP.md` is law]

Staged scorecard, `state/brain_context.json`, shot-aligned retention map,
**no auto-adaptation below ~100 views/video**, bounded reversible edits
only. Channel-specific additions:
- Ledger every upload in the shared `video_ledger` pattern with:
  `search_intent`, `tool_name`, `hook_template_id`, `scene_mechanics`,
  `claim_type` (measured/qualitative/comparison), `proof_status`
  (worked/failed/mixed), `trend_sources`, beat-level annotations
  (`beat_type`, `proof_visible`, `change_events`, `drop_marker`).
- Before writing any script, retrieve the ~15 most similar priors (format
  similarity first) and produce a contrastive memo: nearest winners' shared
  traits, nearest losers' drop points, rules to preserve, patterns banned
  this run.
- House thresholds (tune after 50–100 uploads, treat as operational rules
  not vanity): hook 3s-survival red <75% → rewrite hook library · midpoint
  retention red <55% → compress setup · completion red <30% → move payoff
  earlier · subs/1k views red <0.8 → strengthen conversion promise ·
  saves/1k red <10 → make the workflow more reference-worthy.
- Low reach + high retention = packaging problem. High reach + low
  retention = body/proof problem. Permanent playbook edits only on repeated
  evidence, never one outlier.

## 12. Templates (seed library)

**Hooks:** "Can this AI turn a messy note into a client-ready deck?" ·
"Stop rewriting these emails by hand." · "This workflow deleted 18 clicks
from one task." · "I tried three prompts so you don't have to."
**Titles:** "This AI turned notes into slides in 27 seconds" · "Stop doing
inbox triage like this" · "I tested the fastest way to clean messy
spreadsheet data" · "Can one prompt replace this entire workflow?"
**Closes/CTAs (always future-oriented):** "Verdict: usable if you need
speed." · "Verdict: looks good, breaks on edge cases." · "Tomorrow: same
task, cheaper tool." · "Save this for the next time this task shows up." ·
"Comment the task you want stress-tested."
**Cover lines:** "ONE TASK / ONE RESULT" · "TESTED: DOES IT WORK?" ·
"USE THIS / SKIP THIS".
Hashtags: a few search-aligned tags, never a generic-tag cloud.
English-first; localization only after the format proves itself.

## 13. Wiring & isolation (zero shared-pipeline impact)

- **Token:** `YouTubeUploader(channel="third")` reads secret
  `YOUTUBE_TOKEN_JSON_THIRD` (mint via `setup_youtube.py` signed into the
  new channel's account; shared `YOUTUBE_CLIENT_SECRETS_JSON` OAuth app).
- **Guard:** the channel's workflow sets `YOUTUBE_EXPECTED_CHANNEL` to the
  new @handle so a mis-set token can never post elsewhere.
- **Packages:** `state/third_packages/YYYYMMDD/` — NOT
  `state/trending_packages/` (that dir feeds the shared `daily.yml`).
- **State:** `state/third_posted_log.json`; analytics via
  `python scripts/fetch_analytics.py --channel third` →
  `state/analytics_third/` (already channel-generic).
- **Workflow:** new `third.yml` cloned per `BRAIN_PLAYBOOK_TEMPLATE.md`,
  own concurrency group `third-shorts`, pointed at THIS playbook.
  `daily.yml` / `explainer.yml` are never edited for this channel.
- Until the harness, secret, and workflow exist, nothing runs.

Operator setup checklist: create the channel + @handle → mint
`YOUTUBE_TOKEN_JSON_THIRD` → decide phase-1 tool budget (free-only vs
funded accounts) → greenlight Phase 0 harness build.
