# THIRD CHANNEL ("third" / @Thirdbraindown) — brain playbook: THE CLIP DESK

Operator playbook v3 (2026-07-07). **We are not a clip mirror. We are a
mobile newsroom for one streamer universe.** Status tags: ✅ implemented in
the pipeline · 🔜 roadmap.

The channel slug is `third`; every package sets `"channel": "third"` and
the uploader routes to `YOUTUBE_TOKEN_JSON_THIRD`. Wiring in §12. Operator
doctrine (permanent): mass audience → millions of views → brand →
affiliates/products/sponsors. Entertainment first; no B2B/niche-utility
content ever; rights respected (credit + instant takedown, §3).

---

## 1. Thesis and identity

**One streamer cluster, not all of streaming.** Single-franchise depth
beats broad aggregation: recurring characters, recurring stakes, cleaner
analytics, repeatable audience promise.

> **"We turn the most chaotic, funniest, highest-stakes moments from the
> Kai Cenat / ex-FaZe crew universe into fast, context-rich mobile
> stories."**

| Identity element | Choice |
|---|---|
| Audience promise | You will never miss the most insane moment from this crew |
| Emotional promise | shock, embarrassment, wins, rage, chat betrayals, wholesome reversals |
| Editorial stance | fast, witty, context-first, never slow |
| Format promise | every clip understandable in <2s cold, even muted |

**Core cluster (score weight 1.0) ✅:** kaicenat, lacy, silky,
stableronaldo, jasontheween, rayasianboy, kaysan, plaqueboymax,
lospollostv. **Fallback supply (weight 0.45) ✅:** xqc, jynxzi, caseoh_
(+ kick:adinross, rumble:AdinLive when reachable). Fallback exists so a
quiet crew day still ships; the brand is the crew. Operator owns both
lists (`state/third_packages/default_clip.json`).

Consistent visual system: same caption font (Anton), same hook-card
logic, same credit banner on every upload — viewers recognize the channel
in one frame. High-clarity, face-first, motion-first; never cinematic
overdesign.

## 2. Sourcing and selection

Three layers:
1. **Platform-native discovery ✅** — per-channel top clips of the last
   24h (yt-dlp, no keys; Twitch Helix `Get Clips` is the 🔜 upgrade for
   `created_at`/`vod_offset`/game filters — needs TWITCH_CLIENT_ID/SECRET).
2. **Velocity ranking ✅** — global shortlist re-ranked by views-per-hour
   (age probed per clip) × franchise-fit weight. A 2h-old clip at 5k beats
   a 20h-old one at 8k.
3. **Floors ✅** — `min_views` 2500; thin-day relaxation to `min_views_floor`
   800 (warned in logs) so a slot is never lost to a quiet day.

Priority score = source signal + moment intensity + context clarity +
novelty + franchise fit − saturation penalty. Implemented today: source
signal (views), velocity, franchise fit, dedupe (`source_url`). 🔜: chat
spike counts, novelty/saturation penalties from the ledger (same joke /
same game too often), VOD highlight mining.

Selection rule: **clip moments with standalone narrative shape** — a
scream, a fail, a jackpot, a betrayal, a perfect line. If it needs stream
lore, skip it. Banned (unchanged): harassment/drama-bait on private
people, slurs/TOS-violating source, sexualized content, gambling segments,
mid-controversy content.

## 3. Credit & takedown [ABSOLUTE, unchanged]

Streamer handle burned on screen full duration ✅ + source link & clipper
credit in every description ✅. Any removal request honored instantly;
channel goes on the blocklist. No raw reuploads ever — the edit layer is
the monetization qualifier (non-original Shorts are ineligible) AND the
product. Never imply streamer endorsement.

## 4. Editing and packaging

Everything happens in three windows: **0–3s, 3–10s, final payoff.**
Master: 1080×1920 H.264/AAC ✅, no baked bars, loudness −14 LUFS ✅.

