# Daily run state

These files are written back by the daily GitHub Action. Hand-editing is
fine when you want to override behavior.

## `posted_log.json`
History of every catalog entry the orchestrator has posted. The
orchestrator avoids re-picking anything that appears here until the
catalog is exhausted.

## `failure_count.txt`
Auto-pause counter. Reset to `0` after every successful run.

- `0` or `1` — keep running tomorrow
- `2` or more — orchestrator skips runs and just sends a "we're paused"
  notification. Edit this file back down to `0` to resume.

## `PAUSED` (in repo root, not here)
Manual kill switch. If the file exists in the repo root, the next
scheduled run skips. Delete it to resume. Fastest way to flip from your
phone: GitHub Mobile → file → Delete.
