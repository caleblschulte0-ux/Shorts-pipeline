# Daily Routine Instructions

You are running the daily script-writing routine for the Shorts-pipeline channel.

## Pipeline overview

- Faceless YouTube Shorts channel publishing 25-second doomscroll-style explainers
- The daily GitHub Action renders + uploads whatever packages you push
- Your only job is writing the day's 6 script packages and pushing them to the repo

## Steps

0. **Read yesterday's analytics** (only if it exists):
   ```bash
   cat state/analytics/latest.json 2>/dev/null
   ```
   This file has every uploaded video's views, likes, comments, and
   `views_per_hour` (the only fair comparison across ages). Use the
   `summary.top_5_by_vph` and `bottom_5_by_vph` lists to bias today's
   picks: lean toward topic clusters / hook styles that scored high;
   skip topics resembling the bottom five. If the file is missing
   (first run after this loop ships), skip and proceed.

1. **Discover**:
   `GROQ_API_KEY=$GROQ_API_KEY python3 scripts/rank_topics.py --top-k 10`

2. **Pick 6** from the ranker's output. **Two hard rules.**

   **Rule 1 — Freshness.** This is a "today's news" channel. Every
   package should be something that happened in the last 24-48 hours.
   Each ranker line shows an age marker like `[2h ago]`; strongly
   prefer those. Anything that reads evergreen, retrospective, or
   "X has been quietly happening for years" gets cut even when
   interesting. If you can't anchor the package to "this happened
   today / this morning / just announced", skip it.

   **Rule 2 — Category diversity.** This is a WIDE news channel, not
   a tech/AI channel. **Exactly 1 pick per category — 6 distinct
   categories total.** Two shorts from the same bucket read as
   "I just heard that one already" even when the stories differ.

   **Treat Tech/AI + Business/Finance/Markets as a single combined
   "Tech + Markets" bucket** for this cap. An AI startup story and a
   tech-stock story feel visually identical to viewers — pick at most
   1 from the combined bucket, not 1 from each. Draw the 6 from:

   - Tech + Markets (combined: AI, startups, big tech, earnings, stocks)
   - World affairs / Geopolitics
   - US domestic policy
   - Crime / Justice
   - Science / Health / Medicine
   - Climate / Environment / Disasters
   - Culture / Entertainment
   - Sports (one-off moments only)

   The candidate list will skew tech-heavy because Hacker News
   dominates it — resist that. If the ranker returned a tech-heavy
   top 10, drop down its list and pick the highest-scoring item from
   each underrepresented category. If you genuinely can't fill 6
   distinct buckets, ship 5 — better than two same-category dupes.

   Also reject:
   - Live sports or sports-player news (time-locked, narrow audience)
   - Celebrity deaths / obituaries
   - Political horserace stories (elections, primaries, partisan combat)
   - Anything you can't tell in 60 words
   - Topics with no concrete visual story
   - Evergreen explainers ("how X works", "the history of Y")
   - **Ongoing war / conflict coverage where today's update is
     incremental** ("day 47 of...", "fighting continues",
     "casualties rise"). Viewers hit fatigue on repeat war coverage.
     Only include conflict stories if today brought a major escalation,
     breakthrough, ceasefire, named-victim event, or named-leader
     statement — something genuinely new in the arc.

3. **Cross-reference before writing.** Before drafting any script,
   pull the same story from **at least 2-3 different outlets** to
   avoid baking one publisher's slant into the video. The ranker's
   angle field will list which sources flagged each story
   (e.g. "BBC + Reuters + Politico all covering this") — use those.
   If the ranker only saw it in one source, WebFetch the story from
   another outlet (search the topic on apnews.com, reuters.com,
   bbc.com, or the relevant beat outlet) before writing.

   Synthesize across the sources: what do they all agree on (= the
   facts)? Where do they differ (= the framing)? Write the script
   from the facts. Keep the framing neutral — no editorializing,
   no left/right loaded vocabulary, no "X is bad because..." or
   "Y is finally..." phrasing. The audience should feel informed,
   not convinced.

4. **Write packages** to `state/trending_packages/$(date -u +%Y%m%d)/0N_slug.json`,
   one per pick.

5. **Commit, push, AND open a PR**. You're probably running on an
   isolated worktree branch, not directly on main, so a plain
   `git push` puts your work on a feature branch that nobody renders
   from. You MUST also open a pull request — that's what the auto-
   merge workflow watches:

   ```bash
   git add state/trending_packages/$(date -u +%Y%m%d)/
   git commit -m "daily packages $(date -u +%Y-%m-%d)"
   git push -u origin HEAD
   ```

   Then create the PR. Prefer the GitHub MCP tool if available
   (`mcp__github__create_pull_request` with `base: main`, `head:`
   your current branch name). Otherwise use `gh`:

   ```bash
   gh pr create \
     --base main \
     --title "daily packages $(date -u +%Y-%m-%d)" \
     --body "Today's batch from the morning routine."
   ```

   Auto-merge.yml watches every `claude/*` PR and lands it within
   ~30 seconds. The merge to main fires daily.yml via workflow_run,
   which renders + uploads everything you wrote. **If you skip the
   PR step, NOTHING ships.**

## Script package format

Reference: `state/trending_packages/20260531/*.json`.

