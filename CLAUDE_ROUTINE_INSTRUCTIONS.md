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
     shuts down airport, world's biggest pumpkin
   - **Weather / Natural disaster / Freak event** — meteor over Rome, F4
     tornado, dust devil flips truck, sinkhole swallows house
   - **Weird local / Quirky news** — NYC sewer mystery, town renames itself,
     Hell Michigan listed at $666K, blanket fort, 1M bees escape semi

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

**Slate rule: set `"bottom_theme": "auto"` on 3 of the 6 daily packages**
(prefer the ones with the strongest theme match — space launch, storm,
volcano, animal). The other 3 omit the field and keep Minecraft. This is
a deliberate A/B: same channel, half themed bottoms, half gameplay, so
analytics can tell us within ~2 weeks which retains better. Don't set it
on all 6 — we lose the comparison.

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
Quirky-animal/disaster picks still dominate the slate (Rule 2) — just
choose the ones with a clear visual subject.

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

After the trending batch above, ALSO author **exactly 3 brand-new data-graph
explainer stories** for the **Short_explainer** channel. Three a day, posted
spaced ~6 hours apart — a steady, un-spammy cadence (a young channel that
firehoses uploads gets throttled). Of the 3, **at most 1 may be finance/money**
— the other 2 come from the non-money buckets below. Vary the topics so it's
not three flavors of the same subject.

These are a DIFFERENT format from the packages in Part 1: chart-driven
"X in 4 Charts" breakdowns rendered by `data_learning/studio_render.py`
(four connected charts + a mascot + the round-robin "satisfying" bottom
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

## Topic rules
- Anything genuinely interesting that's best understood through DATA / graphs:
  economy, tech & the internet, business, demographics, science, health,
  housing, energy, transport, media, money, culture. Evergreen-ish — not tied
  to a single breaking headline.
- **VARIETY RULE — at least 1 in 3 stories must NOT be money/economics.** The
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
- Each story EXPLAINS one thing in **4 charts that are 4 STEPS of a single
  explanation** (setup → mechanism → twist → consequence), not 4 separate
  stats. See "EXPLAIN one thing" below — this is the whole brand.
- **Vary the chart types** — don't make every segment a bar list. Pick the
  `insight_type` that fits the data:
  - `trend` → line (a value over time; data points need a `period`/year).
  - `rank` → horizontal bars (compare items; the biggest/smallest is the point).
  - `comparison` → two big columns (A vs B, percentages).
  - `share` → **pie/donut** (parts of a whole that's MUTUALLY EXCLUSIVE and
    roughly sums to the total — e.g. types making up a population, where the
    spending goes). Don't use a pie for overlapping or non-exhaustive lists.
  Aim for at least two different chart types per story.
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
Not "4 facts about subscriptions" — but *"why subscriptions quietly drain you,"*
explained in four steps. The hook poses the question; the four charts are the
four steps of the answer; the closing is the lightbulb going on.

**The four beats are ONE explanation, chained — not four separate facts.** Each
beat picks up where the last left off ("so…", "but here's the catch…", "which is
exactly why…"). Test: if you could shuffle the four beats and it still made
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
- ❌ Weak: *"Four charts show why you can't buy a house."*
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
     "title": "Hooky Title (4 Charts)",
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
