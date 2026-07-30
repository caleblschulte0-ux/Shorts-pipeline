# retro/ — the daily review loop

Once a day, after the last slot has posted, the pipeline writes an evidence
pack and a reviewer reasons over it: how did today's videos do, how is the
week and the month trending, is the machine healthy, is the code drifting.
The reviewer writes **proposals**. Proposals are not changes.

```
23:15 UTC   scripts/build_retro.py  ->  retro/<date>/brief.json + brief.md
  ~7pm CT   ChatGPT reads the brief ->  retro/<date>/proposals/NN-slug.json
            scripts/review_proposals.py triages them
            Claude reads the triage and decides what (if anything) ships
```

**Nothing in this folder is ever applied automatically.** No workflow reads
a proposal and edits code. The loop's output is a ranked queue for a
reviewer with commit access; that is the entire safety model, and it is not
negotiable.

---

## What the brief gives you

`retro/<date>/brief.json`:

| Key | What |
|---|---|
| `channels.<name>.today` | each video posted today, with `percentile_vs_same_age` |
| `channels.<name>.last_7d` / `last_30d` | rolling windows |
| `channels.<name>.thin_bands` | age bands with too few samples to trust |
| `pipeline_health` | failures, exchange result, reserve bank, showrunner |
| `repo` | HEAD, recent commits, test files |

### Read the numbers honestly or do not write the proposal

- **Age-match everything.** A 2-hour-old short and a 3-week-old short are
  not comparable. Use `percentile_vs_same_age`; ignore raw `views` for
  rankings. Anything under ~2 hours old is marked `too young to judge` —
  that is a real verdict, not a gap to fill with a guess.
- **This channel is small.** Single-digit view counts are mostly noise. If
  an explanation requires a 9-view video to mean something, it is not an
  explanation. Say "no signal yet" — that is a useful finding.
- **Respect `thin_bands`.** Fewer than 5 samples is not a trend.
- **One day is never a trend.** A proposal justified only by today needs to
  say so in `confidence`, and should usually be `watch` rather than a change.

## What to write

One file per proposal: `retro/<date>/proposals/NN-short-slug.json`

```json
{
  "schema": "shorts-retro-proposal/v1",
  "title": "Graph race hooks are dead weight below 10s",
  "category": "content",
  "confidence": "medium",
  "observation": "Six graph_race videos in the 1-4w band sit at p12 median vs 47 for text_card, n=6 vs n=10.",
  "evidence": ["channels.trending.last_30d", "state/format_scoreboard.json"],
  "proposal": "Cut the graph_race hook overlay from 1.5s to 0.8s in make_graph_race.py.",
  "files": ["make_graph_race.py"],
  "expected_effect": "Higher 3-second hold on graph_race; no change to other formats.",
  "how_we_would_know": "graph_race avg_view_pct in format_scoreboard after 10 more posts.",
  "risks": "If the hook is what makes the payoff land, shortening it could hurt completion.",
  "rollback": "Revert the one constant."
}
```

Required: `title`, `category`, `confidence`, `observation`, `proposal`,
`expected_effect`, `how_we_would_know`, `risks`.

- `category`: `content` | `code` | `config` | `watch`
- `confidence`: `low` | `medium` | `high`
- **`observation` must cite numbers that appear in the brief.** A proposal
  whose observation cannot be checked against the brief is rejected.
- **`how_we_would_know` must be measurable.** "It'll feel better" is not.
- Prefer **few, specific, reversible** proposals. Three good ones beat
  fifteen. A day with nothing worth changing should produce a `watch`
  proposal saying so — that is a valid, useful outcome.

## What you may NEVER propose

These are hard-refused by `scripts/review_proposals.py`, and a proposal
that tries lands in the report as a policy violation rather than an idea.
This list exists because the obvious way to make the numbers go up is to
lower the bar, and that is the one thing this loop must never do.

1. **Weakening or bypassing the showrunner.** It is the standing editor
   with a veto and its BLOCK is sovereign (`CLAUDE.md`, `docs/DIRECTOR.md`).
   Not the score floor, not the fail-closed behaviour, not `SHOWRUNNER=off`,
   not "skip it when the queue is short". If videos are being blocked, the
   answer is better videos.
2. **Touching the posted logs.** `state/*_posted_log.json` is append-only
   dedupe state. Losing an entry means a duplicate upload.
3. **Weakening the punch-up guard, the placement gate, the graph drama
   gate, or the media verification** (SHA-256 / pixel decode / placeholder
   checks). These exist because each one already caught a real failure.
4. **Raising output volume by lowering a quality bar.** More videos is not
   a goal. Better videos is the goal.
5. **Disabling a test, a CI gate, or an editorial check** to make something
   pass.
6. **Anything that fabricates data** — invented statistics, unsourced
   numbers, synthetic analytics.

Proposing *stronger* gates is always allowed. Proposing to fix the thing a
gate is catching is always allowed.

## What happens next

`scripts/review_proposals.py` validates shape, refuses the forbidden
classes, flags anything touching load-bearing files as
`requires_operator`, and ranks the rest by evidence strength into
`retro/<date>/triage.json`. A reviewer reads that and decides. Some
proposals will be implemented, some will be asked for more evidence, some
will be declined — and a declined proposal that was honestly argued is a
better outcome than a vague one that gets adopted.
