# The Doctor — the standing diagnosis of this repository

Operator ruling, 2026-08-05: *"ChatGPT will read the main repo line by line
and make a long-term plan, short-term plan, small fixes, bug fixes, whatever
it sees, and send that in a file somewhere in the repo that you'll go look at
and be like — we should do this, we are not gonna do this, this is still a
ways out, we're working on this."*

    ChatGPT   READS the code and the runtime evidence, and FILES findings.
              It never edits code. It is the diagnostician.
    Claude    RULES on each finding, and builds the ones it accepts.
              A scheduled Claude session picks the work up.
    Nothing   is applied automatically. There is no autonomous fix path.

Working files: `doctor/` (contract in `doctor/README.md`).
Code: `scripts/doctor.py`. Rules held by: `tests/test_doctor.py`.

## The daily loop

```
 23:15 UTC  retro.yml    performance evidence pack (analytics)
 01:15 UTC  alarm.yml    judges the finished day by OUTCOMES; red when wrong
 05:10 UTC  doctor.yml   writes doctor/evidence.json for the reviewer
   morning  ChatGPT      ← woken by a task IN THE CHATGPT APP
                         reads the repo + the pack, files doctor/reports/<date>.json
  on push   doctor.yml   validates it, folds accepted findings into the backlog,
                         nudges the tracking issue
      then  Claude       ← woken by a task IN THE CLAUDE APP
                         rules on what is waiting, builds what it accepted
```

**The two agents are woken from inside their own apps** — one scheduled task
in ChatGPT, one in Claude. Not by GitHub, not by a browser extension. Adding
a cron here to "start" the doctor would do nothing at all.

GitHub's only jobs are the two things neither app can do for itself:
generate the evidence pack (it needs to run Python against live state), and
validate a report once it has landed. Everything else is the apps' own
schedules, and they are the operator's to set.

A consequence worth knowing: because the two schedules are local-time and
the pack is a UTC cron, the reviewer can occasionally read a pack written
before that day's rulings. That is safe by construction — `validate` reads
`verdicts.json` live, so a stale pack costs at most a rejection ChatGPT
could have avoided, never a wrong decision. The push trigger on
`doctor/verdicts.json` keeps it fresh in the normal case.

## Why this is not the retro loop

They look similar and they are deliberately separate:

| | `retro/` | `doctor/` |
|---|---|---|
| reads | analytics — what performed | the **code** — what is wrong or missing |
| output | per-day proposals, accept/refuse | a **standing backlog** with a lifecycle |
| horizon | one day's experiment | bugs → small fixes → short term → **long term plan** |

Retro answers "what should we try next?". The doctor answers "what is the
state of this codebase, and what should we build?". A performance experiment
and an architectural finding do not belong in the same queue — one is judged
by a metric, the other by reading code.

They share the refusal list, which is imported from
`scripts/review_proposals.py` rather than copied, so the two can never drift
on what is unacceptable.

## The verdicts — the operator's own words

| ruling | means | effect |
|---|---|---|
| `doing` | "we should do this" | queued; `doctor.py next` surfaces it |
| `not_doing` | "we are not gonna do this" | settled indefinitely |
| `later` | "this is still a ways out" | parked 30 days by default |
| `in_progress` | "we're working on this" | a session has it |
| `done` | shipped | closed, records the commit |

```bash
python scripts/doctor.py backlog --state new      # what needs a decision
python scripts/doctor.py next                      # what to build
python scripts/doctor.py rule <sig> doing --because "..."
```

Always give a real `--because`. It is quoted back to ChatGPT when it tries to
re-file the item, and a refusal with a reason teaches while a bare "no" just
gets re-argued in new words.

## Landing a ruling on main: never `[skip ci]` on a claude/* PR

`doctor.py rule` only edits `doctor/verdicts.json` on disk — a session still
has to commit and push it. That push almost always goes out as a PR from a
`claude/*` branch (direct pushes to `main` are refused for this token), and
`auto-merge.yml`'s sanity/tests gate is the *only* thing that can merge that
PR — there is no human review on these.

**Never put `[skip ci]` in the commit message for that push.** `[skip ci]`
suppresses every GitHub Actions run for that commit, on `pull_request`
events exactly as much as on `push` — including `auto-merge.yml`. A
bookkeeping-only PR (`doctor/verdicts.json` alone, changing nothing
executable) looks exactly like the kind of commit this repo's other
automation marks `[skip ci]` (`explainer: update posted log [skip ci]`,
`watchdog: chatgpt task verdicts ... [skip ci]`) — but those are pushed
*directly to main by CI itself* and never need a PR gate. Doing the same on
a `claude/*` PR is self-defeating: the PR sits at `mergeable_state: clean`
with **zero check runs**, forever, because the one check that could pass it
never runs. Nothing about that looks alarming in a PR list — it just reads
as "open, unreviewed" — so it goes unnoticed.

This happened three times before anyone caught it: PR #314 (2026-08-25) sat
stuck for 11 days, PR #323 (2026-09-02) took an entire day's worth of
backlog rulings down with it — never reaching main, so the next day's
session read the backlog as untouched and redid the same triage from
scratch — and PR #327 (2026-09-04) repeated it a third time before #329
finally landed both orphaned rulings. If a bookkeeping PR you opened shows
`mergeable_state: clean` but zero check runs after a minute, check its head
commit for `[skip ci]` first.

## The thing that makes it survive — durable verdicts

A reviewer that re-reads the whole repo every morning **will** re-suggest
what you killed last week, and a file that repeats itself is a file you stop
opening. So:

- every finding gets a **stable signature** keyed on what it TOUCHES (area +
  files + horizon), never on wording — a thesaurus cannot smuggle a settled
  item back in;
- `doctor/verdicts.json` is the standing record, and it survives rewrites;
- `evidence.json` **publishes every settled ruling to ChatGPT**, because a
  reviewer cannot avoid re-filing what it is never shown;
- `doctor.py validate` refuses a re-file of a settled finding unless it
  carries `new_evidence_since` naming what actually changed.

`tests/test_doctor.py` proves the reworded-refile case specifically. It is
the single most important test in the file.

## What a report must survive

- **the schema** — required fields, known horizon and severity;
- **checkable evidence** — a finding whose evidence cannot be verified by
  opening a file is not a finding;
- **real files** — naming a file that does not exist is the cheapest
  hallucination to catch, so it is caught;
- **the refusal list** — weakening a gate, deleting a test, pruning a posted
  log, more volume through a lower bar, fabricating data. Refused however
  well argued. A STRONGER gate is always welcome;
- **anti-repetition** — as above.

Rejections are the gate working, not an error. They are reported on the
tracking issue so the reviewer learns what does not fly.

## Authority

ChatGPT filing findings here is the same thing as ChatGPT writing retro
proposals: **suggestions, not edits**. The 2026-08-02/03 emergency in which
it was explicitly authorized to edit production code was scoped to that
outage and is closed (see CLAUDE.md). Reading the code and writing about it
has never required an exception — that is the job.

## Deliberately not in v1

- No autonomous fix path. The first draft of this had one; it was more than
  was asked for and it is gone.
- No auto-ruling. Claude decides, every time.
- No second suggestion queue for performance — that is retro's job.
