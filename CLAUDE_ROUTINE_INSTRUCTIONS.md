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
| _(omit)_     | baller bro 2.0       | Default — ALL Part-1 packages. News + quirky shorts.                     |

**Every Part-1 package goes to baller bro 2.0 — always omit `channel`.**
Do NOT set `"channel": "explainer"` on a trending package. The
Short_explainer channel is a consistent *data-graph* channel fed
exclusively by the **Part 2** stories below (chart breakdowns, not the
stacked/stock-image format). A teaching-style news beat still ships to
baller bro 2.0; if a topic is better told with charts, write it as a
Part 2 data-graph story instead.

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

---

# Part 2 — Data-graph explainer stories (Short_explainer channel)

After the trending batch above, ALSO author **at least 4 brand-new data-graph
explainer stories** for the **Short_explainer** channel (more is fine — 4 is
the floor, never fewer). Vary the topics across the slate so it's not four
flavors of the same subject.

These are a DIFFERENT format from the packages in Part 1: chart-driven
"X in 4 Charts" breakdowns rendered by `data_learning/studio_render.py`
(four connected charts + a mascot + the round-robin "satisfying" bottom
strip) — NOT the stacked/stock-image format, and NOT the
`"channel":"explainer"` package route above. For this channel's identity,
prefer THESE data-graph stories over routing a Part-1 package to explainer.

You only AUTHOR them (data + config). They post themselves: when this PR
auto-merges, the **Explainer Stories** workflow renders the new stories and
schedules them to the channel hourly, automatically. Don't trigger anything,
don't render, don't upload. The posted-log dedupes, so only NEW stories post.

## Learn from what's working first
Before picking topics, read the explainer channel's own performance:
```bash
cat state/analytics_explainer/latest.json 2>/dev/null
```
Use `summary.top_5_by_vph` / `bottom_5_by_vph` (views-per-hour) to bias the
slate: lean into the subjects and hook styles that scored high, avoid what
flopped. Skip if the file is missing (early days, no data yet).

## Topic rules
- Anything genuinely interesting that's best understood through DATA / graphs:
  economy, tech & the internet, business, demographics, science, health,
  housing, energy, transport, media, money, culture. Evergreen-ish — not tied
  to a single breaking headline.
- **No sports stats / scores / standings.** Data about the *business* of sports
  is fine (team valuations, ticket prices, stadium costs, TV deals) — the chart
  is about money/trends, not box scores.
- Each story = ONE clear narrative arc across **4 connected charts** with a
  payoff (e.g. "the cheery numbers up top, the catch down here").
- Don't reuse a `slug` already in `niche.config.json` (grep first).

## Write it for dummies (this is the whole brand)
The channel is **"the stuff nobody explained to you, broken down so anyone
gets it."** We are NOT a middle-school slideshow that reads the numbers off
the screen. The viewer can already SEE the number — narrating it adds nothing
and is why people scroll away.

**The job is not to FRAME numbers for dummies — it's to DECODE them.** Assume
the viewer doesn't know what the number means and doesn't care until you make
it hit. For every figure: say it, then actually spell out *what it does to a
real person* — in dollars in their pocket, time, "double", a thing they buy,
or a consequence they'll feel. If a smart-but-busy 15-year-old wouldn't go
"ohhh, that's messed up" after your line, you haven't decoded it yet.

The pattern per beat: **number → so what → why that's wild.** Don't stop at
restating; land the gut-punch of what it means.

- ❌ Listing: *"San Jose has the highest cost in years of pay, at 11.3 years."*
  (reads the bar)
