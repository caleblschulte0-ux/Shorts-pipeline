#!/usr/bin/env bash
# Publish staged review media (frames + contact sheets for the ChatGPT judge
# of last resort, shared/review_mailbox.py) to the `preview-renders` orphan
# branch — the repo's existing home for previews, never `main` (CLAUDE.md
# storage rules: no media in main).
#
# Usage: publish_review_media.sh [staging-dir]   (default: output/review_media)
#
# IN A SEPARATE WORKTREE, NEVER BY SWITCHING THE RUN'S OWN CHECKOUT. The
# first live run (2026-09-21 21:59 UTC) did `git checkout -B preview-renders
# origin/preview-renders` in the render's working tree, which had an
# uncommitted state/showrunner_verdicts.jsonl; the checkout refused (the
# error was sent to /dev/null), the script fell into its "no branch yet"
# path, committed an ORPHAN root, and pushed it four times against a branch
# with history — "non-fast-forward" every time — then printed "published 22
# file(s)". The review request went to ChatGPT with a sheet URL that 404s.
#
# ADDS to the branch, never replaces it (the canary evidence publisher
# learned that the hard way: an emptied index deleted every earlier
# render's evidence). Exits 0 quietly when there is nothing staged; exits
# NON-ZERO when the push fails, because a request whose frames are not
# where it says they are is a request nobody can answer.
set -euo pipefail
stage="${1:-output/review_media}"
if [ ! -d "$stage" ] || [ -z "$(find "$stage" -type f -print -quit 2>/dev/null)" ]; then
  echo "[review-media] nothing staged under $stage"; exit 0
fi
stage="$(cd "$stage" && pwd)"
git config user.name  "github-actions[bot]" >/dev/null 2>&1 || true
git config user.email "github-actions[bot]@users.noreply.github.com" >/dev/null 2>&1 || true

wt="$(mktemp -d)"
cleanup() { git worktree remove --force "$wt" >/dev/null 2>&1 || rm -rf "$wt"; }
trap cleanup EXIT

# The branch's tip, fetched shallow into a remote-tracking ref this repo may
# not have a refspec for (a single-branch checkout does not).
if git fetch --depth=1 origin "+refs/heads/preview-renders:refs/remotes/origin/preview-renders" 2>/dev/null; then
  git worktree add --detach "$wt" origin/preview-renders >/dev/null
  git -C "$wt" checkout -qB preview-renders
else
  git worktree add --detach "$wt" >/dev/null
  git -C "$wt" checkout -q --orphan preview-renders
  git -C "$wt" rm -rq --cached . 2>/dev/null || true
  git -C "$wt" clean -fdq 2>/dev/null || true
fi

cp -r "$stage/." "$wt/"
git -C "$wt" add -f reviews
if ! git -C "$wt" -c user.name="github-actions[bot]" -c user.email="github-actions[bot]@users.noreply.github.com" \
     commit -qm "review media: $(date -u +%Y-%m-%dT%H:%MZ) [skip ci]"; then
  echo "[review-media] nothing new to commit"; exit 0
fi

pushed=0
for i in 1 2 3 4; do
  if git -C "$wt" push origin HEAD:refs/heads/preview-renders; then pushed=1; break; fi
  sleep $((2**i))
  # someone else published meanwhile: replay our one commit on their tip
  git -C "$wt" fetch --depth=1 origin "+refs/heads/preview-renders:refs/remotes/origin/preview-renders" || true
  git -C "$wt" rebase -q origin/preview-renders || { git -C "$wt" rebase --abort || true; }
done
if [ "$pushed" != 1 ]; then
  echo "::error::[review-media] could not push review frames to preview-renders — the review request's sheet_url will 404"
  exit 1
fi
echo "[review-media] published $(find "$stage" -type f | wc -l) file(s) -> preview-renders"
