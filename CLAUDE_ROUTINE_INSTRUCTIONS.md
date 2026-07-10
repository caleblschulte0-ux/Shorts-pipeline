# Daily Routine Instructions

You're running the daily script-writing routine for the Shorts-pipeline channel
(faceless YouTube Shorts, 45-second doomscroll explainers). Your job: write the
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

2. **Pick 6** from the ranker output. Hard rules:

   **Rule 1 — Freshness.** Every package should be from the last 24-48 hours.
   Each ranker line shows an age marker like `[2h ago]`. Anchor the package
   to "happened today / this morning / just announced" or skip it.

   **Rule 2 — Quirky-heavy slate (4 of 6 minimum).** Real channel analytics:
   shark attack got 21 views, kangaroo named Hunter got 12, meteor over Rome
   got 10 — Nvidia / Apple / Foxconn / Broadcom earnings got 0. Serious tech
   news doesn't earn a slot here unless it has a niche named-entity angle.

   **At least 4 of 6 picks from the Quirky / Animal / Disaster bucket**, and
   those 4 must cover at least TWO of these three sub-buckets:
   - **Animals / Wildlife** — Hunter the kangaroo, shark attack, raccoon
     shuts down airport, world's biggest pumpkin.
     **HARD CAP: at most 1 animal pick per slate** (operator ruling
     2026-07-10 — the slate had drifted animal-heavy; an exceptional
     named-animal story may take a 2nd slot at most once a week).
   - **Weather / Natural disaster / Freak event** — meteor over Rome, F4
     tornado, dust devil flips truck, sinkhole swallows house
   - **Weird local / Quirky news** — NYC sewer mystery, town renames itself,
     Hell Michigan listed at $666K, blanket fort, 1M bees escape semi

   With animals capped, the quirky weight shifts to weather/freak events
   and weird-local stories — those two sub-buckets should carry most of
   the 4 quirky slots on a normal day.

   **Named-entity rule**: "Hunter the kangaroo escapes Kentucky" >
   "kangaroo escapes in US". Specific names compound on YouTube search
   ("quantinuum ipo" + "qnt ipo" + "twistex dashcam" are the only search
   terms currently driving meaningful traffic). Pick the version with the
   specific name whenever both exist.

   Quirky = the SITUATION is weird, not the PERSON. **Hard cap: at most 1
   "Florida Man" / "local-arrest" / personality-based crime pick per slate.**
   If multiple show up, take the single weirdest situation and skip the rest.

   MUST be real — wire-service (AP / UPI / Reuters / BBC) confirmation, or
   skip it. r/nottheonion and r/FloridaMan get satire reposts, so verify
   before writing. NOT politics-with-quirky-frame. NOT heartwarming fluff.
   NOT celebrity gossip.

   **The other 2 slots:**
   - **1 hard-news slot** — one of: World affairs, US policy, Crime/Justice,
     Science/Health, Climate, Culture/Entertainment. Rotate so the same
     category doesn't repeat two days in a row.
   - **1 Tech/Markets slot — OPTIONAL, max 1.** Include ONLY if a story has
     a niche named-entity search hook (Quantinuum IPO, SpaceX Starship 11
     launch). SKIP generic earnings / chip launches / funding rounds —
     they got literal 0 views. If nothing niche today, swap this slot for
     a 5th quirky pick.

   If quirky is thin, top up with another hard-news pick. Never ship < 6.

   Also reject: live sports, obituaries, political horserace, no-visual-stakes,
   evergreen explainers, and **incremental war/conflict updates** ("day 47 of",
   "casualties rise"). Conflict stories only qualify on a genuinely new
   development — escalation, ceasefire, named-leader statement, named-victim.

3. **Cross-reference before writing.** Pull the same story from 2-3 outlets to
   avoid baking one publisher's slant. The ranker's `angle` field lists which
   sources flagged it ("BBC + Reuters + Politico all covering this"); if it's
   single-source, WebFetch one more outlet before writing. Write from the
   facts all sources agree on — get them right, then tell it with VOICE (see
   the Writing section). Accuracy is non-negotiable; a flat wire-copy recap is
   exactly what we're killing.

4. **Write packages** to `state/trending_packages/$(date -u +%Y%m%d)/0N_slug.json`,
   one per pick.

