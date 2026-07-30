# The exchange pipeline — ChatGPT inside one day's run

The daily run is split so ChatGPT can contribute **before** anything renders.
Rendering first would be wasted work: ChatGPT changes both the scripts and the
visuals, and we are not re-rendering.

```
01:30  Phase A   author'd packages -> resolve media -> JUDGE every shot
                 writes ONE bundle: scripts + media health + gap requests
                 commits, then STOPS.  Nothing renders.
         │
02:00  ChatGPT   reads exchange/bundles/<date>/bundle.json
                 · generates the requested images/animations -> Google Drive
                 · punches up the scripts
                 · commits response.json, then DONE   ← written LAST
         │
   ↓ the DONE push fires Phase B (no clock guessing)
         │
       Phase B   verified Drive pull -> pin media -> SELF-FILL the rest
                 apply punch-ups that survive the claim guard
                 packages now final -> render
```

## Why one bundle, not two asks

The punch-up is better when the writer can see what will be on screen, and
media/line pairings cannot drift if the script and the visuals are decided in
the same breath. One round trip, one wait.

## The pieces

| Piece | Job |
|---|---|
| `funnel/media_judge.py` | Script-aware scoring: "the line says X, this is the image — does it land?" Returns `strong`/`weak`/`missing` + the AI prompt for gaps. |
| `shared/exchange_bundle.py` | Builds the day's bundle; reads the response; owns the READY/DONE markers. |
| `shared/punchup_guard.py` | Mechanically enforces that a rewrite changed *wording*, never *claims* or beat structure. |
| `scripts/exchange_phase_a.py` | Phase A entrypoint. Resolves media, judges, writes the bundle. **Never renders.** |
| `scripts/exchange_phase_b.py` | Phase B entrypoint. Pulls media, self-fills, applies guarded punch-ups. |
| `scripts/fetch_exchange_media.py` | The paranoid downloader (hash + full pixel decode + placeholder detection). |

## The judge — when do we call ChatGPT?

Not only when we find nothing. A shot is a gap when the media is:

- **missing** — nothing found, or
- **weak** — little term overlap with the line, a *generic stand-in* for a
  named subject (line says "Starship", image is a stock rocket), below the
  720px target edge, unverified provenance, or recently reused.

`weak` is the important one: it's the difference between "only when desperate"
and "whenever we could do better".

## Policy A — a no-show never costs us the day

Operator decision, 2026-07-30. When Phase B finds a request unfulfilled it runs
a **self-fill** pass: the funnel again with the gloves off (wider providers,
lower floor, accept the weak-but-real candidates the judge rejected). Worst
case a shot ships weaker than we wanted; we never ship nothing.

The **backstop cron** (`exchange_phase_b.yml`, 03:15 UTC) exists for the same
reason: if ChatGPT never writes DONE, the push trigger never fires, and without
the backstop the day would never render at all. It no-ops when Phase B already
ran for that date.

**Pollinations is retired as the AI-image path.** Every AI-generated image
comes from ChatGPT; the self-fill pass finds *real* media instead.

## The punch-up guard — non-negotiable

ChatGPT may rewrite `script`, `title`, `hook`, `hashtags` and shot `phrase`
text. It may not:

- change, drop, or invent any number, percent, money amount, date or year;
- add or remove a named entity;
- change the shot count or any shot's `query` (media is already chosen
  against those);
- move outside ~0.5×–1.8× the original word count.

A rewrite that breaks any rule is **rejected and the original ships**. This
exists because PR #168 found 519 of 546 explainer datasets were LLM-invented
"illustrative" numbers — a punch-up pass is a fresh chance to manufacture more,
so it is checked, not trusted. The guard errs toward rejection: a false reject
costs a missed improvement, a false accept ships a fabricated fact.

Re-casing an existing word for emphasis (`caught` → `CAUGHT`) is explicitly
allowed — entity comparison runs against the other text's full word set.

## Knobs

