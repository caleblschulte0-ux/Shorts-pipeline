# retro/ — the daily review loop

Once a day, after the last slot has posted, the pipeline writes an evidence
pack and a reviewer reasons over it. The reviewer writes **proposals**;
Claude decides, implements what it agrees with, and **writes back its
reasoning**. Tomorrow's brief opens with those verdicts, so the next day
continues the work instead of restarting it.

```
23:15 UTC   build_retro.py     -> retro/<date>/brief.json
  ~7pm CT   reviewer reads it  -> retro/<date>/proposals/NN-slug.json
            review_proposals.py triages
            Claude: retro_reply.py --verdict ... --because "..."
                    ships what it agrees with, registers an EXPERIMENT
  next day  the brief opens with those verdicts + what is owed
```

This is a collaboration between two agents with different jobs. The
reviewer sees the numbers and has time to think; Claude has commit access
and judgement about the code. Neither half works alone: proposals without
a decision pile up, and changes without a readout are guesses.

**The goal is that the channel gets measurably better every week with
nobody asking it to.** That is the bar this loop is judged against.

**Nothing in this folder is ever applied automatically.** No workflow reads
a proposal and edits code — a proposal reaches production only by Claude
reading it, agreeing, and shipping it deliberately. That separation is the
entire safety model of a loop that runs unsupervised, and it is not
negotiable no matter how good an idea looks.

---

## "Nothing needs changing" is almost always wrong

The brief carries `what_you_owe_today`. It is computed, not rhetorical:

| Obligation | When it fires |
|---|---|
| `readout` | an experiment's window has closed — read it out with numbers |
| `agenda` | Claude asked you for something and you have not delivered it |
| `no_live_experiment` | **nothing is being tested right now** |
| `coverage` | age bands too thin to judge (advisory) |

**An empty retro is legitimate only when `must_do` is 0.** Any other day,
"nothing to change" means the loop stopped working, not that the channel
is finished. In particular, `no_live_experiment` fires whenever nothing is
running — so on a quiet day the job is to *start* something, not to agree
that things are fine.

Ambition is the point. A channel at single-digit views has enormous room;
the constraint is not ideas, it is evidence. Which is what experiments are
for.

## Experiments — how a small channel learns anything

One day of data on six videos is noise. So a change that claims an effect
is registered as a timed test (`shared/experiments.py`) and **cannot be
concluded early**:

```
hypothesis   what we think is true
change       what shipped
metric       the number that must move, and which way
baseline     that number when the change went live
min_days     no readout before this many days     (default 7)
min_samples  no readout before this many videos   (default 10)
guardrail    a number that must NOT regress       (usually quality)
```

`readout_ready()` refuses until **both** floors pass — twelve samples on
day three still reads "3.0/7 days elapsed". At readout, a move under 15%
is `inconclusive` ("this is weather, not a result"), and **a guardrail
regression outranks a win**: more views bought with worse videos is
recorded as a loss and reverted. That ordering is deliberate and is not
open to proposal.

When you propose a change, say what would make it a success and over what
window. A proposal with no measurable readout is an opinion.

## Working with Claude

- Read `continuity.my_verdicts_on_your_last_proposals` first. If something
  was declined, do not re-file it in new words — either bring the evidence
  Claude asked for, or drop it.
- `continuity.open_agenda` is what Claude explicitly asked you for. Those
  are `must_do` items.
- Claude will often adopt a proposal *modified* — shipping 0.9s where you
  proposed 0.8s, for instance — and the `because` field says why. That
  reasoning is the most useful thing in the brief; it is the channel's
  real constraints, learned.
- Disagreeing is fine and useful. Re-propose with better evidence.

## Who edits this pipeline — not you

**Claude is the only agent that edits this repository** — meaning every
Claude in the system: the interactive sessions AND the headless brains that
author packages, judge renders, and write story words inside the pipeline.
They are one author on different runtimes.

You can run quarterback when the Claude subscription is out, and that job
matters — but it is CONTENT and SUGGESTIONS, never additions to the
pipeline itself.

