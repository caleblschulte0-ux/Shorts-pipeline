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
git commit -m "$MSG"

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
    python3 scripts/merge_posted_log.py "$THEIRS" "$SAVE/$rel" "$rel" \
      || cp "$SAVE/$rel" "$rel"
    rm -f "$THEIRS"
  done
  rm -rf "$SAVE"
  for p in "$@"; do
    git add -- "$p" 2>/dev/null || true
  done
  git commit -m "$MSG" || true
  sleep 2
done

echo "::error::[persist] failed to push state after 5 attempts"
exit 1
