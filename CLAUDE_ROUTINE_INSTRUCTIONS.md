# Daily Routine Instructions

You're running the daily script-writing routine for the Shorts-pipeline channel
(faceless YouTube Shorts, 25-second doomscroll explainers). Your job: write the
day's 6 script packages and push them. The daily GitHub Action renders + uploads.

## Steps

0. **Read yesterday's analytics** (if present):
   ```bash
   cat state/analytics/latest.json 2>/dev/null
   ```
   Use `summary.top_5_by_vph` / `bottom_5_by_vph` to bias today's picks: favor
   topic clusters and hook styles that scored high; skip anything resembling
   the bottom five. Skip this step if the file is missing.

1. **Discover**:
   `GROQ_API_KEY=$GROQ_API_KEY python3 scripts/rank_topics.py --top-k 10`

2. **Pick 6** from the ranker output. Two hard rules:

   **Rule 1 — Freshness.** Every package should be from the last 24-48 hours.
   Each ranker line shows an age marker like `[2h ago]`. Anchor the package
   to "happened today / this morning / just announced" or skip it.

   **Rule 2 — Half the slate is quirky.** Channel analytics show "semi truck
   full of bees rolled over" / "town renames itself" / "raccoon shuts down
   airport" stories outperform every serious-news category on views and likes.
   **At least 3 of 6 picks from the Quirky / Offbeat bucket.**

   Quirky = the SITUATION is weird, not the PERSON. Good shape: "1 million
   bees escape from semi on Tennessee highway", "United Airlines flight turned
   back over Bluetooth network name", "town renames itself", "Hell, Michigan
   listed for sale at $666K", "world record pumpkin", "wrong-way driver caught
   on camera", "raccoon shuts down airport".

   **Hard cap: at most 1 "Florida Man" / "local-arrest" / personality-based
   crime pick per slate.** Three Florida-Man-style stories in a row reads as
   fluff. If multiple show up, take the single weirdest situation (e.g.
   "selling stolen radioactive device on Facebook" qualifies; generic assault
   doesn't) and skip the rest. The other quirky picks must be situation-driven.

   MUST be real — wire-service (AP / UPI / Reuters / BBC) confirmation, or
   skip it. r/nottheonion and r/FloridaMan get satire reposts, so verify
   before writing. NOT politics-with-quirky-frame. NOT heartwarming fluff.
   NOT celebrity gossip.

   **Other 3** are serious news, 1 per category (treat Tech + Markets as one
   combined bucket): Tech+Markets, World, US policy, Crime/Justice,
   Science/Health, Climate, Culture/Entertainment, Sports (one-off only).

   If fewer than 3 usable quirky stories exist, top up serious. Vice versa
   if serious categories are thin. Never ship fewer than 6.

   Also reject: live sports, obituaries, political horserace, no-visual-stakes,
   evergreen explainers, and **incremental war/conflict updates** ("day 47 of",
   "casualties rise"). Conflict stories only qualify on a genuinely new
   development — escalation, ceasefire, named-leader statement, named-victim.

3. **Cross-reference before writing.** Pull the same story from 2-3 outlets to
   avoid baking one publisher's slant. The ranker's `angle` field lists which
   sources flagged it ("BBC + Reuters + Politico all covering this"); if it's
   single-source, WebFetch one more outlet before writing. Write from the
   facts all sources agree on. Neutral framing, no editorializing.

4. **Write packages** to `state/trending_packages/$(date -u +%Y%m%d)/0N_slug.json`,
   one per pick.

5. **Commit, push, AND open a PR.** Plain `git push` puts work on a feature
   branch nothing renders from; the PR is what auto-merge.yml watches:

   ```bash
   git add state/trending_packages/$(date -u +%Y%m%d)/
   git commit -m "daily packages $(date -u +%Y-%m-%d)"
   git push -u origin HEAD
   gh pr create --base main \
     --title "daily packages $(date -u +%Y-%m-%d)" \
     --body "Today's batch."
   ```

   If your runtime exposes a native GitHub tool (e.g. Claude's
   `mcp__github__create_pull_request`), prefer that — same effect.
   **If you skip the PR step, nothing ships.**

## Script package schema

Reference: `state/trending_packages/20260531/*.json`.

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
  "music_vibe": "dark | cinematic | hiphop",
  "channel": "explainer"
}
```

## Channel routing

Each package can include an optional `"channel"` field that picks
which YouTube channel the upload targets. Available slugs:

| Slug         | Channel              | Use for                                                                 |
|--------------|----------------------|-------------------------------------------------------------------------|
| _(omit)_     | baller bro 2.0       | Default. News + quirky shorts.                                          |
| `explainer`  | Short_explainer      | Micro-learning / explainer-style breakdowns of a concept or mechanic.   |

If you're unsure which channel a story belongs on, omit the field —
it lands on baller bro 2.0. Set `"channel": "explainer"` only when the
script is a teaching piece ("here's how X works", "here's why Y
happens") rather than a news beat. Quirky stories almost always belong
on baller bro 2.0; tech-explainer breakdowns of a single mechanism
belong on Short_explainer.

## Hashtags

10-15 per package in the `hashtags` field. Orchestrator dedupes against a
baseline set (`#shorts #news #explainer #trending #viral #fyp`) before
uploading. Algos weight the first 3-5 hardest — put the most specific topical
ones at the front. Bare words, no `#`, no spaces (`aiethics` not `ai ethics`).

## Specific imagery for proper nouns

Stock libraries (Pexels/Pixabay) don't have photos of specific companies,
products, people, or events. For every proper noun in the script, attach a
real photo via the `image` field.

1. WebFetch `https://en.wikipedia.org/wiki/<EntityName>`, grab a
   `upload.wikimedia.org` URL. Prefer photos of the entity itself, NOT
   wordmark logos.
2. `500px` Wikimedia thumbs are almost always safe; `1024px` only for very
   large originals.
3. Attach to the shot whose phrase mentions that entity, AND keep `query`
   as a fallback:
   ```json
   {"phrase": "Figure AI's humanoid",
    "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/.../500px-...",
    "query": "humanoid robot warehouse"}
   ```

If no Wikipedia article exists, try the news article's `og:image` or Commons
search (`https://commons.wikimedia.org/wiki/Special:Search?search=<entity>`).

Never use wordmark-only logos (composite as PowerPoint slides). Never use
`image` without a `query` fallback (URL 404 → blank shot).

## Other script rules

- **60-80 words.** Hook → 3-5 facts → kicker. Use digits ("12 million", "25%",
  "1980") so Whisper transcription matches.
- **5-7 shots, 4-7 punches.** Every `shot.phrase` / `punch.phrase` must be a
  verbatim substring of the script (case-insensitive).
- **Punch SFX auto-mapped**: `$` in punch text → ka-ching;
  "RIP/DEAD/CRASH/KILLED/GAME OVER/BANNED" → shock thump; `#ff3030` red →
  shock, `#50ff80` green → bright bell, `#ffaa30` orange → warning, `#ffffff`
  white → neutral.
- **Avoid**: "Wayfair" (heard as "wafer"); "Once" as a sentence opener (heard
  as "wants" — use "First" / "Back in" / "Once you").

## Don't

- Don't render or upload — daily.yml handles both.
- Don't run `run_trending_daily.py`. You only write packages.