- 🟡 Framing only: *"In San Jose it takes 11.3 years of pay to buy a home."*
  (better, but they still don't FEEL it)
- ✅ Decoding: *"In San Jose, a house costs 11.3 years of your ENTIRE salary.
  Not what you save — every single dollar you earn, for over a decade, going
  to nothing but the house. That's why it feels impossible. It basically is."*

Another: a `6.6%` mortgage rate isn't "rates went up" — it's *"on a 30-year
loan that's almost double the interest you hand the bank, for the exact same
house."* An `84` cost-of-living index isn't "Hawaii is expensive" — it's
*"the same 100 dollar grocery run costs 184 there; your money just evaporates."*

Rules:
- Each beat names **1–2 real on-chart numbers** (exact digits shown, e.g.
  `6.6 percent`, `449`, `35.7 percent`) — those auto-circle on the chart —
  then DECODES them as above. Spend the words on the meaning, ~30–45/beat.
- Conversational, blunt, second-person ("you", "your paycheck"). Contractions.
  No jargon, no "as you can see", no "this chart shows".
- The four beats build ONE argument to a payoff in the closing.
- Total ~55–75s is fine if the words are doing real explaining — depth beats
  brevity here. Cut filler, never the decode.

### Hooks — the single most important line
A weak hook = nobody watches. The hook must open a curiosity gap or land a
gut-punch in the first 3 seconds, and it must NOT just announce the topic.

- ❌ Weak: *"Four charts show why you can't buy a house. Watch how they connect."*
- ✅ Strong: *"Your parents bought a house on one salary. You can't get one on
  two — and no, it's not the avocado toast. Here's the actual math."*

Good hook shapes: a then-vs-now gut punch ("X cost $270k. Today? $449k."), a
"you've been lied to" reframe, a personal-stakes question ("Why does your
paycheck buy less every year?"), or a number so wild it demands the why.

## How to author one (mirror the existing six)
Templates: `data_learning/data/*.json` and the `"stories"` array in
`data_learning/niche.config.json` (copy the shape of e.g. `debt-trap`).

1. **Data files** — one JSON per chart at `data_learning/data/<key>.json`:
   ```json
   {
     "key": "<key>", "title": "Human title (unit)", "unit": "percent",
     "geography": "United States", "time_coverage": "2019-2026 (annual)",
     "source": {"name": "series name", "publisher": "U.S. Bureau of Labor Statistics",
                "url": "https://www.bls.gov", "officiality": "official",
                "access_date": "<today>"},
     "notes": "Illustrative ...",
     "points": [{"label": "2019", "value": 3.7, "period": "2019"}]
   }
   ```
   - Numbers realistic and attributed to a real publisher (BLS / FRED / Census /
     BEA / OECD / World Bank / company filings…). Mark `notes` "Illustrative".
   - `unit`: `percent`, `dollars`, `thousand dollars`, `billion dollars`,
     `million`, `index`, `years`, `hours`…
   - **trend** → points carry `"period"` (years); use a `percent`, `dollars`,
     or `index` unit (value labels are unit-aware).
   - **rank** → category points + optional `"baseline": {"label","value"}`.
   - **comparison** → percent points incl. the baseline value, plus a
     `"baseline"` block (renders high-vs-low + a baseline line).

2. **Story block** — append to `"stories"` in `niche.config.json`:
   ```json
   {
     "slug": "kebab-case-unique",
     "title": "Hooky Title (4 Charts)",
     "hook": "One-line scroll-stopper. Watch how they connect.",
     "closing": "SHORT quirky one-liner (<=12 words) — the mascot says it in a speech bubble at the end. Make it land.",
     "hashtags": ["topic", "data", "..."],
     "segments": [
       {"source":"offline","key":"<key1>","params":{"file":"<key1>.json"},
        "insight_type":"trend","topic":"clean noun phrase","role":"1 · LABEL",
        "say":"Reference the exact number, then explain what it MEANS. ~20-35 words."}
     ]
   }
   ```
   - 4 segments. `insight_type`: `trend` | `rank` | `comparison`. For rank add
     `"ascending": false` + `"use_baseline": true` (if it has a baseline); for
     comparison add `"use_baseline": true`.
   - `topic` = clean noun used as the chart heading ("mortgage rates").
   - **`say`** = the spoken line for that beat — the heart of the video. It MUST
     contain the exact on-chart digits you want circled (e.g. `449`, `6.6
     percent`) and then explain them (see "Write it for dummies" above). This
     replaces the old auto-generated line; don't use `connector`/`explain`.
   - Keep each beat ~20–35 words so the finished video lands ~45–60s.
   - Look at the `housing-affordability-wall` story for a full worked example.

3. **Sanity check** (optional — needs matplotlib/Pillow locally; CI validates
   on merge regardless). Confirms the story builds:
   ```bash
   python3 - <<'PY'
   import json, tempfile; from pathlib import Path
   from data_learning import story
   cfg = json.loads(Path('data_learning/niche.config.json').read_text())
   sc = next(s for s in cfg['stories'] if s['slug'] == '<your-slug>')
   with tempfile.TemporaryDirectory() as td:
       st = story.build(sc, cfg, Path(td), Path('.'))
       print('OK', len(st.segments), 'charts,', len(st.sentences()), 'beats')
   PY
   ```

4. Commit the new `data_learning/data/*.json` + the `niche.config.json` change
   in the **same daily PR** as the trending packages. Done — they post on merge.
