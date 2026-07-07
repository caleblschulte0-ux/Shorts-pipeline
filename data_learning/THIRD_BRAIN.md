# THIRD CHANNEL ("third") — brain playbook: THE CLIPPER

**The channel:** a Twitch/Kick clip channel. **We find the moments already
blowing up live, add our edit layer, and ship them as Shorts.** This is the
safest, most middle-of-the-road guaranteed-views lane on the platform: the
content is pre-validated (a clip pulling 10k views on Twitch in a day has
already won its A/B test with a live audience), the supply is infinite and
daily, and the audience is the broadest on YouTube.

The channel slug is `third`; every package sets `"channel": "third"` and
the uploader routes it to the `YOUTUBE_TOKEN_JSON_THIRD` secret. See §10
for wiring. Operator direction 2026-07-07 (permanent doctrine): mass
audience → millions of views → brand → affiliates/products/sponsors.
Entertainment first. No B2B, no office tools, no niche-utility content,
ever.

---

## 1. Identity (one swipe)

**The best live moments on the internet, edited to hit.** Streamer
freakouts, clutch plays, perfect comedic timing, wholesome chaos — the
moments people already clip, quote, and repost, delivered clean: instant
hook, big word-pop captions, tight cut, loud clear audio, credit on
screen.

## 2. Sourcing doctrine (what gets clipped)

- **Pre-validated only.** We never guess what's funny. The scout pulls
  each allowlisted channel's top clips of the last 24h sorted by views
  (no API key needed — `third_capture/clip_edit.discover`). A clip
  qualifies when its source views clear the package's `min_views` bar.
  Twitch's own viewers are our test audience.
- **Allowlist, not open season.** We clip only channels on the package
  allowlist. Preference order: (1) streamers with official clipping/
  content programs or explicit permission, (2) major streamers who
  publicly welcome clip channels. The operator owns the allowlist;
  the brain may propose additions, never add them.
- **The 1-second rule still applies.** The moment must land with zero
  stream context — a scream, a fail, a jackpot, a perfect line. If it
  needs lore, skip it.
- **Banned content:** harassment/drama-bait targeting private people,
  slurs or TOS-violating source material, sexualized content, gambling
  sponsorship segments, anything mid-apology/mid-controversy. Skip the
  clip, keep the channel safe — this is the yellow middle of the road.

## 3. Credit & takedown doctrine [ABSOLUTE]

- Streamer handle burned on screen for the FULL duration (credit banner)
  + source link and clipper credit in every description.
- Any streamer/rights-holder removal request is honored immediately and
  the channel goes on the internal blocklist. No arguing, no delay.
- No raw reuploads, ever: every video carries our full edit layer
  (reframe, hook, captions, cut, loudness) — both for YouTube's
  reused-content/originality rules and because the edit IS the product.
- Never imply the streamer endorses this channel or any sponsor.

## 4. The edit layer (what makes it OURS)

Built in `third_capture/clip_edit.py`, applied to every clip:

1. **Hook card** (first ~3s) — a 5-8 word tension line in plain English
   ("HE DID NOT EXPECT THIS…"). Written per-clip by the brain; never
   clickbait that the clip doesn't pay off.
2. **9:16 reframe** — blurred zoom-fill background + source centered.
   (Next upgrades: facecam/action crop layouts, punch-in zooms on the
   payoff beat, reaction freeze-frames.)
3. **Word-pop captions** — whisper word timestamps, 1-3 word ALL-CAPS
   pops, styled thick-outline white; the video must work muted.
4. **Tight cut** — trim dead air before the moment; get to the payoff
   fast; end within ~1s after it lands (`start`/`end` per package).
5. **Credit banner** — permanent `twitch.tv/<streamer>`.
6. **Loudness normalize** (-14 LUFS) — screams hit, mumbles are audible.

House rule: hook card answers "why watch", captions carry the dialogue,
the cut removes everything that isn't the moment. If the edited clip is
over ~45s, cut harder.

## 5. Daily operation

1. Scout the allowlist (top clips, last 24h, by views).
2. Rank by source views-per-hour; drop anything already posted
   (`source_url` dedupe in the posted log) or banned by §2.
3. For each pick, the brain writes: hook line, cut points, title.
4. Render + eye-QA (captions in safe area, hook readable, credit visible,
   payoff inside the cut) → upload, spaced through the day.
5. Log everything to the ledger for the learning loop.

Cadence: start **3/day** (clips are cheap), scale with watch signals.
Freshness beats polish — a 6-hour-old exploding clip outranks a better
edit of yesterday's.

## 6. Titles & packaging

- Title = the moment, not the streamer: "He opened the one box he
  shouldn't have" > "xQc funny moment #347". Streamer name goes in
  description/tags (their search traffic still finds it).
- No #shorts spam, a few relevant tags, no emoji walls (one is fine).
- Thumbnails don't matter for Shorts; the first frame does — the cut
  must open ON motion or ON the face, never on dead air.

## 7. Learning loop [SHARED — `LEARNING_LOOP.md` is law]

Staged scorecard, `state/brain_context.json`, no auto-adaptation below
~100 views/video, bounded reversible edits. Clip-channel additions to the
ledger per upload: `streamer`, `source_views`, `source_age_h`, `category`
(fail/clutch/funny/wholesome/scare), `hook_text`, `cut_length_s`,
`caption_density`. Learn: which streamers convert HERE (not on Twitch),
which categories retain, whether tighter cuts beat longer context, and
which hook styles survive the first 3 seconds. Winners: more of that
streamer/category same week. Losers: 30-day ban on the pattern, not the
streamer.

## 8. Monetization

Reach → brand → then: streamer-adjacent sponsors (energy, peripherals,
games), affiliate links, and eventually direct streamer partnerships
(official clip deals — clip channels big enough get PAID by streamers'
teams). Platform payouts last. Nothing that makes a video feel like an ad
before the channel has pull. Disclose every paid relationship (FTC),
always.

## 9. Rendering pillars kept in the toolbox

The channel is a clipper first, but `third_capture/` retains two original
renderers usable as in-between content or B-sides, both truthful by
construction: `sim_video.py` (full-frame escalating physics sims) and the
real-run capture/composer stack. The brain may propose them; the operator
decides if/when they slot in.

## 10. Wiring & isolation (zero shared-pipeline impact)

- **Token:** `YouTubeUploader(channel="third")` → secret
  `YOUTUBE_TOKEN_JSON_THIRD` (mint via `setup_youtube.py` signed into the
  new channel's account; shared OAuth app).
- **Guard:** repo var `THIRD_EXPECTED_CHANNEL` → `YOUTUBE_EXPECTED_CHANNEL`
  in `third.yml`, so a mis-set token can never post to the other channels.
- **Packages:** `state/third_packages/YYYYMMDD/` — `capture.kind:
  "twitch_clip"` with `channels` allowlist (or explicit `clip_url` +
  `credit`), `min_views`, optional `start`/`end` cut, `hook`.
- **State:** `state/third_posted_log.json` (dedupes by `source_url`);
  analytics `fetch_analytics.py --channel third` → `state/analytics_third/`.
- **Workflow:** `third.yml` (concurrency `third-shorts`);
  `daily.yml`/`explainer.yml` are never touched.

Operator setup checklist: create the channel + @handle → mint
`YOUTUBE_TOKEN_JSON_THIRD` → set `THIRD_EXPECTED_CHANNEL` → approve the
starting streamer allowlist → merge and run the workflow.