| You may write | You may never write |
|---|---|
| `exchange/bundles/<date>/response.json` + `DONE` | any `.py`, `.yml`, `.sh` — anywhere, including inside your own folders |
| authored packages, words, media pointers | any workflow, gate, validator or test |
| `retro/<date>/proposals/*.json` | `retro/README.md` or `exchange/README.md` — your own instructions |
| | anything under `scripts/`, `shared/`, `funnel/`, `engines/`, `docs/` |

Nothing mechanically stops you from breaking this — it is a working
agreement, and it holds because you keep it. If you believe something in
the pipeline should change, that is a PROPOSAL: write it as one and Claude
will decide, implement it properly, and tell you what it thought. A change
you make yourself skips the review that makes the change safe, and skips
the reply that would have taught you why.

## How to pick up work — the mailbox

**Do not compute today's UTC date.** The brief is written at ~6:15pm
Central and you may poll after midnight UTC, so "today" is often the wrong
folder and you would find nothing. Ask the repo instead:

```
retro/<review_date>/brief.json        exists = a review is owed
retro/<review_date>/proposals.json    exists = that date is ANSWERED
```

The oldest date with a brief and no `proposals.json` is your job. A day
missed on Tuesday is still open on Wednesday — take the oldest first.
`scripts/retro_mailbox.py` prints exactly this if you can run it.

**Write ONE file: `retro/<review_date>/proposals.json`**, an object with a
`proposals` array. If it already exists for that date, that date is done —
do not write it again. That is what makes re-running you safe.

## The proposal schema

```json
{"proposals": [{
  "proposal_id": "20260801-graph-hook",
  "review_date": "20260801",
  "channel": "trending", "format": "graph_race",
  "category": "content", "confidence": "medium",
  "problem_class": "packaging",
  "observation": "graph_race median_views 0.16 at the 72h cohort vs 0.04 for text_card (n=8 vs 10)",
  "evidence": ["channels.trending.maturity.72h.by_format.graph_race"],
  "proposal": "Cut the graph_race hook overlay from 1.5s to 0.8s",
  "one_variable": "hook overlay duration",
  "files": ["make_graph_race.py"],
  "baseline": 0.16,
  "target_metric": "channels.trending.maturity.72h.by_format.graph_race.median_vph",
  "success_threshold": 0.22,
  "guardrails": ["showrunner avg_score must not drop >10%"],
  "required_samples": 10, "minimum_runtime_days": 7,
  "expected_effect": "better 3-second hold on graph_race",
  "how_we_would_know": "median_vph at the 72h cohort after 10 more posts",
  "risks": "may clip the second line",
  "blast_radius": "graph_race only",
  "rollback": "revert the one constant",
  "new_evidence_since": ""
}]}
```

`problem_class` must be one of `brief.problem_classes` — and picking it is
not a formality. **A render that failed or an upload that never went
public is a `pipeline_failure`, not evidence that viewers rejected the
idea.** A null metric is `insufficient_data`, never a zero.

## What gets your proposal thrown out

- **Numbers that are not in the brief.** Every decimal and every large
  integer in your `observation` is checked against `brief.json`. A
  confident hallucination is more dangerous than a vague one, because it
  reads like rigour and gets adopted.
- **Evidence paths that do not exist.** Cite real fields.
- **Re-filing something already decided.** Identity is channel + format +
  files, so rewording does not evade it. If it was declined and you have
  genuinely new data, set `new_evidence_since` and say what changed.
- **A second experiment on a channel that already has one unresolved.**
  Two concurrent changes make both unreadable — neither verdict can be
  attributed. Wait for the readout.

## Comparing fairly

Use `channels.<name>.maturity` — cohorts at ~24h, ~72h and ~7d, split by
format. Do not compare a 2-hour-old upload with a 7-day-old one, and do
not use a graph_race baseline to judge a reddit_story unless you argue
why that is valid. `mature_enough_to_judge` and `worst_mature` list only
videos old enough to have been seen.

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
