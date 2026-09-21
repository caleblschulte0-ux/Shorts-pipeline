#!/usr/bin/env bash
# Publish staged review media (frames + contact sheets for the ChatGPT judge
# of last resort, shared/review_mailbox.py) to the `preview-renders` orphan
# branch — the repo's existing home for previews, never `main` (CLAUDE.md
# storage rules: no media in main).
#
# Usage: publish_review_media.sh [staging-dir]   (default: output/review_media)
#
# ADDS to the branch, never replaces it (the canary evidence publisher
# learned that the hard way: an emptied index deleted every earlier
# render's evidence). Exits 0 quietly when there is nothing staged.
set -euo pipefail
stage="${1:-output/review_media}"
if [ ! -d "$stage" ] || [ -z "$(find "$stage" -type f -print -quit 2>/dev/null)" ]; then
  echo "[review-media] nothing staged under $stage"; exit 0
fi
tmp="$(mktemp -d)"
cp -r "$stage/." "$tmp/payload/"
git config user.name  "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"
git fetch origin preview-renders --depth=1 || true
if git checkout -B preview-renders origin/preview-renders 2>/dev/null; then
  :        # the branch exists: its files are now the working tree
else
  git checkout --orphan preview-renders
  git rm -rq --cached . 2>/dev/null || true
  git clean -fdq -e evidence -e reviews 2>/dev/null || true
fi
cp -r "$tmp/payload/." ./
git add -f reviews
if git commit -qm "review media: $(date -u +%Y-%m-%dT%H:%MZ) [skip ci]"; then
  for i in 1 2 3 4; do
    git push origin preview-renders && break || { sleep $((2**i)); git pull --rebase -q origin preview-renders || true; }
  done
  echo "[review-media] published $(find reviews -type f | wc -l) file(s) -> preview-renders"
else
  echo "[review-media] nothing new to commit"
fi
git checkout -q - 2>/dev/null || git checkout -q main
