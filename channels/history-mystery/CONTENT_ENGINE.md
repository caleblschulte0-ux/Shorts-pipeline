# History & Mystery — Content Engine

The repeatable machine that turns a topic into a shippable package. Read
[`OPERATING_MANUAL.md`](OPERATING_MANUAL.md) for the *why*; this is the *how*.
Run order each day lives in [`DAILY_ROUTINE.md`](DAILY_ROUTINE.md).

---

## 1. Topic research system (evergreen — NOT the news channel's RSS rule)

The news channel demands 24–48h freshness. **We do the opposite: evergreen.** A
1518 story is as valid today as next year. Our scarcity isn't time — it's
*topic exhaustion*, which is why the bank holds 300–500 pre-scored ideas
(`templates/topic_bank.json`).

**Sourcing funnel:**
1. **Mine the bank first.** Day-to-day, you pick from `topic_bank.json` by score
   — no daily inspiration required. This is the point of the bank.
2. **Replenish from durable seams** (add new finds to the bank, scored):
   - Wikipedia's *"Unusual articles"* and *"List of unusual deaths"*.
   - *List of unsolved problems / unexplained disappearances / lost works*.
   - Museum & archive collections (British Museum, Smithsonian, Bibliothèque).
   - Standing books/podcasts on the weird-history beat (for leads, not copy).
3. **Search-interest sanity check.** Before banking a topic, confirm it has a
   *name* people might search (the Antikythera mechanism, the Dyatlov Pass, the
   Dancing Plague). A named mystery compounds; an anonymous "a weird thing once
   happened" does not. Low search interest isn't a kill, but it caps the score.
4. **Credibility pre-screen.** If two minutes of checking can't find a solid
   source, it goes to the graveyard, not the bank.

**Source confidence tiers** (recorded as `source_confidence` in the bank):
- `high` — multiple academic / primary / museum sources agree.
- `medium` — reputable secondary sources, some detail contested.
- `low` — mostly popular retellings; **needs real verification before scripting,
  or stays unbanked.**

---

## 2. Series Engine (the repeat-viewer machine)

People don't subscribe to one-off videos; they subscribe to a **bucket** they
want more of. Every topic belongs to a series, carrying `series_id`,
`series_name`, `episode_number`. Surface the series in the title and the kicker
("Another one for *Impossible Artifacts*…") so viewers learn the bucket.

**Launch series:**

| series_id | Series name | What goes in it |
|---|---|---|
| `weird-wars` | **Weird Wars** | Absurd-but-real conflicts (Emu War, War of the Bucket, the football-match truce). |
| `disappearances` | **Historical Disappearances** | People/ships/colonies that vanished (Roanoke, Flight 19, the lighthouse keepers). |
| `impossible-artifacts` | **Impossible Artifacts** | Objects that "shouldn't exist" yet (Antikythera mechanism, Baghdad battery, Roman dodecahedra). |
| `ancient-engineering` | **Ancient Engineering** | Tech that outpaces its era (Roman concrete, qanats, Greek fire). |
| `made-up-humans` | **Humans That Sound Made Up** | Real people who sound fictional (Tarrare, Wojtek the bear-soldier, Mary Toft). |
| `forgotten-disasters` | **Forgotten Disasters** | Huge events history skipped (Boston Molasses Flood, Lake Nyos, the Dancing Plague). |
| `medical-history` | **Strange Medical History** | Unsettling real medicine (trepanation, the radium girls, Phineas Gage). |
| `lost-expeditions` | **Lost Expeditions** | Doomed/vanished journeys (Franklin, Dyatlov Pass, the Darién scheme). |

**Series discipline:** spread the daily slate across ≥4 series so the channel
reads as a *library*. When a series wins (analytics memory, §9), give it more
slots and make it the next long-form.

---

## 3. Script template

Skeleton fill-in lives in `templates/script_template.md`; the rules:

- **110–140 words**, lands ~45–50s. Hook → 6–9 escalating facts → twist → kicker.
- **Hook ≤5 words, ends `?`/`!`** (disbelief beat; the real claim follows in the
  setup — see Manual §2).
- **Kicker ends `?` AND names a story entity** (not "what do you think?").
- **Digits, not words** for numbers ("1518", "25,000", "3 days") — Whisper has to
  transcribe them for caption alignment.
- Every `shot.phrase` and `punch.phrase` must be a **verbatim substring** of the
  script (case-insensitive) — the renderer aligns on it.
- **Fact-vs-theory language baked in** (Manual §6): "records show" for confirmed,
  "one theory says" for contested.
- **No banned phrases** (Manual §4 + `slop_check.py`).

---

## 4. Fact-checking checklist

Per video, fill `templates/fact_check_template.md`. The gate:

- [ ] Every **date, place, name, number** in the script traced to a source.
- [ ] At least one `high`/`medium` source; `low`-only claims cut or flagged.
- [ ] Confirmed facts vs. theories **labeled** in the doc and matched by the
      script's language.
- [ ] No invented quotes, no invented numbers.
- [ ] Unsolved parts left explicitly unsolved.
- [ ] Sources logged (title + URL) so we can defend any line in a comment.

No completed fact-check file → the package does not ship.

---

## 5. Visual prompt template (tuned for the hybrid cinematic-top look)