5. **Pre-flight validation.** Cheapest gate to catch a bad slate before
   render. Runs the LLM entity extractor against every package, checks
   that each named entity has a shot whose phrase covers it, AND reports
   **illustration coverage** — the fraction of shots that carry a real
   `image_url` (or a named entity the funnel can resolve) rather than
   falling to bare keyword stock:

   ```bash
   GROQ_API_KEY=$GROQ_API_KEY python3 scripts/validate_packages.py \
     state/trending_packages/$(date -u +%Y%m%d) \
     --min-coverage 70 --min-illustration 60
   ```

   Exits non-zero when any package has uncovered entities OR illustration
   coverage below the bar. Fix by adding a shot whose `phrase` mentions
   the uncovered entity, or by pinning a real `image_url` on the shots
   flagged as keyword-stock-only (see the Imagery rules above), then
   re-run. The daily render runs this same gate and **quarantines any
   package that fails — it ships the rest of the slate without the bad
   one**, so a single un-illustratable package no longer poisons a day,
   but it does mean you lose that slot. Fix it here instead.

6. **Commit, push, AND open a PR.** Plain `git push` puts work on a feature
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
  "script": "110-140 word script. Hook is <=5 words and ends with ? or !. Kicker is a story-specific question answerable in one word.",
  "shots": [
    {"phrase": "verbatim substring of script", "image_url": "https://...",
     "query": "tight 2-4 word stock fallback", "mascot_pose": "idle"}
  ],
  "punches": [
    {"phrase": "verbatim substring", "text": "1-3 ALL CAPS", "color": "#hex"}
  ],
  "hashtags": ["topical", "tags", "specific", "to", "this", "story"],
  "music_vibe": "dark | cinematic | hiphop",
  "bottom_theme": "auto",
  "channel": "explainer"
}
```

**`bottom_theme`** — what plays in the BOTTOM half of the stacked video.

| Value | Bottom half |
|-------|-------------|
| _(omit)_ | Classic Minecraft parkour gameplay |
| `"auto"` | Keyword-routed procedural game themed to the story (PREFERRED) |
| `"space"` | Rocket hopping star-to-star, drawing a constellation (launches, space) |
| `"volcano"` | Distant eruption raining bouncing fireballs (volcano/wildfire) |
| `"quake"` | City + live seismograph ramping to rupture (earthquake/tsunami) |
| `"runner"` | Critter sprinting over fences/rocks/logs (animal escapes) |
| `"stacker"` | Blocks snapping onto a record-chasing tower (world records, builds) |
| `"fight"` | Red vs blue orbs clashing in an octagon (UFC/boxing/combat) |
| `"moto"` | Hill-climb dirt bike: drop-offs, airtime, flips, coins (vehicles/races) |
| `"train"` | Runaway express on a loop-the-loop track, coin rings (rail, summits) |
| `"rain"` | Storm streaks + lightning bolts (generic weather) |
| `"ocean"` | Fish + bubbles + god rays (marine stories) |
| `"coins"` | Gold plinko cascade (markets / money stories) |
| `"plinko"` | Neutral plinko — the universal fallback |

All escalating themes follow the same arc: start calm, the sim clock
compounds until the physics genuinely breaks (tunneling / solver
divergence / temporal aliasing), the engine hangs, and the world
regenerates. That arc is the retention hook — see the DESIGN CHARTER
at the top of `themed_bottom.py` before adding or modifying themes.

**Bottom-game rules (MUST — full spec in `docs/BOTTOM_GAME_RULES.md`).**
Set `"bottom_theme": "auto"` on EVERY package (no Minecraft); semantic
routing picks the theme. But routing to a theme is NOT enough — the bottom
must match the story's SUBJECT visually:
- The on-screen character/object must BE the subject — tortoise escape → a
  tortoise running; stolen-backhoe chase → a backhoe being chased; duck story
  → a duck. **Reskin = swap the sprite/object, not just recolor.**
- Reuse a base game **at most ~1 in 3** videos; a reused game ALWAYS gets a
  different character. Mostly new/distinct, not the same critter twice.
- If no existing game fits, **build a new one** (naval battle for a warship
  strike; fireworks duel for fireworks) — `plinko` is the last resort only.

**`mascot_pose` per shot** — one of `idle | shock | point | laugh | think |
dismiss`. Drives the news-anchor mascot's reaction in the corner overlay.
Default is `idle`; pick a non-idle pose only on the 2-3 emotional beats per
script (max 3 non-idle shots per script). The renderer silently no-ops the
overlay when `assets/mascot/anchor/<pose>.png` is missing, so omitting the
field is always safe.

| Pose | Use it on |
|------|-----------|
| `idle` | Default — most shots |
| `shock` | Twist / surprising fact ("$320 BILLION lost") |
| `point` | First mention of the central entity |
| `laugh` | Absurd / quirky beat ("the driver ran for the river") |
| `think` | Setup / mystery framing ("nobody knows why") |
| `dismiss` | Skeptical kicker framing |

**Hook + kicker rules** (validator rejects packages that miss these):
- First sentence must be ≤5 words AND end with `?` or `!` ("A kangaroo did
  WHAT?", "Why fire 30,000?"). Drives the 3-second hold.
- Last sentence MUST end with `?` AND name something from the story (not
  generic "what do you think?").
- Banned phrases (algorithm-suppressed): "comment yes", "subscribe for part",
  "tag a friend", "let me know in the comments", "like if you agree".

## Writing — voice, story, payoff (READ THIS; it's the whole channel)

The #1 reason a finished video falls flat is NOT the images — it's that the
script reads like a police blotter: a flat, chronological, who-did-what
recap with no point of view and a limp ending. A neutral wire-copy recap is
exactly what we are killing. Same energy as the Part-2 "EXPLAIN one thing"
philosophy below, applied to quirky news.

### Voice — write like a person, not a press release
The narrator is a deadpan, slightly incredulous friend telling you the most
ridiculous thing they read today. Dry wit, real reactions, second person,
contractions. It has a TAKE. It's allowed to be amused, skeptical, or
appalled — as long as every FACT stays true (accuracy is non-negotiable;
attitude is mandatory). Concretely:
- React to the absurd instead of just reporting it ("Cool, weird, whatever —
  until a SECOND call comes in.").
- Short punchy sentences. Vary rhythm. Sentence fragments are fine for
  punch. The em-dash and the hard stop are your friends — they also make the
  TTS breathe instead of droning.
- No corporate hedging ("officials confirmed", "authorities stated"), no
  filler procedure ("teamed up with officers from Naugatuck and Prospect").
  Cut anything a viewer wouldn't repeat to a friend.

### Story — find the ONE angle, then escalate
Don't list facts in the order they happened. Find the single thing that makes
this share-worthy (the coincidence, the absurd detail, the twist) and build
the whole script around it: **setup → escalation → turn → payoff.** Each beat
raises the stakes or twists; if you could shuffle the sentences and it still
made sense, you wrote a list, not a story. Lead with the weird, withhold the
turn, land the button.

### Hook — stop the thumb in 2 seconds
≤5 words, ends `?`/`!` (hard gate). But length isn't enough — it must open a
curiosity gap or land a gut-punch, not just announce the topic.
- ❌ Announces, no tension: "Pigs on the loose!", "A new study is out."
- ✅ Opens a gap: "Two loose pigs — same morning?", "Why is this town on
  fire?", "Nobody ordered 40,000 bees."

### Kicker — land the plane, don't trail off
Last line ends `?` and names something from the story (hard gate). But make
it a SHARP question — ironic, pointed, or genuinely intriguing — that pays
off the angle you set up. Not a noncommittal both-sides shrug.
- ❌ Limp: "Is this one owner, or did two strangers lose their pigs?"
- ✅ Pointed: "So who loses a pig and just… doesn't notice?"

### Quick gut-check before you save
Read the script out loud. If it sounds like a person who's actually amused by
the story, ship it. If it sounds like the 6 o'clock news reading a wire
report, rewrite it with voice. A worked example, same facts both ways:
- ❌ BLOTTER: "On June 10, police in Woodbridge, Connecticut got 2 calls about
  2 separate pigs… Animal control teamed up with officers from Naugatuck and
  Prospect, plus a local vet… Is this 1 owner, or did 2 strangers lose
  their pigs?"
- ✅ VOICE: "Woodbridge, Connecticut woke up to a problem with hooves. Two
  pigs, two streets, same tiny town, same morning. First one's trespassing
  through a yard at 5:45 a.m. Weird — until a SECOND pig turns up a mile away,
  apparently living its best life for two days… So who loses a pig and just…
  doesn't notice?"

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

## Imagery — THE #1 quality problem, read this twice

Published videos have been failing on exactly one thing: **the picture on
screen doesn't match what the narrator is saying.** A serval story showed a
bobcat, a leopard in a zoo, fishermen, and a corrugated-iron wall. That
happens when a shot has no real `image_url` and falls back to a `query`
keyword string, because stock libraries (Pexels/Pixabay) return whatever
loosely matches the words — not the thing you meant. Fix it at authoring
time, every shot, no exceptions.

### Rule A — every shot needs a real image, not just proper-noun shots

The old rule ("attach a photo for every proper noun") left most shots on
keyword stock. New rule: **every shot's primary visual is a real
`image_url`.** A `query` is a *fallback only*, never the intended visual.

For each shot, the on-screen image must clearly read as on-topic to a
viewer who is half-paying-attention. Three tiers, in order of preference:

1. **The actual subject** — the named person, place, building, named
   animal/object, or event in that beat. WebFetch
   `https://en.wikipedia.org/wiki/<EntityName>`, grab a
   `upload.wikimedia.org` URL (a `500px` thumb is almost always safe;
   `1024px` only for very large originals). Prefer a photo of the entity
   itself, NEVER a wordmark logo.