Schema:
```json
{
  "title": "Punchy 6-10 word YouTube title",
  "script": "60-80 word script, hook + facts + kicker",
  "shots": [
    {"phrase": "verbatim substring of script", "image": "https://...", "query": "stock fallback"}
  ],
  "punches": [
    {"phrase": "verbatim substring", "text": "1-3 ALL CAPS", "color": "#hex"}
  ],
  "hashtags": ["topical", "tags", "specific", "to", "this", "story"],
  "music_vibe": "dark | cinematic | hiphop"
}
```

## Hashtags

Write **10-15 topical hashtags per package** in the `hashtags` field.
The orchestrator dedupes and merges with a baseline set (`#shorts #news
#explainer #trending #viral #fyp` etc.) before uploading. Algos weight
the first 3-5 hashtags hardest, so put the most specific topical ones
at the front:

| Topic                  | Good topical hashtags                                         |
|------------------------|---------------------------------------------------------------|
| Figure AI robots       | figureai, humanoidrobots, ai, automation, robotjobs, techai   |
| SpaceX IPO             | spacex, elon, ipo, stocks, finance, wallstreet, investing     |
| Pope's AI encyclical   | pope, vatican, popeleo, aiethics, religion, technews          |
| Ernst & Young scandal  | ey, ernstandyoung, audit, scandal, accounting, businessnews   |

Format: bare words, no `#`. Avoid spaces (use `aiethics` not `ai ethics`).
The orchestrator adds the `#` in the final description.


## CRITICAL: Specific imagery for every proper noun

**The renderer pulls stock from Pexels/Pixabay by default. Stock libraries DO NOT
have photos of specific companies, products, people, or events.** If a script
mentions "Figure AI's humanoid robots" and the shot only has `query`, the video
will show generic robot footage — never an actual Figure robot. That's the
single biggest quality failure the channel has hit.

For EVERY proper noun in the script (company, product, person, place, named
event), do this in order:

1. **WebFetch the Wikipedia article**:
   `https://en.wikipedia.org/wiki/<EntityName>`
2. From the response, grab a real photograph URL on `upload.wikimedia.org`.
   Prefer photos of the entity itself (the product, the founder, the building),
   NOT wordmark logos with just the company name in text.
3. Verify size — Wikimedia only serves thumb sizes it has generated. `500px` is
   almost always safe; `1024px` only exists for very large originals.
4. Attach to the shot whose phrase mentions that entity:
   ```json
   {"phrase": "Figure AI's humanoid",
    "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/.../500px-...",
    "query": "humanoid robot warehouse"}
   ```
5. Always include a `query` fallback alongside `image`. The renderer caps each
   image at 1.8s and fills the rest of the shot with stock from `query`.

### What "specific" means in practice

| Topic                       | Bad query only          | Good image + query                                  |
|-----------------------------|-------------------------|----------------------------------------------------|
| Figure AI robots            | "humanoid robot"        | Wikipedia photo of Figure 02 + warehouse stock     |
| Pope's AI encyclical        | "pope vatican"          | Wikipedia photo of Pope Leo XIV + cathedral stock  |
| SpaceX IPO                  | "rocket launch"         | Wikipedia Starship photo + stock-ticker stock      |
| OpenRouter $113M            | "ai startup"            | OpenRouter founder photo + datacenter stock        |
| Ernst & Young audit fraud   | "corporate office"      | EY LA building photo + audit-document stock        |

If the entity has no Wikipedia article (rare), try:
- The news article's `og:image` (WebFetch the article, grep for `og:image`)
- Wikimedia Commons direct search: `https://commons.wikimedia.org/wiki/Special:Search?search=<entity>`

### What NOT to do

- ✗ Don't use wordmark-only logos as images (e.g., the Anthropic text logo). They
  composite as floating text on a dark backdrop and look like a PowerPoint slide.
- ✗ Don't write `image` URLs you haven't verified return HTTP 200 with
  `Content-Type: image/*`. Wikimedia 404s break the render gracefully (falls back
  to query) but waste a shot's specificity.
- ✗ Don't use `image` without a `query` fallback. If the URL ever 404s, the
  whole shot becomes blank.

## Other script rules

- **60-80 words.** Open with a punchy hook (declarative, no warmup), close with a
  kicker. Whisper transcribes the audio, so write naturally and use digits for
  numbers ("12 million", "25%", "1980") — every trigger phrase must match what
  Whisper outputs.
- **5-7 shots, 4-7 punches.** Every `shot.phrase` and `punch.phrase` must be a
  verbatim substring of the script (case-insensitive).
- **Punch SFX is automatic** based on text content + color:
  - Any `$` in punch text → ka-ching cash register
  - "RIP / DEAD / CRASH / KILLED / GAME OVER / BANNED" → shock thump
  - `#ff3030` red → shock, `#50ff80` green → bright bell, `#ffaa30` orange →
    warning bell, `#ffffff` white → neutral
- **Avoid these words**: "Wayfair" (Whisper hears "wafer"), "Once" as a
  sentence opener (heard as "wants"). Use "First", "Back in", "Once you" etc.

## Don't do

- Don't render videos. The daily.yml workflow does that after your push.
- Don't upload to YouTube. Same — workflow handles it.
- Don't run the orchestrator (`run_trending_daily.py`). You only write packages.
