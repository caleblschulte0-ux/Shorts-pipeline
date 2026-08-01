# The Pipeline Doctor — the daily autonomous maintainer

Operator ruling, 2026-08-01: *"every day, look at the pipeline, look at
what's working, what's not working, recommend changes, and then actually go
and fix shit — so I don't have to keep coming on here. You guys are just
gonna figure it out on your own eventually, even if it takes a little
longer."*

Code: `scripts/pipeline_doctor.py`. Schedule: `doctor.yml`, 02:30 UTC daily.
Memory: `state/doctor/journal.jsonl`. Rules held by:
`tests/test_doctor.py`.

## What it is

A daily cycle that turns yesterday's OUTCOMES into today's fixes:

```
 23:15 UTC  retro.yml       evidence pack; ChatGPT reviews it overnight
 01:15 UTC  alarm.yml       judges the day by outcomes; red when wrong
 02:30 UTC  doctor.yml      ← THIS
             1 gather      alarm verdict, showrunner ledger, exchange
                           reports, reserve bank, triaged suggestions,
                           its own journal
             2 diagnose    findings with STABLE signatures
             3 judge       yesterday's actions: resolved or failed, by
                           whether the outcome they named actually happened
             4 mechanical  deterministic playbooks (≤3/day)
             5 authored    ONE brain-written fix → claude/doctor-<date>
                           branch → constitution review → full suite →
                           PR → the auto-merge gate re-runs everything
             6 report      what it may not touch, with the exact command
 ~09:19 UTC the Routine starts the new day
```

## The authority model — why this is allowed to exist

CLAUDE.md's ruling: **Claude is the only agent that edits this repository**,
and an interactive session's authority comes from working "on a `claude/*`
branch through a PR". The doctor's brain is a headless Claude doing exactly
that. Its reviewer is the gate: 650+ tests, the drift guards, the dry-runs,
run twice (locally before the PR exists, again by auto-merge).

ChatGPT's place is unchanged: it **proposes** (retro proposals), it never
edits. The doctor consumes ChatGPT's ideas only through
`review_proposals.py` triage output (`retro/<date>/triage.json`) — after
the refusal list has run — and implements accepted ones on its own
authority as a Claude. The doctor never reads raw proposals; the two
workflows allowed to touch them remain exactly `retro.yml` and
`retro_decide.yml` (`tests/test_retro.py` enforces it).

## The constitution — what it can NEVER do

Enforced on the diff, in code (`review_diff`), before a PR can exist. A
violation discards the entire day's authored work. Tested attack-by-attack
in `tests/test_doctor.py`.

The doctor may never:

- edit the showrunner (`scripts/showrunner_review.py`,
  `shared/showrunner_gate.py`), the punch-up guard, the placement gate, the
  package buffer, or `docs/DIRECTOR.md` — the proposal triage's protected
  set, imported from `review_proposals.py` so there is ONE list;
- **silence its own alarm or rewrite its own rules**
  (`scripts/daily_alarm.py`, `scripts/pipeline_doctor.py`, their tests,
  `scripts/review_proposals.py`);
- delete a test file, remove a test function, or net-remove assertions;
- remove any line mentioning the showrunner, fail-closed handling, a
  posted log, or a guard — **gates may only be ADDED**;
- write under `.github/`, `config/`, `exchange/`, `retro/`,
  `assets/mascot/`, or `state/` outside `state/doctor/`;
- edit doctrine (`CLAUDE.md`, routine instructions, this file);
- exceed 8 files / 400 changed lines per fix, or 1 authored fix per day.

Everything else — renderers, scenes, funnel, engines, non-protected shared
code, new tests — is its working surface. Making any gate **stronger** is
always allowed. Widening the constitution is the operator's act alone, done
by editing `pipeline_doctor.py` + `tests/test_doctor.py` in an interactive
session.

## The closed loop — the part that makes it a doctor, not a scriptwriter

Every action journals the outcome it expects (usually: a named alarm code
absent on the next judged day). The next run marks it **resolved** or
**failed** against reality. Two failures on one signature and the doctor
**stops trying** and escalates to a report — it never grinds the same
failed fix forever, and it never gets to claim success; the alarm does.

`state/doctor/journal.jsonl` is append-only and is the doctor's memory
across days: dedup (one shot per signature per day), cooldown, escalation,
and the honest record of what it did and whether it worked.

## Mechanical playbooks (v1)

Deterministic, precondition-gated, no brain involved:

| playbook | trigger | why it is safe |
|---|---|---|
| `redispatch_phase_b` | `done_but_no_report` and the DONE marker is still unconsumed | Phase B validates checkpoints; posted logs dedupe any already-published slot. This is the exact remedy for the 2026-08-01 wrong-bundle incident. |

New playbooks earn their place one at a time, each with the precondition
that makes it safe stated next to it.

## Failure honesty

- No token / CLI install fails → the authored fix is **skipped and
  journaled as failed**, never silently.
- Constitution refuses, or the suite fails on the brain's diff → the tree
  is reset, the failure journaled; nothing half-fixed survives.
- The report comments on the tracking issue **only when there is
  something** — a daily "all good" is how people stop reading. A quiet
  doctor is a healthy pipeline.

## What v1 leaves for later (deliberately)

- More playbooks (corrupt-cache sweep, stale-branch inventory).
- Reading CI run logs as evidence (needs `gh` in the gather path).
- A weekly "second opinion" pass where the brain reviews the doctor's own
  journal for patterns across days.
- Widening the authored surface (workflows, uploader) — operator's call,
  after the doctor has a track record worth trusting.
