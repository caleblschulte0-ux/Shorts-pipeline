# History & Mystery — Daily Routine

Day-to-day execution. Mirrors the structure of the repo's
`CLAUDE_ROUTINE_INSTRUCTIONS.md`, but for the evergreen History & Mystery
channel. Strategy and standards live in [`OPERATING_MANUAL.md`](OPERATING_MANUAL.md);
templates and style guides in [`CONTENT_ENGINE.md`](CONTENT_ENGINE.md).

Goal each run: ship **1–2 schema-valid Short packages** that clear the
credibility and visual floors, then PR them so the daily Action renders + uploads.

---

## Steps

### 0. Read what's working
```bash
cat channels/history-mystery/templates/winning_patterns.json 2>/dev/null
```
Use the `rollups` (winning hook types / categories / series) to bias today's
picks. Skip if empty (early days). Once analytics exist, also read the channel's
own analytics snapshot the same way the news channel does
(`state/analytics*/latest.json`).

### 1. Pick topics from the bank
```bash
# highest-scoring, floor-passing topics not yet shipped
python3 -c "import json;import sys; \
b=json.load(open('channels/history-mystery/templates/topic_bank.json'))['topics']; \
ok=[t for t in b if t['scores']['total']>=85 and t['scores']['visual']>=7 and t['scores']['credibility']>=6]; \
ok.sort(key=lambda t:-t['scores']['total']); \
[print(t['scores']['total'], t['series_id'], t['slug']) for t in ok[:20]]"
```
**Selection rules:**
- **Score gate:** `total >= 85`, `visual >= 7`, `credibility >= 6` (Manual §8).
- **Series spread:** across a week, cover ≥4 series; don't ship two from the same
  series back-to-back.
- **No freshness rule** (unlike the news channel) — evergreen is the point.
- **No repeats:** skip anything already shipped (cross-check the posted log /
  prior `state/trending_packages/*`).

### 2. Fact-check gate (BLOCKING)
Fill `templates/fact_check_template.md` for each pick. Verify every date, place,
name, number. Label confirmed-fact vs theory. Cut or flag any `low`-confidence
claim. **No completed fact-check → do not script it.** (Manual §6.)

### 3. Write the script
From `templates/script_template.md`:
- 110–140 words; hook ≤5 words ending `?`/`!`; kicker ends `?` and names a story
  entity; digits not number-words.
- Fact-vs-theory language matched to the fact-check doc ("records show" /
  "one theory says").

### 4. "No AI Slop" gate (BLOCKING)
```bash
python3 channels/history-mystery/slop_check.py channels/history-mystery/templates/package_template.json
# (point it at each package you authored)
```
Rejects scripts containing slop phrases (`Imagine…`, `What if I told you…`,
`You won't believe…`, hype filler) OR lacking specificity (no dates, no places,
no proper names, no concrete numbers). Fix and re-run until it passes. The script
linting is also a human checklist in Manual §4 — the tool is the backstop.

### 5. Author the package (v8 schema)
Copy `templates/package_template.json` and adapt. Requirements:
- Attach a real archival `image_url` (Wikimedia/Commons) to every proper noun,
  with a `query` fallback (CONTENT_ENGINE §5).
- `music_vibe`: `cinematic` (or `dark` for a Concept-B lane video). **Never
  `hiphop`.**
- `bottom_theme`: **omit** (or calmest existing fit) — no gameplay/runner/fight
  (Manual §9).
- 10–14 shots, 6–10 punches; every `phrase` a verbatim substring of the script.
- `channel`: your history-mystery routing slug **once it exists** (Manual §9);
  until then omit to use the default.
- Carry `series_id` / `series_name` / `episode_number` for the series engine.

Write to: `state/trending_packages/$(date -u +%Y%m%d)/0N_slug.json`.

### 6. Validate
```bash
GROQ_API_KEY=$GROQ_API_KEY python3 scripts/validate_packages.py \
  state/trending_packages/$(date -u +%Y%m%d) --min-coverage 70
```
Fix any uncovered-entity failures (add a shot whose `phrase` names the entity, or
tighten the script). Exit 0 = good to ship.

### 7. Commit, push, PR
```bash
git add state/trending_packages/$(date -u +%Y%m%d)/ \
        channels/history-mystery/templates/topic_bank.json
git commit -m "history-mystery packages $(date -u +%Y-%m-%d)"
git push -u origin HEAD
# open a PR against main (the auto-merge workflow renders + uploads on merge)
```
Use the native GitHub tool (`mcp__github__create_pull_request`) if available.
**No PR = nothing ships.**

### 8. After it's live
Log each video into `templates/winning_patterns.json` once it has data, and run
the analytics review ritual (CONTENT_ENGINE §9) weekly. Re-score the bank from
what's winning; push losers toward `topic_graveyard.json`.

---

## Don't
- Don't render or upload locally — the daily Action handles both.
- Don't ship a package without a completed fact-check.
- Don't use `hiphop` music or gameplay bottom themes — wrong channel.
- Don't present a theory as fact, or invent any historical detail (Manual §6).
- Don't re-pick a graveyard topic — check `topic_graveyard.json` first.
