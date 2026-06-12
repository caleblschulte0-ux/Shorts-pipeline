# History & Mystery — Channel Operating System

An evergreen **History & Mystery** channel bolted onto the Shorts-pipeline, in
the niche of *"ancient events that sound fake but aren't."* It mirrors the
isolated-subsystem pattern of `data_learning/`: a self-contained folder of docs +
starter assets that **ride the existing v8 package schema and renderer** — no base
pipeline code is changed.

> **North star:** build the internet's largest library of *"That can't be real…
> wait, that's actually true"* stories. History is the setting; **wonder and
> disbelief are the product.**

## Start here

| File | What it's for |
|------|---------------|
| [`OPERATING_MANUAL.md`](OPERATING_MANUAL.md) | Strategy & standards: the 3 channel concepts, the retention video formula, success metrics, anti-slop toolkit, **credibility charter**, 30-day launch plan, and the 7-axis scoring system. |
| [`CONTENT_ENGINE.md`](CONTENT_ENGINE.md) | The repeatable machine: topic research, the **Series Engine**, script template, fact-check, visual/voice/caption guides, title & thumbnail formulas, analytics loop. |
| [`DAILY_ROUTINE.md`](DAILY_ROUTINE.md) | The day-to-day steps (mirrors `CLAUDE_ROUTINE_INSTRUCTIONS.md`): pick → fact-check → write → slop-gate → package → validate → PR. |
| [`slop_check.py`](slop_check.py) | Optional, additive linter enforcing the "No AI Slop" gate. `python3 channels/history-mystery/slop_check.py <package.json>` |

### Templates (`templates/`)

| File | What it's for |
|------|---------------|
| `topic_bank.json` | Pre-scored evergreen topic inventory, grouped into 8 series. **Generated** — edit `build_topic_bank.py` and re-run, don't hand-edit. |
| `build_topic_bank.py` | Source of truth for the bank; computes weighted scores + episode numbers. Append real topics here to grow it. |
| `package_template.json` | A fully worked, **renderer-legal** example package (the Dancing Plague of 1518) — copy this to author a video. |
| `script_template.md` | Fill-in script skeleton with the retention beats. |
| `scoring_sheet.md` | The 7-axis rubric, weights, greenlight threshold, and hard floors. |
| `fact_check_template.md` | Per-video fact-vs-theory ledger + source log (required before ship). |
| `winning_patterns.json` | Analytics memory — log every video; the review ritual makes the system smarter. |
| `topic_graveyard.json` | Rejected ideas + reasons, so weak topics aren't re-evaluated. |

## How it plugs into the existing pipeline

- Packages authored here use the **same v8 schema** the news channel ships
  (`script` + `shots[]` + `punches[]` + `music_vibe` + optional `channel`), so
  `make_explainer_stacked.py` renders them and `scripts/validate_packages.py`
  gates them unchanged.
- Differences are **editorial, not technical**: evergreen topics (no freshness
  rule), `music_vibe: cinematic|dark`, atmospheric/omitted `bottom_theme` (no
  gameplay), restrained mascot, and a hard **credibility gate** (fact vs theory).

## Known scope notes (read `OPERATING_MANUAL.md` §9)

- **Topic bank size:** seeded with **121 real, hand-scored topics**. The user
  target is 300–500; every entry is a *real* event (we never pad the bank with
  fabrications — credibility is the brand). Grow it toward 500 with the
  `CONTENT_ENGINE.md` §1 sourcing funnel by appending to `build_topic_bank.py`.
- **Bottom-half visual:** the ideal atmospheric `bottom_theme` (fog/embers/
  parchment) doesn't exist yet — approximate with `music_vibe` + an omitted theme
  today. Adding one atmospheric theme to `themed_bottom.py` is the single
  recommended follow-up renderer task.
- **Channel routing slug:** a new `channel` slug for this channel is a
  prerequisite you own; until it exists, packages route to the default channel.

## Quick verification

```bash
# JSON parses + example package passes the slop gate
python3 -c "import json,glob;[json.load(open(f)) for f in glob.glob('channels/history-mystery/templates/*.json')]"
python3 channels/history-mystery/slop_check.py channels/history-mystery/templates/package_template.json
# regenerate the bank after editing build_topic_bank.py
python3 channels/history-mystery/templates/build_topic_bank.py
```