| Setting | Default | Effect |
|---|---|---|
| `CHATGPT_ANIM_BUDGET` (repo var) | `0` | How many of the day's gaps are requested as **animation** instead of a still. `0` = stills only. |
| `CHATGPT_MAX_REQUESTS` (repo var) | `24` | Hard cap on daily requests. Gaps are spent worst-first. |
| `--no-self-fill` | off | Skip the gloves-off pass (leaves gaps unfilled). |
| `--no-punchup` | off | Ignore script rewrites entirely. |
| `--require-done` | off | Phase B defers instead of proceeding without ChatGPT. |

## Wiring (LIVE as of 2026-07-30)

| Step | Fires on |
|---|---|
| **Phase A** | `workflow_run` on **Auto-merge claude PRs** (the Routine's packages landing) + `30 1 * * *` backstop + dispatch |
| **ChatGPT** | its own 02:00 scheduled task, reading `exchange/bundles/<date>/bundle.json` |
| **Phase B** | `push` on `exchange/bundles/*/DONE` + `15 3 * * *` backstop + dispatch |
| **Render** (`daily.yml`) | `workflow_run` on **Exchange Phase B** + manual `.github/triggers/daily` |

### The trigger that had to MOVE — read before changing any of this

`daily.yml` used to fire on `workflow_run: Auto-merge claude PRs` **and** on a
`state/trending_packages/**` push. Both meant "render the instant the Routine's
packages land". With the exchange in place that **races and always wins**: the
render would finish long before ChatGPT's 02:00 task, using pre-ChatGPT media
and the un-punched scripts, every single day — while everything still looked
green. Nothing would have alerted us.

So Phase A **took over** the auto-merge slot, the package-push path was
**removed**, and `daily.yml` now renders only when Phase B completes. If you
ever see `daily.yml` triggering on package landing again, the exchange is dead
and you are shipping the old media.

Consequence worth knowing: `third.yml` and the explainer chain off "Daily
Shorts", so they now run roughly 1.5–2h later in the morning as well.

### Times, and why an earlier chain is free

| Step | UTC |
|---|---|
| Claude Routine authors | ~00:45 |
| Phase A (auto on auto-merge; cron backstop) | 01:30 |
| ChatGPT task | 02:00 |
| Phase B (auto on DONE; cron backstop) | 03:15 |
| Render | ~03:30 |
| **Uploads** | **13, 15, 17, 19, 21, 23 — FIXED, unaffected** |

Moving the chain earlier costs nothing operationally: publish slots are
hardcoded UTC hours (`DEFAULT_PUBLISH_HOURS_UTC` in
`scripts/run_trending_daily.py`) and `schedule_times()` simply takes the next
free ones. An earlier render does not move a single upload — it only widens the
margin before the 13:00 first slot. The one real trade is **topic freshness**:
authoring earlier means less overnight news has accumulated for the Routine's
"happened today / just announced" rule.

**Keep the ChatGPT task and these crons on the same clock.** The crons are UTC;
ChatGPT Tasks are set in local time. If ChatGPT runs *after* the Phase B
backstop, the backstop renders pre-ChatGPT media every day and everything still
looks green.

### What the operator's Claude Routine must do

**Author packages, push, stop.** It must NOT dispatch `daily.yml` — that is now
the last step of the chain, not the next one. Full note at the top of
`CLAUDE_ROUTINE_INSTRUCTIONS.md`.

## Testing

```bash
python -m unittest tests.test_exchange          # judge + bundle + guard, offline
python scripts/exchange_phase_a.py --date <D> --channel trending --dry-run
python scripts/exchange_phase_b.py --date <D> --channel trending --dry-run
```

The full handshake was simulated end-to-end before shipping: Phase A wrote a
bundle for 2 gaps, a faked ChatGPT response fulfilled one and offered a
punch-up, Phase B pinned the media with `media_origin: chatgpt`, and the
punch-up was correctly rejected for an invented entity.
