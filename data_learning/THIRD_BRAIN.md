# THIRD CHANNEL ("third") — brain playbook: TRUE SURVIVAL STORIES

Working title: **"Survived"** (branding is the operator's call — alternatives:
"Against All Odds", "The Last Second"). The channel slug is `third`; every
package for this channel sets `"channel": "third"` and the uploader routes it
to the `YOUTUBE_TOKEN_JSON_THIRD` secret. See §12 for the full wiring and the
isolation guarantees.

This file is the channel. The scout, sandbox, validators, render tools,
uploader and token are shared infrastructure; what makes this channel itself
is the doctrine below. The brain reads this file first and treats it as law.
Operator feedback gets written back INTO this file so it becomes permanent
doctrine, not a one-off fix.

---

## 0. Why this niche (evidence, 2026-07-07)

Chosen from our own two channels' analytics, not taste:

- **Survival stories are the default channel's best performers.** Top 3 by
  views-per-hour on baller_bro_2_0: "His Parachute Failed at 12,000 Feet. He
  Lived." (#1), "Two Tornadoes Touched Down at the Exact Same Time" (#2),
  "A Diver Swam Next to the Biggest Fish on Earth" (#3). Danger + a person +
  a resolution outperforms everything else we ship there.
- **Named incidents drive our only real search traffic.** The only search
  terms with meaningful volume across both channels are named entities —
  including `twistex dashcam` (the El Reno storm-chaser tragedy). People
  search *named* disasters and survivors for years. Survival stories are a
  named-entity catalog with permanent search demand.
- **Animals/vivid-danger retain 74–102%** on the explainer channel; dry
  process content dies at 31–41%. Survival stories are 100% vivid danger.
- **Evergreen beats perishable at our size.** The trending channel averages
  6 views/video because one-cycle news dies with the cycle. A survival
  catalog (decades of documented cases) keeps earning search + suggested
  traffic long after upload.
- **Zero cannibalization.** Channel 1 = quirky trending news / animal-danger
  facts. Channel 2 (Schulte Media / Data Minute) = data & scale explainers.
  Nobody owns "one person, one impossible situation, how they lived."

## 1. Identity (one swipe)

**One real person. One impossible situation. How they made it out — in 45
seconds.**

Every video is a true, documented survival story with a named human at the
center. The viewer's contract: *someone should have died here, and didn't —
stay to find out how.* The promise in the title/hook is always survival, so
the watch is a search for the mechanism, not the outcome. That's the
retention engine: outcome known, method withheld.

## 2. The iron gate (a story may not enter the queue unless…)

> It has a **named survivor** (person, crew, or named incident), **documented
> mortal stakes** (a number: altitude, depth, days, degrees, distance), a
> **survival mechanism you can show** in one concrete image, AND at least
> **three concrete visual beats** (a place on a map, a physical object, a
> scale comparison, a before/after).

Reject even if compelling:
- Unverifiable tales (reddit-only, "friend of a friend", uncorroborated
  viral posts). Requires wire service (AP/UPI/Reuters/BBC), official report
  (NTSB, Coast Guard, park service), or established documentary record.
- Stories where nobody survives — the channel promise is survival. Incidents
  with mixed outcomes (some lived, some didn't) are allowed only when told
  through the survivor, with the deceased treated respectfully by name or
  not at all.
- Ongoing tragedies (<30 days old with active grief/rescue) — we are not a
  news channel; let the second channel's rules handle fresh events.
- Crime/violence-as-entertainment, self-harm, and anything whose "survival
  mechanism" is luck alone with no picturable method.

## 3. Angle-derivation rule for the shared scout pool

The scout pool (`state/scouted_sources.json`) is channel-agnostic RAW
MATERIAL. From the shared pool, extract **the human-survival kernel — who
came closest to dying and the specific mechanism that kept them alive —
never the event itself.**

- Tornado outbreak trends → not "F4 hits Oklahoma" → **"He rode out an F4 in
  a bathtub. The bathtub is why he's alive."**
- Shark sighting trends → not "shark seen off beach" → **"She punched a
  great white in the gills. That's the only spot that works."**

But the scout pool is a *minority* input here (§11). The spine of the
channel is the **evergreen catalog**: aviation (Juliane Koepcke, Vesna
Vulović), mountains (Joe Simpson, Beck Weathers), open ocean (José
Salvador Alvarenga, the Robertsons), caves/mines (Chilean 33, Tham Luang),
wilderness (Aron Ralston, Hugh Glass), animal encounters, freak physics
(Roy Sullivan's 7 lightning strikes). Maintain a backlog file of gated
candidates; never depend on the day's news to fill the slate.

## 4. Editorial pillars

| Pillar | Qualifies | Rejected |
|---|---|---|
| **Survival vs. physics** — falls, crashes, exposure, depth, lightning | parachute failure, plane-crash sole survivors, avalanche burials, free-diving blackouts | fatal-only crashes, disaster-porn compilations |
| **Survival vs. nature** — animal encounters, open ocean, wilderness, weather | shark/bear/croc attacks survived, adrift-at-sea, desert/jungle treks, tornado close calls | animal facts with no human story (channel 1's lane), pet content |
| **Survival vs. entrapment** — caves, mines, rubble, wrecks, machinery | Chilean miners, Tham Luang, earthquake-rubble rescues, sunken-ship air pockets | active/ongoing rescues, crime confinement cases |

Seed weights from this channel's OWN analytics once it has them; until then
the prior is the cross-channel evidence in §0.

**Named-entity rule (hard):** "Juliane Koepcke fell 10,000 feet into the
Amazon" > "teen survives plane crash". Always pick the version with the
name — names compound in search. Title/description/hashtags carry the name
and the incident name (e.g. "LANSA Flight 508").

## 5. Retention doctrine [SHARED — platform truth]

- First second = **proof, not setup**. No branding/throat-clearing. Open on
  the moment of maximum danger.
- New information OR a new visual state every **1–1.5 seconds** (the 50%
  frame must not equal the 100% frame).
- **Context never before intrigue** — at most one context sentence, after
  the hook earns the stay.
- The final line must **escalate, invert, or resolve** — never restate a
  shown fact.

Channel-specific arc (every script): **danger peak → how bad, in numbers →
the mechanism, step by step → the survival proof → an aftermath kicker that
inverts or escalates** ("She was found 11 days later — she walked out on a
broken collarbone. Would you have followed the water downstream?").

## 6. The three retention failures [SHARED]

1. **Packaging** (good shown-in-feed, weak viewed-vs-swiped) → fix first
   frame / first clause. Nothing else matters until this is fixed.
2. **Body** (stay past 1s, leave mid) → cut filler; add a change where they
   drop.
3. **Payoff** (competent but weak ending) → last line must add something new.

## 7. Production rules (house style)

1. **Cold open = the danger stated in ≤5 words**, ending `?` or `!`
   ("12,000 feet. No parachute!"), over the proof frame.
2. **Proof frame** — a real, on-topic image: the actual person, aircraft,
   mountain, or a labeled map/scale comparison. Never generic stock as the
   opener.
3. **Numbers are the texture** — altitude, temperature, days without water,
   depth. Every number shown on screen is spoken. Punch the biggest one.
4. **Maps and scale comparisons whenever geography or magnitude matters**
   (the shared entity/media funnel already resolves these).
5. **`bottom_theme: "auto"` on every package** — the themed-bottom router
   already covers this niche's subjects (`quake`, `volcano`, `rain`,
   `ocean`, `runner`, `moto`, `train`). Reskin rules in
   `docs/BOTTOM_GAME_RULES.md` apply: the bottom character/object must BE
   the story's subject.
6. **Tone: awe and respect, never mockery.** No gore, no body imagery, no
   suffering close-ups. The camera looks at the mechanism, not the wound.
   Deceased parties in the same incident are either named respectfully or
   left out.
7. **Kicker** — last line ends with `?`, names something from the story,
   answerable in one word (validator-enforced by the shared rules).

## 8. Package output schema

Same JSON schema as the explainer packages
(`CLAUDE_ROUTINE_INSTRUCTIONS.md` §"Script package schema" — title, 110–140
word script, shots with verbatim phrases, punches, hashtags, music_vibe,
mascot poses), with these channel constants:

```json
{
  "channel": "third",
  "bottom_theme": "auto",
  "music_vibe": "cinematic | dark"
}
```

Hashtags always include the survivor's name and the incident name as tags.

## 9. Eye-QA checklist [SHARED loop + channel specifics]

After baking, render each beat's final frame + 25/50/75% samples and
**LOOK**. Shared checks: would a pro proudly post this frame; does the first
second earn the view; does something visibly change every beat; text legible
in the safe area; survives platform UI. Channel-specific:
- The real survivor/incident is recognizable or clearly labeled — no
  anonymous stock human standing in for a named person.
- Every number shown is spoken.
- Nothing in frame is gory or disrespectful to victims.
- The map (when present) actually shows the incident location.

Fix → re-render → re-look until every frame passes. **Non-negotiable.**

## 10. Invariants no brain may break [SHARED]

- Trend is raw material — never publish the raw item form.
- The iron gate (§2) is absolute.
- Every on-screen claim spoken + labeled honestly; illustrative media
  labeled as such.
- **AI-content disclosure stays ON** for every upload.
- **The eye-QA loop is non-negotiable.**
- The brain edits only its target slugs' fields; state, dedupe, caps, and
  channel guards are outside its blast radius.

## 11. Weekly cadence

| Track | Share | Goal |
|---|---:|---|
| Evergreen catalog survival stories (named, historical) | 70% | search compounding + shelf life |
| Survival kernel extracted from current events (≥30 days settled, or clearly resolved happy-ending rescues) | 25% | relevance + suggested traffic |
| Format experiments (2-part cliffhangers, "survival rule" explainers) | 5% | learn without diluting identity |

## 12. Wiring & isolation (how "third" stays out of the shared pipeline)

The shared infrastructure is already channel-generic; this channel plugs in
by slug with **zero edits to the existing channels' workflows**:

- **Token**: `uploaders.YouTubeUploader(channel="third")` reads the
  `YOUTUBE_TOKEN_JSON_THIRD` repo secret (suffix = upper-cased slug). Mint it
  with `setup_youtube.py` signed into the NEW channel's Google account, then
  save the token JSON as that secret. The shared
  `YOUTUBE_CLIENT_SECRETS_JSON` OAuth app is reused — only the token is
  per-channel.
- **Wrong-channel guard**: any workflow step uploading for this channel must
  set `YOUTUBE_EXPECTED_CHANNEL` to the new channel's @handle/title/id so a
  mis-set token can never post to the other channels (enforced in
  `uploaders.py`).
- **Packages**: carry `"channel": "third"`. Keep them in their own dated dir
  `state/third_packages/YYYYMMDD/` (NOT `state/trending_packages/` — that
  dir is rendered by the shared daily workflow, and dropping third-channel
  packages there would make `daily.yml` render them and burn its slots).
- **State**: own posted log (`state/third_posted_log.json`) and analytics dir
  (`state/analytics_third/`, produced by
  `python scripts/fetch_analytics.py --channel third`, which already
  generalizes by slug).
- **Workflow**: clone the reference `explainer.yml`/`daily.yml` per
  `BRAIN_PLAYBOOK_TEMPLATE.md`, point its brain step at THIS file, give it
  its own concurrency group (`third-shorts`) and a cron offset after the
  05:00 UTC scout. Until that workflow exists and the secret is set,
  **nothing in this channel runs — the shared pipeline is untouched.**

Setup checklist (operator):
1. Create the YouTube channel; note its @handle.
2. Run `python setup_youtube.py` signed into that account → save the token
   as repo secret `YOUTUBE_TOKEN_JSON_THIRD`.
3. Add repo secret/var for the guard handle; wire the cloned workflow with
   `YOUTUBE_EXPECTED_CHANNEL` set to it.
4. First slate: 6 evergreen catalog stories from §3's backlog, dry-run,
   eye-QA, then ship.
