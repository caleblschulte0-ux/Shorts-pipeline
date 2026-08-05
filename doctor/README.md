# The Doctor — ChatGPT's standing read of this repository

This folder is a **conversation between two agents about what to build next**.

    ChatGPT   reads the repo line by line, and the runtime evidence, and
              files findings here. It never edits code.
    Claude    rules on each finding — doing / not doing / later / working on
              it — and builds the ones it accepts.

Nothing in this folder is ever applied automatically. No workflow reads a
finding and changes code. That separation is the safety model, and it is the
same one `retro/` uses.

## What lives here

| File | Written by | What it is |
|---|---|---|
| `evidence.json` | the daily job | runtime truth for ChatGPT to read alongside the code: yesterday's alarm verdict, production outcomes, showrunner ledger, recent commits, **the open backlog and every settled ruling** |
| `reports/<date>.json` | **ChatGPT** | that day's findings |
| `backlog.json` | `scripts/doctor.py ingest` | the standing set of live findings |
| `verdicts.json` | **Claude** | the durable record of every ruling |

## ChatGPT: how to do this job

**1. Read `evidence.json` FIRST.** It contains `settled` — everything Claude
has already decided — and `open_backlog`. This is the difference between a
file that stays useful and one that gets ignored.

**2. Read the repo.** Not just the diff: the actual code, the workflows, the
docs, the tests. You are looking for what a senior engineer would flag —
contradictions between two files that both claim authority, a capability
nothing calls, a gate that can be satisfied without doing the work, a doc
that lies about the code, a failure mode nothing would catch.

**3. Write `reports/<date>.json`** in this schema:

```json
{
  "schema": "shorts-doctor-report/v1",
  "date": "20260806",
  "summary": "one paragraph — the shape of the repo right now",
  "findings": [
    {
      "title": "short, specific",
      "horizon": "bug | small_fix | short_term | long_term",
      "severity": "critical | high | medium | low",
      "area": "trending/render",
      "files": ["make_reddit_story.py"],
      "observation": "what is true right now",
      "proposal": "what to do about it",
      "evidence": "the file, the line, the log, the run — something checkable",
      "new_evidence_since": "(only when re-filing a settled item)"
    }
  ]
}
```

**The horizons are the plan.** `bug` and `small_fix` are things to do now;
`short_term` is the next few weeks; `long_term` is the direction. Write all
four — the long-term plan is as valuable as the bug list, and nobody else is
writing it.

**4. Rules that are not negotiable:**

- **Never edit code, workflows, gates, or docs.** You are the diagnostician.
  (The 2026-08-02 emergency was an explicit, scoped, operator-granted
  exception for a specific outage. It is closed. It does not generalize.)
- **Never re-file a settled finding** without `new_evidence_since` naming
  what actually changed. `scripts/doctor.py validate` refuses it, and it
  matches on WHAT the finding touches, not on how you word it — rewording is
  not new evidence.
- **Never propose lowering a bar.** Weakening the showrunner, pruning a
  posted log, relaxing the punch-up guard or media verification, deleting a
  test, more volume through a lower standard, fabricating data — all
  refused, however well argued. Proposing a STRONGER gate is always welcome.
- **Evidence, not vibes.** A finding whose evidence field cannot be checked
  by opening a file is not a finding.

**5. Validate before you commit:**

```bash
python scripts/doctor.py validate doctor/reports/<date>.json
```

## Claude: how to rule

```bash
python scripts/doctor.py ingest doctor/reports/<date>.json   # fold in
python scripts/doctor.py backlog                              # see it all
python scripts/doctor.py next                                 # what to pick up
python scripts/doctor.py show <signature>                     # one in full

python scripts/doctor.py rule <sig> doing       --because "..."
python scripts/doctor.py rule <sig> not_doing   --because "..."
python scripts/doctor.py rule <sig> later       --because "..."   # parks 30d
python scripts/doctor.py rule <sig> in_progress --because "..."
python scripts/doctor.py rule <sig> done        --commit <sha>
```

Give a real `--because` on every ruling. It is what ChatGPT is shown when it
tries to re-file, and "no" with a reason teaches; "no" alone just gets
re-argued.

`later` parks a finding for 30 days. `not_doing` settles it indefinitely.
Both can be reopened by genuine new evidence — that is the point of the
escape hatch, and why it requires naming what changed.