2. **A clearly-representative image** when the exact subject has no photo
   (a random escaped pig, an anonymous lottery winner): use an
   unmistakable stand-in — a photo of *a* pig, *a* scratch-off ticket, *a*
   dumpster. It must be instantly recognizable as the thing being
   described. A serval beat gets a serval, never "a wild cat."
3. **Reuse the nearest real image** for un-photographable narration beats
   ("he climbed in", "the first call came in at 5:45 a.m.", "severe air
   hunger"). Don't invent literal stock for an abstract beat — repeat the
   shot's anchor image (the renderer holds it with a slow pan). A wrong
   literal clip is worse than holding a correct one.

If no Wikipedia article exists, try the news article's `og:image` or a
Commons search
(`https://commons.wikimedia.org/wiki/Special:Search?search=<entity>`).

```json
{"phrase": "Figure AI's humanoid",
 "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/.../500px-...",
 "query": "humanoid robot warehouse"}
```

### Rule B — queries must be TIGHT, never keyword-soup

When you do write a `query` fallback, keep it to 2-4 concrete nouns naming
ONE recognizable thing. Long descriptive strings retrieve nonsense:
- ❌ `"porch foundation under house shelter dark crawlspace animal hiding"`
  → returned a corrugated-iron shanty wall.
- ❌ `"wildlife conservation officers police team catching animal rope net"`
  → returned fishermen.
- ✅ `"serval cat"`, `"animal control van"`, `"scratch off lottery ticket"`.

Hard rule: **never use a generic place/skyline photo for a story that
isn't about that skyline.** A Vancouver skyline on a serval story is
off-topic; pin the serval instead.

### Rule C — visual-ability is now a topic-selection test

Before you lock a pick, ask: *can a viewer SEE this story?* A topic with a
recognizable subject (a named person, a specific place, an identifiable
animal, a named object/event) is illustratable. A topic whose subject is
abstract — a scientific journal, an organization, a virus, a statistic, a
"someone somewhere did X" with no named subject — is NOT, and the funnel
will return logos and the shots will fall to off-topic stock. Between two
otherwise-equal quirky picks, take the one you can actually illustrate.
Quirky/disaster picks still dominate the slate (Rule 2 — animals now
hard-capped at 1) — just choose the ones with a clear visual subject.

### Rule D — VERIFY every image_url exists (do not fabricate filenames)

Guessing a plausible-looking Wikimedia filename is the #2 cause of broken
shots — `Willard_Ohio_downtown.jpg`, `Circle_K_store.jpg`, and
`Woodbridge,_Connecticut_aerial.jpg` were all invented, all 404'd, and all
silently fell through to off-topic stock. Before you write an `image_url`,
confirm the file actually exists. Cheapest check, no rate-limit pain:

```bash
curl -s "https://commons.wikimedia.org/w/api.php?action=query&titles=File:<Exact_Name>&prop=imageinfo&iiprop=mime&format=json"
```

A `"missing"` page means the file does NOT exist — pick a different one.
Only use a filename you pulled from a real Commons/Wikipedia page or
confirmed via the API. The renderer drops unresolvable URLs at render time
(so a bad URL becomes a keyword-stock shot, i.e. the exact problem we're
fixing) — catch it here instead.

Never use wordmark-only logos. Never use `image_url` without a `query`
fallback (URL 404 → blank shot).

### Rule E — the `query` is that beat's B-ROLL, so match the moment

The renderer no longer holds one photo for the whole video. It shows each
visual **once** (never twice), caps every cut at ~4 seconds, and **cuts in
stock FOOTAGE from each shot's `query` to fill the gaps and break monotony.**
So `query` is not just a 404 fallback any more — it's the moving footage for
that exact beat. Write it to match what the narration is *saying right there*,
as 2-4 concrete nouns:

- beat says "...through the suburbs" → `query: "suburban street"`
- beat says "police teamed up" → `query: "police car lights"`
- beat says "at 5:45 a.m." → `query: "sunrise quiet neighborhood"`
- a beat about the actual subject → `query: "domestic pig"` (a real pig clip)

Give **every shot a distinct, on-moment `query`** (don't repeat
`"domestic pig"` on all 12). You do NOT need a hand-picked unique `image_url`
for every beat — 3-6 strong real photos plus good per-beat queries is plenty,
because the renderer fills the rest with distinct stock automatically.

### What the renderer now handles for you (don't fight it)

- **Commons URLs:** `Special:FilePath/<File>` is auto-rewritten to the
  `upload.wikimedia.org/.../960px-...` CDN thumbnail (the FilePath form is
  rate-limited to 429 and was silently dropping images). You may still write
  the thumbnail URL directly; just keep widths to allowed buckets (960 is safe).
- **News media:** the funnel keeps the top *several* real photos per entity
  (not just one) and weaves them in — so naming the right entities in
  `news_query`/phrases is what surfaces real story photos.
- **No-repeat + stock fill:** each visual airs once; gaps become fresh
  on-`query` stock. That's why per-beat queries matter more than ever.

## Other script rules

- **110-140 words.** Hook → escalating story → payoff (NOT a flat fact-list —
  see the Writing section). Use digits ("12 million", "25%", "1980") so Whisper
  transcription matches.
- **10-14 shots, 6-10 punches.** Every `shot.phrase` / `punch.phrase` must be a
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

After the trending batch above, ALSO author **exactly 4 brand-new data-graph
explainer stories** for the **Short_explainer** channel. Four a day, posted
spaced ~6 hours apart — a steady, un-spammy cadence (a young channel that
firehoses uploads gets throttled). Of the 4, **at most 1 may be finance/money**
— the other 3 come from the non-money buckets below. Vary the topics so it's
not four flavors of the same subject.

These are a DIFFERENT format from the packages in Part 1: chart-driven
"X in 3 Charts" breakdowns rendered by `data_learning/studio_render.py`
(three connected charts + a mascot + the round-robin "satisfying" bottom
strip) — NOT the stacked/stock-image format, and NOT the
`"channel":"explainer"` package route above. For this channel's identity,
prefer THESE data-graph stories over routing a Part-1 package to explainer.

You AUTHOR them (data + config) **and then you trigger the posting yourself.**
Do BOTH, every day — don't assume an automatic chain ran. After your story
config is pushed to `main` (via the daily PR / merge), kick the posting:

```bash
# Native tool preferred (Claude): mcp__github__actions_run_trigger
#   workflow_id: explainer.yml   inputs: { "mode": "schedule" }
# CLI equivalent:
gh workflow run explainer.yml -f mode=schedule
```

`mode=schedule` with no slugs renders + schedules **every un-posted story**
(the posted-log dedupes, so already-live stories are skipped and nothing
double-posts). You don't render or upload locally — the workflow does that —
but YOU are responsible for firing it. Treat "wrote the stories" and "fired
the posting" as two separate must-do steps; finishing one without the other
means nothing new ships.

(There is also a daily cron + a Daily-Shorts chain as backups, but do not rely
on them — GitHub event chains silently no-op. The explicit trigger above is the
guarantee.)

## Learn from what's working first
Before picking topics, read the explainer channel's own performance:
```bash
cat state/analytics_explainer/latest.json 2>/dev/null
```
Use `summary.top_5_by_vph` / `bottom_5_by_vph` (views-per-hour) to bias the
slate: lean into the subjects and hook styles that scored high, avoid what
flopped. Skip if the file is missing (early days, no data yet).

**Also read retention when present.** When the analytics token carries the
`yt-analytics.readonly` scope, the snapshot adds `summary.top_5_by_retention`
/ `bottom_5_by_retention` (average view %) and `summary.avg_view_percentage`.
vph conflates topic + thumbnail + hook + retention into one number;
*retention* is the thing the algorithm actually rewards, so when it's
available it's the stronger signal for whether a hook/format change worked.
If the retention block is absent, the token predates the scope — re-auth via
`setup_youtube.py` to enable it.

## Data integrity — numbers must be REAL, not "Illustrative"
Accuracy IS this channel's brand. A fabricated figure attributed to a real
agency (the bundled `data_learning/data/*.json` files marked
`"notes": "Illustrative"` but credited to BLS/Fed/Census) is the fastest way
to earn a "fake stats" reputation. Before leaning on a dataset for a new
story, prefer a **live, source-backed** snapshot:

```bash
python3 scripts/refresh_data.py --check            # which files are still illustrative / mappable
FRED_API_KEY=$FRED_API_KEY python3 scripts/refresh_data.py --key savings_rate   # dry-run: prints real numbers
FRED_API_KEY=$FRED_API_KEY python3 scripts/refresh_data.py --key savings_rate --write   # persist after eyeballing
```

`refresh_data.py` defaults to **dry-run** — eyeball the printed values
against the live series page before `--write`. To make a new key refreshable,
add a verified entry to `data_learning/data_sources.map.json` (series id +
frequency + unit). Files with no live equivalent yet stay illustrative; shrink
that list over time, and never invent a number you can't trace to a source.

## Custom thumbnails (automatic)
`studio_render.render()` now writes a title-aligned 1280×720 thumbnail next to
every mp4 (`<out>.jpg`): the spoken hook as the claim + the biggest on-chart
number as the accent, in the video's theme palette. `post_stories.py` uploads
it so YouTube stops auto-picking a mismatched mid-video chart frame. No action
needed per story — it's emitted on render. (Thumbnail upload needs the channel
to be verified for custom thumbnails; if not, it's skipped without failing.)

## Topic rules
- Anything genuinely interesting that's best understood through DATA / graphs:
  economy, tech & the internet, business, demographics, science, health,
  housing, energy, transport, media, money, culture. Evergreen-ish — not tied
  to a single breaking headline.
- **VARIETY RULE — at least 3 of the 4 stories must NOT be money/economics.** The
  channel drifts hard toward personal finance (prices, wages, debt, housing).
  Resist it. Every batch needs a non-money data story, and ideally the daily
  slate spans different worlds. Tons of great stats stories have nothing to do
  with your wallet — tell those too. Non-money buckets to pull from:
  - **Science/space:** exoplanets found per year, rocket launch cadence,
    telescope discoveries, asteroid near-misses, depth/size comparisons.
  - **Health/body:** sleep trends, life expectancy, screen time, steps, vision
    loss, caffeine, what actually kills people vs what we fear.
  - **Nature/climate:** species decline, ocean temps, wildfire acreage, ice,
    animal speeds/lifespans, migration.
  - **Tech/behavior:** AI adoption curves, app/attention time, dating &
    marriage age, commute times, what languages/names are dying or surging.
  - **Demographics/society:** population shifts, urbanization, loneliness,
    where people move, how we spend our 24 hours.
  - **Quirky-but-true:** a wild record, a counterintuitive ranking, a "you'd
    never guess the #1" — the offbeat angle that does numbers on Part 1 works
    with charts too.
- **No sports stats / scores / standings.** Data about the *business* of sports
  is fine (team valuations, ticket prices, stadium costs, TV deals) — the chart
  is about money/trends, not box scores.
- Each story EXPLAINS one thing in **3 charts that are 3 STEPS of a single
  explanation** (setup → turn → consequence), not separate stats. See "EXPLAIN
  one thing" below — this is the whole brand.
- **RETENTION RULE — keep it SHORT and FAST (this is non-negotiable).** Videos
  that run long get swiped. Target **~25–30s, max 35s**: exactly **3 segments**,
  each `say` is **1–2 tight sentences** (not a paragraph). A 4th "and also…"
  beat is a data tour — cut it. Pick the 3 strongest beats and drop the rest.
  The renderer already slams the hook on frame 1 and runs the voice fast; your
  job is to not overload it with words.
- **Vary the chart types** — don't make every segment a bar list. Pick the
  `insight_type` that fits the data:
  - `trend` → line (a value over time; data points need a `period`/year).
  - `rank` → horizontal bars (compare items; the biggest/smallest is the point).
  - `comparison` → two big columns (A vs B, percentages).
  - `share` → **pie/donut** (parts of a whole that's MUTUALLY EXCLUSIVE and
    roughly sums to the total — e.g. types making up a population, where the
    spending goes). Don't use a pie for overlapping or non-exhaustive lists.
  Aim for at least two different chart types per story.
- **NO REPEAT TOPICS — not just slugs.** The channel has shipped near-dupes
  (a second "ocean vs space", another "loneliness") because the old rule only
  checked slugs. A new story must be a genuinely new SUBJECT, and it must use
  NEW data — recombining leftover data files usually just re-tells a subject
  that's already covered. Before writing each one, run the guard and avoid
  anything it flags:
  ```bash
  python3 scripts/topic_guard.py --list                         # every subject already done
  python3 scripts/topic_guard.py --check "<your title>" tag1 tag2 tag3   # exits 1 if too close
  ```
  Already covered (do NOT re-tell): housing/rent, groceries/food prices, credit
  card debt, wages, jobs, cost-of-living, healthcare costs, student loans,
  retirement, car costs, exoplanets, causes of death, wildlife, rate hikes,
  obesity, sleep, marriage age, subscriptions, oceans, loneliness, attention
  span, rocket launches, birth rate, tipping, AI/data-center power, EVs, flight
  delays, food waste. Pull from a DIFFERENT world (see the non-money buckets).
- Don't reuse a `slug` already in `niche.config.json` (grep first).

## EXPLAIN one thing (this is the whole brand)
The channel **teaches one idea to someone who knows nothing and isn't trying
hard** — a mechanism, a *why*, a how-it-actually-works. The viewer should leave
able to explain it to a friend. We are NOT a stat tour. "Here's number A, here's
number B, here's a one-liner, next graph" is the exact thing we are killing.
**Tell the STORY; fall back on the data only as evidence for the point.**

### TENANT #1 — every number must SPEAK cleanly
This is a number-heavy channel, so the narrator mispronouncing figures is the
single most annoying thing it can do. In every `say` line, write each number as
**digits plus its unit, the way it should be heard**:
- money → `$300` (spoken "three hundred dollars"), `$1,920`, `$50.4k` → write
  `$50.4 thousand`
- percent → `200%` (spoken "two hundred percent")
- plain/units → `5,600`, `11.3 years`, `240 thousand`, `1 in 8`
The renderer guarantees correct speech (dollars/percent, commas, decimals all
handled) AND keeps the digits on-screen so the ring still lands. So: never write
a number a way you wouldn't want read aloud — and always pair it with its unit.

**Pick ONE thing to EXPLAIN, then build the whole video around teaching it.**
Not "facts about subscriptions" — but *"why subscriptions quietly drain you,"*
explained in three steps. The hook poses the question; the three charts are the
three steps of the answer; the closing is the lightbulb going on. Keep each
step to one or two sentences — short holds the viewer, long loses them.

**The three beats are ONE explanation, chained — not three separate facts.** Each
beat picks up where the last left off ("so…", "but here's the catch…", "which is
exactly why…"). Test: if you could shuffle the three beats and it still made
sense, you wrote a LIST, not an explanation. Beat 2 should not stand without
beat 1.

**Data is the EVIDENCE, not the subject.** Lead with the idea in plain words;
drop the number as proof. The viewer came to understand something, not to read a
chart. *"Your brain literally ignores a $12 charge — too small to bother
cancelling"* (the idea) → *"which is why people guess $86 when they really pay
$219"* (the proof). The number still lands and auto-circles — but it's serving
the sentence, not the other way around. If you fell back on raw data, fine, but
only as backup for the point you're making.

**Talk to a curious 12-year-old.** Short words. Analogies ("it's like a gym
membership you forgot you had"). Cause-and-effect ("so what happens is…"). No
jargon, no "as you can see", no "this chart shows". Contractions, second person,
blunt. Still decode any number you use (number → so what → why it's wild) — but
now the decode serves the explanation.

The shift, on the subscription video:
- ❌ TOUR (what we're killing): *"People pay $219 a month. // It's split across
  video, music, gaming. // The count grew from 3 to 12. // 48% pay for unused
  stuff."* — four disconnected facts.
- ✅ EXPLAINER: *"Here's WHY subscriptions drain you without you noticing. →
  It starts because each one is tiny — your brain ignores a $12 charge, so you
  guess you spend $86 when it's really $219. → Then they go automatic: you
  decided once, and now 12 of them renew forever with no decision. → Companies
  design it that way — 48% of people pay for something they never use, because
  forgetting IS the business model. → Stack it up and it's a $219 car payment
  you never agreed to."* — same data, but it TEACHES a mechanism.

Length: ~55–75s is fine if every second is teaching. Cut filler, never the
explanation.

### Hooks — short, the single most important line
A weak hook = nobody watches. A LONG hook = they swipe before the data even
loads. The hook is spoken before the first chart, so every extra word delays
"the juice." **Keep it to ONE punchy line, ≤10 words (~2 seconds).** Open a
curiosity gap or land a gut-punch — do NOT announce the topic, and do NOT dump
the numbers (those belong on the charts, revealed as you talk).

- ❌ Too long (the swipe-killer): *"The average 50-year-old has 130 thousand
  saved. They need 360 thousand. That gap isn't closing — it's growing. Here's why."*
- ❌ Weak: *"Three charts show why you can't buy a house."*
- ✅ Tight: *"You're way behind on retirement. Here's how far."* / *"One income
  bought your parents a house. Not anymore."* / *"It's not the lattes."*

Good hook shapes (all short): a then-vs-now jab, a "you've been lied to"
reframe, a personal-stakes question, or a flat contradiction of the headline.
Save the actual figures for the beats — the hook only has to stop the thumb.

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
     "title": "Hooky Title (3 Charts)",
     "hook": "One-line scroll-stopper. Watch how they connect.",
     "closing": "SHORT quirky one-liner (<=12 words) — the mascot says it in a speech bubble at the end. Make it land.",
     "question": "Engagement CTA spoken + shown at the very end. A PERSONAL, easy-to-answer question that begs a reply, then 'comment/tell me/drop it below'. e.g. 'How many hours do you actually sleep? Drop it below.' Keep it one short sentence, no emojis (it's spoken).",
     "caption": "The YouTube/Shorts DESCRIPTION (not spoken). 2-4 sentences: lead with the most shocking number to hook the scroll, tease the payoff, end with the engagement question + a 👇. Front-load search keywords. e.g. 'You think you spend $86/mo on subscriptions. It's really $219...'. Falls back to hook+closing if omitted.",
     "hashtags": ["10-15 tags, most specific/topical FIRST (algos weight the first 3-5), bare words no #"],
     "segments": [
       {"source":"offline","key":"<key1>","params":{"file":"<key1>.json"},
        "insight_type":"trend","topic":"clean noun phrase","role":"1 · LABEL",
        "say":"Reference the exact number, then explain what it MEANS. ~20-35 words."}
     ]
   }
   ```
   - 3 segments. `insight_type`: `trend` | `rank` | `comparison`. For rank add
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

---

# Part 3 — Evergreen curiosity LONG-FORM story (Visualized / OpenRangeInteractive)

This channel is **4–5 minute 16:9 long-form on the main watch feed — NOT a
Shorts channel.** Read `data_learning/CURIOSITY_BRAIN.md` FIRST and treat it
as law — it is a different brand from Data Minute: **question-first, strictly
evergreen, one memorable reveal**, never news, never a "here's a dataset"
story. Posting is weekly (Saturday cron posts ONE story); your job is to keep
the queue stocked.

1. **Check the queue first — only author when it's short.** Count un-posted
   stories (in `curiosity.config.json` but not in
   `state/curiosity_posted_log.json`). If **≥2 are queued, skip Part 3
   entirely today.** Otherwise author exactly 1 story.
2. **Read the channel's own analytics** (skip if missing):
   ```bash
   cat state/analytics_curiosity/latest.json 2>/dev/null
   ```
3. **Pick from the topic bank** (CURIOSITY_BRAIN.md §14) or add a new idea
   that passes the iron gate (§2: instant question, 2–5 year half-life,
   ≥24/30 scorecard). NEVER derive from today's headlines. **Dedupe against
   BOTH channels** (cross-channel near-dupes split the same audience):
   ```bash
   python3 scripts/topic_guard.py --config data_learning/curiosity.config.json \
     --check "<your title>" tag1 tag2 tag3
   python3 scripts/topic_guard.py --check "<your title>" tag1 tag2 tag3
   ```
4. **Author it long-form** (worked examples: `kola-deepest-hole`,
   `sitting-still-speed`):
   - story block in `data_learning/curiosity.config.json` → `"stories"`;
     datasets in `data_learning/data/curio_<key>.json` (prefix `curio_`);
   - **set `"keep_order": true` on the story** (mandatory — the renderer
     maps beats to treatments by config order) and mark exactly ONE
     segment `"hero": true` — the beat with the most cinematic scale
     contrast gets the Blender 3D shot (add `"hero_invert": true` when
     the values are depths, so the monoliths hang downward);
   - give **every segment a `"broll"` list** (1–2 stock-footage queries,
     2–4 concrete nouns each, matched to what the narration says right
     there — "mount everest aerial", "molten lava glowing"); the renderer
     plays the footage while the beat sets up, then cuts to the data
     payoff;
   - **pick each beat's storytelling primitive** (CURIOSITY_BRAIN.md §7.5):
     set `"scene": "descent" | "zoomout" | "cutaway"` on beats where a
     journey beats a chart (depths → descent, scale ladders → zoomout,
     part-of-a-whole → cutaway); leave chart beats (rank/comparison/trend)
     for the record-book moments. Think camera, not chart: "what does the
     viewer fly past?";
   - **6–8 segments**, each `say` 50–90 words (3–5 sentences), total
     **550–800 spoken words**; the arc is hook → why it matters → build →
     escalate → **REVEAL around beat 5** → zoom-out implication;
   - hook = 2–3 sentences (premise, tension, promised payoff — it narrates
     the title card); closing = one zoom-out line; `role` becomes the
     chapter name, so make it clean ("2 · TWENTY YEARS DOWN");
   - **numbers must be REAL and traceable** — encyclopedic constants from
     NASA/USGS/NOAA/records with the exact figure + source named in `notes`
     and `officiality: "reference"`. Never invent, never mark a real-agency
     figure "illustrative"; vary chart types (≥2 of rank/comparison/trend).
5. **Sanity-build it** (same snippet as Part 2 step 3, but load
   `data_learning/curiosity.config.json`) and check the spoken-word count
   lands in 550–800.
6. Commit in the **same daily PR**. No posting trigger needed — the weekly
   cron (Saturdays 15:00 UTC) posts one queued story. To post out-of-band,
   dispatch `curiosity.yml` with `mode: schedule`.

Mark the topic bank row ✅ authored in `CURIOSITY_BRAIN.md` §14 in the same PR.

---

## Engines capability layer (shared, opt-in)

The repo has a top-of-pipeline capability library at `engines/` — reusable
rendering/media engines any channel or session can call (Ken Burns,
experimental depth-parallax, more coming via tickets E1–E14). Discover it
with `python -m engines list` (offline, fast); full registry + verdicts in
`docs/ENGINE_REGISTRY.md`. If a package or render idea needs a capability,
check the registry BEFORE writing new code or requesting new tools —
it may already exist, be one `install` away, or be explicitly rejected
with a reason. Note: `parallax` is experimental and must not be used in
production renders until Ticket E2's benchmark passes.