The **top half** carries the credibility. Use the schema's existing
`image_url` + `query` mechanism (same as the news channel's "specific imagery for
proper nouns"):

- For every proper noun / place / artifact, attach a **real** archival image:
  - `WebFetch https://en.wikipedia.org/wiki/<Entity>` → grab a
    `upload.wikimedia.org` thumb (prefer `500px`), or
    `https://commons.wikimedia.org/wiki/Special:FilePath/<File>`.
  - Prefer the **thing itself** (the artifact, the map, the person) over logos.
  - Always keep a `query` fallback so a 404 doesn't leave a blank shot.
- **Lean on maps, documents, engravings, period photos** — they read as
  "researched," which is the brand. A historical map under slow Ken Burns is the
  single most on-brand shot type.
- **Shot phrasing** for the cinematic mood: long, settling holds on few images
  beat rapid cuts. Aim **10–14 shots** but let the key reveal breathe.
- **Bottom half:** per Manual §9, omit `bottom_theme` (or use the calmest fit)
  until an atmospheric theme exists. Do not use gameplay/runner/fight themes.

**Per-shot mood:** the v8 schema supports `mascot_pose`, but this channel is
restrained — default to `idle`/omit; reserve `think`/`shock` for the one or two
genuine reveal beats if the mascot is used at all.

---

## 6. Voiceover style guide

- **Persona:** a measured, slightly ominous narrator who *trusts the facts to
  land*. Think late-night documentary, not hype-y MrBeast.
- **Pace:** mostly steady, then **slow down hard on the reveal**. The pacing
  change is the drama; we don't manufacture it with adjectives.
- **Tone:** curious, never breathless. Let a wild fact sit for a half-beat
  instead of piling three "insane!"s on it.
- **Person:** second person and present tense pull the viewer in ("you're
  standing in Strasbourg, 1518").
- **`music_vibe`:** `cinematic` (default) or `dark` (for Concept-B lane). Never
  `hiphop`.
- **Number delivery:** write numbers as digits with units so they're both spoken
  and captioned correctly ("25,000 birds", "3 days").

---

## 7. Caption style guide

- Captions are auto-generated (Whisper → 3-word chunks) — your job is to make the
  *words* caption-friendly: digits not number-words, avoid homophones that
  mistranscribe (the news manual flags "Wayfair"→"wafer", "Once" sentence-openers
  → use "Back in" / "First").
- **Punches** (`punches[]`) are the on-screen kinetic overlays — 1–3 ALL-CAPS
  words on the disbelief beats. Use them on the *wonder spikes*, not every line.
  - `#ffffff` neutral, `#ffaa30` warning/curious, `#ff3030` shock/death,
    `#50ff80` resolution. SFX auto-map from text ("DEAD"/"GONE" → shock thump).
  - 6–10 punches per script; each `phrase` verbatim in the script.
- **The YouTube description/caption** (the text post): front-load the most
  shocking true fact + a search keyword, tease the payoff, end with the kicker
  question + 👇. This is where search interest is captured.

---

## 8. Title & thumbnail formulas

### Title formula (Shorts + long-form)

Pattern: **[Concrete subject] + [impossible/unsolved twist]**, named so it's
searchable. 6–10 words. The named entity goes early (search weight).

- ✅ "In 1518, a Town Danced Itself to Death"
- ✅ "The Ancient Greek Computer That Shouldn't Exist"
- ✅ "Australia Lost a War to Birds (Really)"
- ❌ "This Will Blow Your Mind" (no entity, no search, slop)
- ❌ "A Crazy Historical Mystery" (vague)

Lead with the wonder, never with "the history of…".

### Thumbnail formula (long-form)

- **One arresting archival image** (artifact / map / face) + **3–5 words** of
  high-contrast text that poses the impossible claim or the unsolved question.
- Text = the *curiosity gap*, not the answer ("DANCED TO DEATH?", not "Ergot
  Poisoning Explained").
- Consistent treatment per series so the channel reads as a brand at a glance
  (same font, same text placement, a small series tag).
- For Shorts, the **first frame is the thumbnail** — open on a wonder-image, never
  a logo or a title card.

---

## 9. Analytics review checklist (the system gets smarter over time)

After uploads have data, log each video into `templates/winning_patterns.json`
(video_id, topic_category, hook_type, title_style, series_id, retention, AVD,
rewatches, likes, comments, shares, subscriber_conversion).

**Periodic review ritual** (weekly, then monthly) — answer these from the data:
1. **Which hook types win?** (disbelief-question vs flat-number vs "no survivors")
2. **Which topic categories / series win?** (retention + AVD)
3. **Which series generate repeat viewers / subscribers?**
4. **Which stories create comments?** (the kicker styles that provoke replies)
5. **Which stories create subscriptions?** (conversion per video)

**Feed it back:** bump the topic-bank scores for winning patterns, drop the
losers toward the graveyard, and let the next slate lean into what's working.
This loop — bank → ship → measure → re-score — is the whole growth engine. The
channel should be measurably smarter every month.

---

## 10. Putting it together (one video, end to end)

1. Pick a topic from `topic_bank.json` (score ≥85, visual ≥7, credibility ≥6),
   spread across series.
2. Fill `fact_check_template.md` — verify every fact, label fact vs theory.
3. Write the script from `script_template.md` (hook/kicker rules, no slop).
4. Run the slop gate (`slop_check.py` or the checklist).
5. Author the v8 package (copy `templates/package_template.json`): attach
   archival `image_url`s, set punches, `music_vibe: cinematic`, calm/omitted
   `bottom_theme`, the channel slug.
6. Validate (`scripts/validate_packages.py`), commit, PR (see `DAILY_ROUTINE.md`).
7. After it's live, log performance into `winning_patterns.json`.
