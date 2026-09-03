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
  for p in "$@"; do
    [ -e "$p" ] && cp -a --parents "$p" "$SAVE/" 2>/dev/null || true
  done
  git fetch origin "$BRANCH"
  git reset --hard "origin/$BRANCH"
  # Restore every artifact this run generated on top of the fresh branch...
  cp -a "$SAVE/." . 2>/dev/null || true
  # ...then recompute the dedupe ledgers as a UNION of theirs + ours. Scan
  # the backup mirror so ledgers inside directory args (e.g. `state/`) are
  # found too, not just explicitly-listed files.
  (cd "$SAVE" && find . -type f \( -name '*posted_log.json' -o -name '*_log.json' \) 2>/dev/null) \
  | while read -r rel; do
    rel="${rel#./}"
    THEIRS=$(mktemp)
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