**Framing rule:** if a face exists, the face wins; if no face, the
decisive action wins; both → alternate aggressively. **Two-stage
auto-editor ✅** (`third_capture/auto_edit.py`): Stage 1 retimes the clip
into a dynamically edited program (motion+speech locate the "money
moment"; punch-in zoom on the reaction, `minterpolate` slow-mo + instant
`REPLAY` of the payoff, dead-air speed-up, impact shake/flash/aberration);
Stage 2 face-tracks the reframe (OpenCV Haar cascade → EMA-smoothed 9:16
crop that fills the frame — no blur bars — when a confident face track
exists, else blur-fill center). A **style selector** applies effects with
discretion per `series` and clip strength (wholesome → gentle punch, no
shake/replay; fail/rage → full package; weak/flat clips → minimal), and an
**ironclad fallback ladder** (per-effect → per-segment plain re-encode →
whole-Stage-1 skip → blur-fill reframe → today's simple render) guarantees
every clip ships; each fallback is logged in the ledger
(`auto_edit`/`fallback_reason`/`effects`/`edl`). Behind `auto=True`.

**Never start with dead air ✅** — auto tight-cut opens ~0.8s before the
first spoken word, ends ~1.5s after the last, hard cap 45s. Never open on
scene setup or "hello".

**Hook = compressed conflict.** First card 4–8 words: one emotional
label + one subject + one implied consequence ("CHAT SET HIM UP SO
BADLY"). Written by the Claude author (Groq fallback) from the transcript ✅ — honest to the
clip, never clickbait it doesn't pay off.

**On-screen text rules ✅:** captions 1–3 words per pop, ALL CAPS Anton,
thick outline + shadow, pop-in scale, one yellow-emphasized word per
group, positioned below the clip (y≈1350 — clears Reels' bottom-35%
danger zone and TikTok safe zones for future cross-posting). Expressive
face → fewer overlays.

**Edit templates** (the brain picks per clip 🔜 explicit; today the tight
cut + hook approximates "instant punchline"):

| Template | Hook window | Payoff |
|---|---|---|
| Instant punchline | open ON the reaction/fail frame + 4-6 word card | immediate aftermath, one reaction beat |
| Escalation | the threatening clue first | fail/win + release |
| Reversal | confidence line first | hard reversal + close-up |
| Argument | strongest line first, filler stripped | final line / stunned silence |

**Sound:** source-first — the streamer's audio IS the asset ✅; **CC0
impact SFX ✅** (self-authored numpy one-shots in `assets/sfx/`, zero
licensing risk — whoosh on the punch-in, boom on the peak hit, riser into
the replay) mixed onto the Stage-1 beats via `adelay`|`amix`, **no music
bed** (licensing risk). Asset-guarded — missing files skip silently.
**Cover frame 🔜:** one readable face or decisive action, 2–4 words, high
contrast (matters on channel-page surfaces, not feed).

## 5. Metadata

- **Title formula ✅:** [Streamer] + [emotional event] + [object/context]
  — "Kai Cenat Realizes Chat Set Him Up". Clarity first, emotion second,
  keyword third. Groq-authored from transcript; raw clip titles ("v")
  never ship when the author is up.
- **Hashtags ✅: 2–4 only** (YouTube surfaces 3 by the title; over-tagging
  reduces relevance). Authored per clip.
- **Tags field ✅: sparse name variants** ("kaicenat", "kai cenat clips"…)
  — tags play a minimal role beyond misspellings.
- **Description ✅:** sentence 1 = what happened; sentence 2 = source
  credit + link; hashtags. Short.
- **Series shelves ✅ label / 🔜 playlists:** every clip gets a series
  label (rage / chat-betrayal / jumpscare / clutch / fail / win /
  wholesome / argument / chaos) in the ledger; identity-based playlists
  ("Chat Betrayals", "Best of the Crew This Week") via API next.
- **Related-video linking 🔜** — point each Short at a recap/another
  Short; no dead ends.
- **Every language ✅:** titles + descriptions localized to ~29 languages
  (`localize.ALL_LANGS`) on every upload.

## 6. Cadence and CI

- **3/day ✅** via daily cron (11:00 UTC) → publish slots 17:00/19:00/21:00
  UTC. Packages self-synthesize from `default_clip.json` when none are
  authored ✅ — the machine never has a no-op day.
- Scale 4–5/day only when the QA pass rate holds (days 91+, §10).
- Publish time is not a growth lever (YouTube's own guidance) — slots
  exist for early data density, not mythology.
- 🔜 split jobs: scout every 2–4h, render 2–3×/day, nightly analytics
  (today: one daily run + `fetch_analytics.py --channel third`).
- Weekly long-form recap 🔜 phase 2 (watch-page RPM + mid-rolls).

## 7. Analytics learning loop [LEARNING_LOOP.md is law]

Daily ingest per video ✅ views/likes/vph + retention where exposed;
🔜 full set: shown-in-feed, viewed-vs-swiped, engaged views, avg view %,
1s/3s/7s retention, retention curve (`elapsedVideoTimeRatio`), traffic
split, subs gained — joined to hook template, series, streamer, caption
density, cut length from the ledger. NOTE: Shorts `viewCount` counts
plays with NO minimum watch time (2025-03-31 change) — never optimize on
raw views; engaged views + avg view % + viewed-vs-swiped are the truth.

**Operating thresholds** (internal control limits for 15–45s clips;
recalibrate per duration bucket + streamer after ~100 uploads; no
auto-adaptation below ~100 views/video):

| Metric | Green | Red | Action if red |
|---|---:|---:|---|
| Viewed vs swiped | ≥38% | <30% | rebuild first second / opening frame / premise card |
| 1s retention | ≥78% | <68% | change first frame, tighter crop, kill intro air |
| 3s retention | ≥65% | <55% | replace hook copy, start later in the moment |
| 7s retention | ≥48% | <38% | compress setup, more motion, fewer words |
| Avg view % | ≥85% | <70% | clip too long / payoff weak — cut harder |
| Subs /1k views | ≥3 | <1 | identity weak — series naming + niche clarity |
| Share rate | ≥0.7% | <0.25% | more universally legible moments |

**Failure→action mapping:** weak viewed-rate = packaging (never topic
first); 1s good but 3s/7s collapse = setup too long, start later;
retention spikes late = move that beat to the open next time; high
retention + low reach = narrow the niche, harden series identity; high
shares + low comments = add pinned question + sequels; high comments +
weak retention = keep topic class, rebuild the format.

**Frame-mapped retention 🔜 (highest-value build):** join retention
buckets to frame grabs, caption windows, face-size and audio-intensity —
"what was on screen when 3s retention failed?"

**A/B rules:** one variable per experiment, 20–30 clips per condition,
same cluster + duration band, randomized slots. Candidate tests: opening
frame, 4- vs 8-word card, punchline-first vs setup-first, facecam- vs
gameplay-dominant, 18–24s vs 28–35s cuts, streamer-first vs event-first
titles.

**The 90-day bar:** the brain must be able to explain in writing why the
last 20 winners won and the last 20 losers lost. That's the difference
between a system and uploads.

## 8. QA gates (before every publish)

Five tests: cold-view clarity <2s · mobile dominance (subject centered) ·
caption legibility (never covering face or bottom-35%) · pacing (no dead
second unless deliberate tension) · payoff density (ends on a reaction/
reversal/line). Human spot-check + brain answers in structured form: the
clip's emotional promise, why a cold viewer stops, the one context
sentence, the first likely drop-off point, which similar past clip failed
this same way, and the sequel opportunity if it hits.

## 9. Monetization stack (in order)

1. Shorts ad revenue (YPP: 500 subs + 3M Shorts views/90d early access;
   1k subs + 10M/90d full share at 45%) — requires the value-add edit
   layer, which is doctrine anyway.
2. Weekly long-form recaps (55% share, mid-rolls at 8+ min) 🔜.
3. Affiliate commerce (gear/peripherals; Shorts product tagging).
4. Memberships (70% share) — members-only weekly best-of.
5. Sponsorships (gaming/energy/peripherals) — disclosed, never before the
   channel has pull.
6. Licensing/service: the channel is the demo reel for an official clip
   desk streamers pay for.

**Use Shorts to acquire, long-form to deepen, Shopping/memberships to
monetize, sponsorships to multiply.**

## 10. KPI roadmap (high-growth targets, not guarantees)

| Horizon | Output | Growth | Quality |
|---|---|---|---|
| 90 days | 180–270 Shorts, 3/day, one clear niche | 5–20k subs, 0.5–3M monthly views | median viewed-rate >35%, avg view % >75%, top-3 series identified |
| 180 days | +weekly recap | 20–75k subs, 3–15M monthly | viewed-rate >38%, winner archetypes documented |
| 365 days | 1,000–1,500 Shorts, mature automation | 75–250k subs, 15–60M monthly | 80% of uploads pass green/yellow |

## 11. Toolbox (B-sides)

`sim_video.py` (escalating physics sims) and the real-run capture stack
remain available for original in-between content — also useful for the
originality profile of the channel. Operator decides if/when.

## 12. Wiring & isolation (zero shared-pipeline impact)

- Token: `YouTubeUploader(channel="third")` → `YOUTUBE_TOKEN_JSON_THIRD`;
  guard `YOUTUBE_EXPECTED_CHANNEL` defaults to `Thirdbraindown`.
- Discovery/edit: `third_capture/clip_edit.py`; authoring:
  `third_capture/author.py` (GROQ_API_KEY); orchestrator:
  `scripts/run_third.py`; workflow `third.yml` (cron 11:00 UTC daily,
  concurrency `third-shorts`).
- Packages: `state/third_packages/YYYYMMDD/` or self-synthesized from
  `state/third_packages/default_clip.json` (core/fallback lists live
  there). State: `state/third_posted_log.json` (source_url dedupe),
  analytics → `state/analytics_third/`.
- `daily.yml` / `explainer.yml` are never touched by this channel.
- 🔜 needs from operator: TWITCH_CLIENT_ID/SECRET (Helix upgrade),
  decision on comment seeding (API can post but not pin — manual op),
  Kick/Rumble access route (bot-walled from CI today).
