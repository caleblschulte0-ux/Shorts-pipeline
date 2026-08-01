# The closed creative-improvement loop

> A judge response that cannot be viewed after the runner disappears is
> treated as MISSING judge evidence.

Shared capability — every channel, every format. Nothing here selects behavior
by story slug, title, topic or id.

```
render → run every judge → persist every response → rank a repair plan
       → materially revise → re-render → re-judge → compare
       → pass · escalate · abandon
```

## Why it exists

The pipeline was optimized to prevent broken or unsafe videos, and it was good
at that. The *creative* loop was open: mechanical defects were repaired by the
gates that detected them, the real taste judge was asked afterwards, and its
answer was recorded rather than acted on. Two concrete failures followed.

1. **A mediocre film could advance.** The gate was "no reject labels AND
   personality ≥ 3". A film scoring **3.0/10** against professional work
   satisfied it. The one number that answered *"would I believe a professional
   editor shipped this?"* was written down and ignored.
2. **The complaints died with the runner.** `worst_beat`, `fix`, pacing and
   hook complaints were printed to an Actions log. A green workflow could hide
   every criticism that mattered.

## The five pieces

| module | job |
|---|---|
| `data_learning/judge_policy.py` | the binding quality law |
| `data_learning/judging_store.py` | append-only durable evidence |
| `data_learning/repair_planner.py` | findings → ranked repair tasks |
| `data_learning/judge_loop.py` | the loop + escalation + comparison |
| `data_learning/judges.py` | production judge adapters |
| `scripts/judge_report.py` | the human + Actions surfaces |

### 1. The quality score is binding

| band | score | meaning |
|---|---|---|
| `structural_failure` | < 7.5 | the creative approach is failing |
| `repair_required` | 7.5 – 8.49 | repairable |
| `internal_review` | 8.5 – 8.99 | internal review only |
| `owner_review` | ≥ 9.0 | eligible for owner review |

Advancement out of the development loop needs `overall_10 ≥ 8.0` **and**
personality ≥ 3 **and** no hard objection **and** no unresolved majors **and**
no unresolved judge disagreement **and** every required judge to have spoken.

Rules that hold no matter the score:

- **A missing `overall_10` is missing evidence**, not a pass. `judge_verdict.py`
  refuses a verdict without one at the door.
- **One hard objection blocks.** `decide()` never folds a blocker into a mean.
- **Dissent is a blocker, not a rounding problem.** Every dissenting judge is
  preserved by name.
- **A required judge that failed or abstained fails closed.**
- **The score never unlocks publishing.** Only the separately approved launch
  policy does, and it is off by default.

Everything is configurable via a `judge_policy` block in the channel config or
`CURIOSITY_JUDGE_*` env vars; an unreadable override never loosens the law.

### 2. Evidence that outlives the runner

```
<out>_pkg/judging/
  attempt_01/
    manifest.json            mp4 sha256, package manifest hash, timestamps,
                             rubric version, policy snapshot, runner ids
    <judge>_raw.json         exactly what the judge returned, untouched
    <judge>_normalized.json  the schema the repair engine consumes
    combined_verdict.json    merged view + the binding policy decision
    repair_plan.json         the ranked plan built from those findings
    comparison.json          movement against the previous attempt
  attempt_02/ …
  final_summary.json
  report.md / report.html
```

`next_attempt()` always returns one past the highest on disk, so nothing is
ever overwritten. Every response is bound to the exact artifact judged — a
re-render invalidates stale evidence by construction, not by convention.
Failures and abstentions are recorded; silence is never mistaken for consent.
Small JSON only, never media.

### 3. Findings become work

Ranked by a fixed law, deterministically, so a stalled loop is detectable:

1. **integrity** — factual, safety, licence, artifact blockers
2. **premise** — hook, promise, payoff
3. **structure** — pacing, ordering, stale spans
4. **depiction** — sameness, weak or unsuitable depiction
5. **polish** — captions, framing, local shot repair

Each task carries a target, defect code, severity, subsystem, the **judge's own
recommended fix**, a success criterion, supporting evidence, dependencies and
an effort estimate. Two subsystems aimed at the same shot are resolved by
severity and the loser is **recorded**, not dropped.

### 4. Escalate rather than repeat

| attempt | class | scope |
|---|---|---|
| 1 | `local` | replace media, shorten spans, captions, framing, single beats |
| 2 | `scene` | visual grammar, composition, pacing pattern, transitions |
| 3 | `structural` | hook, narration, beat order, storyboard, creative approach |

The class widens by attempt and a stall widens it further — never narrower. A
structural attempt that still fails **abandons** the approach. The system does
not endlessly move labels around on a fundamentally mediocre video.

### 5. Improvement is measured

`comparison.json` records previous vs new overall and personality, the delta,
defects fixed, defects introduced, defects persisting, whether the *targeted*
defect moved, and whether the artifact hash changed. **A re-render that
produces the same bytes is not a repair**, and the comparison says so. Stalls,
regressions and a repeated plan signature all escalate.

## Where to look

- **Machine-readable**: `<out>_pkg/judging/` in the render package.
- **Human**: `judging/report.md` (and `.html`) — scores by judge and attempt,
  every complaint with its timestamp, the repair asked for, before/after
  movement, defects fixed / remaining / introduced, disagreement, final reason.
- **Actions**: a scoreboard in the run summary, plus the complete evidence as
  the **`curiosity-judging`** artifact.

## Tests

`scripts/test_judge_policy.py` · `test_judging_store.py` ·
`test_repair_planner.py` · `test_judge_loop.py` · `test_judge_report.py` ·
`test_judge_production_wiring.py` — wired as CI Layer 2f. They prove, among
other things, that a 3.0/10 film cannot pass on personality, that a 9.9/10 film
still fails closed when a required judge crashes, that prior attempts are never
overwritten, that a changed video invalidates old evidence, that a stalled
score escalates and a failed structural attempt abandons, and that publishing
stays disabled by default.
