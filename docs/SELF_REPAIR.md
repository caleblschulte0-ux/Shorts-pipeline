# Self-repair — the daily session that fixes what keeps going wrong

Operator, 2026-09-26: *"we can't be babysitting every little video."*

The pipeline already holds, re-authors and repairs individual videos on its
own. What still needed a person was the step above that: reading the day's
verdicts, noticing that the same defect keeps coming back, and fixing it
**at the level of the code that produces it**. This routine is that step.
It runs once a day as an unattended Claude session (a Routine that starts a
fresh session), fixes ONE recurring class of defect, and leaves a note.

It is Claude editing the pipeline, on a `claude/*` branch, through a PR that
auto-merges — the same authority and the same path as an interactive session
(`CLAUDE.md`, "WHO MAY EDIT THIS PIPELINE").

## The run, in order. A run that skips a numbered step FAILED.

0. **Finish yesterday first.** List open PRs from branches starting
   `claude/self-repair-`. If one is red or conflicted, that is today's job:
   fix it (rebase, root-cause the failing test) and stop. Never skip,
   disable or delete a test to get green.

1. **Branch.** `git fetch origin main` and create
   `claude/self-repair-<YYYYMMDD>` from `origin/main`.

2. **Gather the evidence.**
   - Today's and the previous two days' rows of
     `state/showrunner_verdicts.jsonl` (`ts` is UTC): `slug`, `score`,
     `verdict`, `auto_fails`, `problems`, `weakest_scene`.
   - `state/production_runs/<YYYYMMDD>/*.json` for what shipped and why the
     rest did not.
   - The last three notes in `self_repair/` so you do not redo a class, and
     so you can see whether yesterday's fix held.
   - When a verdict names something you cannot see from the text, read the
     day's `daily.yml` / `explainer.yml` job log (GitHub MCP
     `get_job_logs`) — the render log says which panel was dropped, which
     request 429'd, which fallback fired.

3. **Group by class, not by video.** A class is one thing the CODE does
   wrong, wherever it shows up: "tip labels in the series colour are
   unreadable", "caption events overlap", "image requests are rate-limited",
   "the last beat's picture repeats in the closing". Count, for each class,
   the videos and the days it appeared in. Auto-fails and FATAL checks count
   double.

4. **Pick ONE class**: the most frequent one that is fixable in code in this
   session. Not fixable here — say so in the note and move to the next:
   - a dead credential or quota (ping the operator; see step 9),
   - anything whose fix would touch a file below.

   **Never touched by this routine** (a human decides these, always):
   everything in `PROTECTED_FILES` and `OPERATOR_REVIEW_FILES` in
   `scripts/review_proposals.py` — the showrunner, the publish gate, the
   punch-up guard, the placement gate, the package schema, the rubric, every
   workflow, the uploaders, `CLAUDE.md` — and any posted log.
   **Never done**, whatever the evidence says: lowering a threshold,
   weakening or bypassing a gate, raising volume by lowering a bar, deleting
   or skipping a test, inventing data. The answer to "videos are being
   blocked" is a better video. `scripts/review_proposals.py`'s
   `FORBIDDEN_INTENT` is the same list in code; if your plan matches it,
   pick another class.

5. **Reproduce it.** Render the offending thing offline and LOOK at the
   frames before changing anything:
   - a graph race: `engines.chart_race.render(spec, out)` on the day's
     package from `state/trending_packages/<date>/`;
   - an explainer machine or beat: `data_learning/viz_scene` draw functions,
     or a full `studio_render.render(slug, out, config_path=<a COPY>)`;
   - a reddit story: `make_reddit_story` pieces (captions, card, panels).
   Measure motion with `scripts/showrunner_review._temporal_evidence`.

6. **Fix the class.** The smallest change that removes the defect
   everywhere it can occur. Follow `CLAUDE.md` and the doctrine files it
   names (`docs/CHANNEL_LOOK.md`, `docs/DATA_MACHINES.md`). Read the comments
   around the code you change — most of this code carries the verdict that
   shaped it, and a fix that undoes an older fix is not a fix.

7. **Prove it.**
   - Add a test that FAILS on the old code (check it: put the old file back,
     run the test, restore) and passes on the new.
   - Run every test module that touches the files you changed
     (`grep -l <module> tests/*.py`). Do not edit source while they run.
   - Re-render the case from step 5 and look at it again.

8. **Ship.** Rebase onto `origin/main`, push, open a PR whose body quotes the
   verdicts, states the cause, the fix and the test results. Auto-merge
   takes it from there. Include the note from step 9 in the same PR.

9. **Leave a note**: `self_repair/<YYYYMMDD>.md`, ten lines at most —
   the class and its counts, what was fixed, what is still recurring and why
   it was not fixed today. If something needs the operator (a dead key, a
   quota, a decision), write it as the first line, starting `OPERATOR:`, with
   the exact action required; the Routine's push notification carries it.

One class per run. A day with no recurring class writes a one-line note and
stops.
