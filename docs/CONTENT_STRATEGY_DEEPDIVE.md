# Third channel — content deep dive: what's selling vs what we do

**Date:** 2026-07-19 · **Case study:** Streamer University (Kai Cenat's
event, ends 2026-07-20) · **Method:** 208 top #streameruniversity TikToks
scraped via Apify + our own committed YouTube analytics (66 videos) + web
research. Raw scrape datasets: Apify runs `3lRLDBfQDLLMrQHLP` (200 clips) and
`J92dRO4CBF5pSDly1` (validation).

## TL;DR — the problem is NOT how our videos look. It's reach + framing.

Our craft is already competent (shot-planned framing, captions, slow-mo,
replay, SFX, hook card). The numbers say we lose on **distribution and
packaging**, not editing:

- **Our median video gets 10 views** (mean 26, max 194). Only 15% ever
  cleared 50. Retention is actually FINE (median 77%, opening 0.92) — good
  clips that nobody sees.
- **79% of our views come from YouTube SEARCH** (people typing "jynxzi",
  "qt engaged"). The **Shorts recommendation feed — the engine that makes
  clip channels explode — delivers under 10% to us.** We are a search
  utility, not a feed channel.
- **The winners in our exact niche get a median of ~380,000 views** (top clip
  13.4M) — from accounts as small as a few thousand followers. The ceiling is
  not follower count; it's the moment + how it's framed.

## What's SELLING (from 200 top SU clips)

1. **It's reality TV, not gameplay.** Viewers follow PEOPLE and STORYLINES —
   fights, beef, crying, betrayal, breakups, someone getting caught / kicked /
   exposed / disrespected. **29/40 top clips name a specific person**
   (Kai Cenat, Crystal, Yonna, Rakai, TPain, Skai Jackson). The recurring
   breakout wasn't a streamer's gameplay — it was **Crystal's drama arc**
   (bullied → kicked off → "losing her mind"), clipped over and over.
   Representative top captions:
   - "Kai Cenat starts CRYING and ENDS the stream after Rakai BROKE…" (4.1M)
   - "Me and Marlon broke up 😕💔" (5.7M)
   - "Crystal was so SAD after this girl kept being RUDE to her" (2.4M)
   - "Kai Cenat is CRYING and has EXPELLED everyone" (3.5M)
2. **Titles are narrative curiosity-gaps, not search copy.** [Name] + [the
   dramatic beat] + [a tease that makes you tap]. Emotional stakes up front.
3. **Short wins.** On TikTok, **0–15s clips have the highest median views
   (718k)**; most winners are <30s. (We center ~24s — fine, but the very top
   is tighter.)
4. **Original audio (the dialogue) = 85% of winners.** Trending music is NOT
   the lever — the drama itself is the hook.
5. **Small accounts hit millions.** A 6.6k-follower account got 1.7M views.
   The moment + framing carries it, which means **we can win this too.**

## What's NOT selling

- Gameplay mechanics, inside-baseball, "just chatting" with nothing at stake.
- Generic/raw titles. Our own bottom clips are literally "wowza", "Maya is
  one of the professors…" — no name-drama-tease, no reason to tap.
- Slow or context-heavy openings that don't state the drama immediately.

## Where WE diverge (the gap)

| Axis | Winners | Us (before this change) |
|---|---|---|
| Subject | drama characters + storylines | streamer velocity ranking |
| Title | [name] + drama + curiosity gap | "[Streamer] [event] [object]" (search copy) |
| Framing | reality-TV stakes stated instantly | competent but neutral |
| Reach | Shorts/TikTok FEED | 79% search, <10% feed |
| Hashtags | name + event first | generic (clips/gaming) |

Our editing was never the bottleneck. We were packaging feed content like a
search catalog, and selecting by "which streamer is spiking" instead of
"which human drama is the internet already watching."

## Changes shipped in this pass (packaging + selection rebuild)

Reach is driven by **moment + packaging**, so that's what changed (no re-skin
of the already-good render):

1. **Author title/hook rebuilt** (`third_capture/author.py` SYSTEM) — the
   title formula is now [WHO by name] + [dramatic/emotional beat] +
   [curiosity gap]; the hook is a swipe-stopping stakes tease. Explicit
   "this niche is reality TV — follow people and drama, not mechanics."
2. **Banger pre-scorer sharpened** (`_RANK_SYSTEM`) — now scores for what the
   FEED pushes: human drama (fights/beef/crying/betrayal/caught/exposed) and
   live-storyline moments score HIGH; gameplay/insider scores LOW.
3. **Event/name-first hashtags** — the author now leads hashtags with the
   person's name and the live event/storyline, generic tags last.
4. **`drama` + `beef` series** added (`author.py`, `auto_edit.py`) so the
   human-drama categories are first-class with their own overlays.

## Recommended next (needs operator input / more build)

- **Source the drama characters, not just streamers.** The breakout clips
  came from SU cast members (Crystal Izaguirre, Yonna, Rakai, Skai Jackson,
  TPain) who are NOT in our Twitch sources list. Add their handles (verify
  first) so we can clip the storylines people already follow. This is the
  single biggest untapped lever.
- **Speed / first-to-post.** The first channel to a viral moment takes most
  of the views. Measure and shrink live-moment → upload latency.
- **Feed-reach feedback.** Extend the learned prior to optimize the
  Shorts-FEED traffic share (already in our analytics) — not just views.
- **Format templates** (story/context framing, event-recap) as
  director-selectable forms, each earning its slot via the feedback loop.

## How we'll know it worked

The metric is **reach, not retention**: watch median views and — critically —
the **Shorts-feed traffic share** (today <10%) climb in
`state/analytics_third/`. Canary the new packaging on the next batches and
compare to the ~10-view baseline over the following week.
