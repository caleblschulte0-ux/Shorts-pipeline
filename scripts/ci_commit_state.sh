#!/usr/bin/env bash
# Hardened state persist for CI (audit Ticket 1) — the ONE way every
# workflow commits state back to the repo.
#
#   Usage: bash scripts/ci_commit_state.sh "commit message" path [path...]
#   Env:   CI_COMMIT_BRANCH  target branch (default: main)
#
# Behavior (generalizes the battle-tested explainer.yml logic):
#   - stages the given paths; exits 0 quietly when nothing changed
#   - pushes with a 5-attempt retry loop
#   - on a push race: backs up OUR artifacts, hard-resets to origin,
#     restores them, and UNION-MERGES every *_log.json / *posted_log.json
#     among the paths (scripts/merge_posted_log.py) so no dedupe entry
#     from either side is ever lost — a lost entry = a duplicate upload.
set -u

if [ $# -lt 2 ]; then
  echo "usage: ci_commit_state.sh \"commit message\" path [path...]" >&2
  exit 2
fi
MSG="$1"; shift
BRANCH="${CI_COMMIT_BRANCH:-main}"

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

for p in "$@"; do
  git add -- "$p" 2>/dev/null || true
done
if git diff --cached --quiet; then
  echo "[persist] nothing to commit"
  exit 0
fi
# The commit itself must not fail silently: this line is only reached with
# real staged changes, so ANY failure here (a hook, a broken index, a
# read-only checkout) means the state was NOT persisted — and without this
# guard the push loop below would happily push the unchanged HEAD, report
# success, and exit 0 with our artifacts lost. Callers (the watchdog, the
# alarms) treat exit 0 as "the record is durable on the remote".
if ! git commit -m "$MSG"; then
  echo "::error::[persist] git commit failed with changes staged" >&2
  exit 1
fi

for attempt in 1 2 3 4 5; do
  if git push origin "HEAD:$BRANCH"; then
    echo "[persist] pushed on attempt $attempt"
    exit 0
  fi
  echo "[persist] push failed (attempt $attempt) — union-merging onto fresh $BRANCH"
  SAVE=$(mktemp -d)
  # EVERYTHING THE RUN HAS PRODUCED SO FAR, not only the paths of THIS call.
  #
  # `git reset --hard` below throws away every uncommitted change in the
  # checkout. This script is also called MID-RUN by post_stories with a
  # single path (the posted log, pushed the moment a video is live) — and on
  # 2026-09-22 that call lost the race (Phase A, the doctor and a claim had
  # moved main since the 09:36 checkout), backed up the posted log alone,
  # reset, and silently destroyed seven showrunner verdicts appended to
  # state/showrunner_verdicts.jsonl and the repair plan the run had just
  # written. The end-of-run persist then found "nothing changed" in both.
  # The ledger is the showrunner's memory and the rewrite mailbox's
  # evidence; a plan is a repair the next run would otherwise redo.
  # So: back up every modified tracked file too, and restore it. Only the
  # given paths are committed here; the rest stay dirty for the caller's
  # own persist, exactly as if the push had simply succeeded.
  # ...but ONLY what this run actually changed. A listed path the run did
  # not touch (a directory argument like data_learning/ori_episodes, given
  # so a NEW script is picked up when one is written) must not be restored
  # from this checkout over the fresher branch: on 2026-09-23 that put a
  # three-hour-old copy of an episode over an edit that had landed since,
  # with this step reporting success. The run's own changes are the commit
  # it just made (HEAD, on the stale base), anything still dirty, and
  # anything untracked under a listed path.
  { git diff --name-only HEAD~1 HEAD 2>/dev/null
    for p in "$@"; do git ls-files --others --exclude-standard -- "$p" 2>/dev/null; done
    git diff --name-only 2>/dev/null
    git diff --cached --name-only 2>/dev/null; } | sort -u | while read -r p; do
    [ -n "$p" ] && [ -e "$p" ] && cp -a --parents "$p" "$SAVE/" 2>/dev/null || true
    # ...and remember what each one looked like when this run CHECKED OUT
    # (the parent of the commit it just made), so a file that moved on the
    # branch since can be told from one that did not
    base=$(git rev-parse -q --verify "HEAD~1:$p" 2>/dev/null || true)
    [ -n "$p" ] && echo "$p $base" >> "$SAVE/.base"
  done
  git fetch origin "$BRANCH"
  # A file that changed on BOTH sides and has no merge rule keeps the
  # BRANCH's copy. On 2026-09-23 the storyboard review edited an episode
  # script in a run that had checked out three hours earlier; the branch
  # had since taken a rebalanced version of the same script; the race
  # restored the run's copy over it and the persist reported success —
  # 57 cave-mouth scenes back over the 35 that had been argued down. The
  # ledgers below are unioned; anything else two-sided is one run's output
  # against a deliberate push, and the push wins. It is said out loud.
  if [ -f "$SAVE/.base" ]; then
    while read -r p base; do
      case "$p" in
        *posted_log.json|*_log.json|*viz_mechanics.json|*niche.config.json|*.jsonl) continue ;;
      esac
      theirs=$(git rev-parse -q --verify "origin/$BRANCH:$p" 2>/dev/null || true)
      if [ -n "$theirs" ] && [ "$theirs" != "$base" ]; then
        echo "::warning::[persist] $p changed on $BRANCH since this run checked out; keeping the branch's copy, dropping this run's" >&2
        rm -f "$SAVE/$p"
      fi
    done < "$SAVE/.base"
    rm -f "$SAVE/.base"
  fi
  git reset --hard "origin/$BRANCH"
  # Restore every artifact this run generated on top of the fresh branch...
  cp -a "$SAVE/." . 2>/dev/null || true
  # ...then recompute the dedupe ledgers as a UNION of theirs + ours. Scan
  # the backup mirror so ledgers inside directory args (e.g. `state/`) are
  # found too, not just explicitly-listed files.
  # ...and the two LEARNING files the same way (scripts/merge_state_json.py):
  # the mechanic library by `sig` and the story config by `slug`. Restoring
  # OUR copy over fresh main deleted four just-merged exemplars from the
  # library on 2026-09-21, fourteen minutes after they landed, with this
  # step reporting success.
  # ...and every append-only *.jsonl ledger (the showrunner's verdicts) as a
  # UNION OF LINES — theirs, then ours that theirs lacks — so a verdict
  # appended on either side of the race survives.
  (cd "$SAVE" && find . -type f \( -name '*posted_log.json' -o -name '*_log.json' \
        -o -name 'viz_mechanics.json' -o -name 'niche.config.json' \
        -o -name '*.jsonl' \) 2>/dev/null) \
  | while read -r rel; do
    rel="${rel#./}"
    THEIRS=$(mktemp)
    case "$rel" in
      *.jsonl)
        git show "origin/$BRANCH:$rel" > "$THEIRS" 2>/dev/null || : > "$THEIRS"
        python3 scripts/merge_state_json.py "$THEIRS" "$SAVE/$rel" "$rel" \
          || { echo "::error::[persist] union-merge failed for $rel — refusing to overwrite either side" >&2
               touch "$SAVE/.merge_failed"; }
        rm -f "$THEIRS"
        continue ;;
      *viz_mechanics.json|*niche.config.json)
        git show "origin/$BRANCH:$rel" > "$THEIRS" 2>/dev/null || echo '' > "$THEIRS"
        python3 scripts/merge_state_json.py "$THEIRS" "$SAVE/$rel" "$rel" \
          || { echo "::error::[persist] union-merge failed for $rel — refusing to overwrite either side" >&2
               touch "$SAVE/.merge_failed"; }
        rm -f "$THEIRS"
        continue ;;
    esac
    git show "origin/$BRANCH:$rel" > "$THEIRS" 2>/dev/null || echo '{}' > "$THEIRS"
    # A merge failure means a side is CORRUPT (merge_posted_log fails
    # closed on unparseable input). The old fallback here — cp OURS over
    # the merge target — was exactly the silent mass-drop the union exists
    # to prevent, and when OUR copy was the corrupt side it pushed garbage
    # over the good remote ledger. Flag and refuse instead; the while runs
    # in a pipeline subshell, so a plain `exit` would never reach the
    # caller — hence the flag file.
    python3 scripts/merge_posted_log.py "$THEIRS" "$SAVE/$rel" "$rel" \
      || { echo "::error::[persist] union-merge failed for $rel — refusing to overwrite either side" >&2
           touch "$SAVE/.merge_failed"; }
    rm -f "$THEIRS"
  done
  if [ -e "$SAVE/.merge_failed" ]; then
    rm -rf "$SAVE"
    echo "::error::[persist] a dedupe ledger could not be union-merged; state NOT pushed. Repair the corrupt side (git history has the last good copy) and re-run." >&2
    exit 1
  fi
  rm -rf "$SAVE"
  for p in "$@"; do
    git add -- "$p" 2>/dev/null || true
  done
  # Same rule as the first commit, with one benign case: after the
  # union-merge the fresh branch may already contain everything we produced
  # (the racing push carried identical state), in which case "nothing to
  # commit" means the record IS durable on the remote — that is a success,
  # not a swallow. A commit failure with changes still staged is real and
  # must reach the caller, not loop into a no-op push that reports success.
  if ! git commit -m "$MSG"; then
    if git diff --cached --quiet; then
      echo "[persist] union-merge left no delta — remote already has our state"
      exit 0
    fi
    echo "::error::[persist] git commit failed with changes staged (after union-merge)" >&2
    exit 1
  fi
  sleep 2
done

echo "::error::[persist] failed to push state after 5 attempts"
exit 1
