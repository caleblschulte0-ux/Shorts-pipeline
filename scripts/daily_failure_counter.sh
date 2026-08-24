#!/usr/bin/env bash
# The failure-counter policy of the Daily Shorts workflow — extracted
# VERBATIM from the "Update failure counter" step of
# .github/workflows/daily.yml (doctor finding 9943424b8251, 2026-08-24) so
# tests/test_production_outcome.py can EXECUTE the policy against fixture
# state instead of pinning tokens in workflow text. Same reads, same writes,
# same decisions, same messages; the only change is that the step's inline
# `${{ steps.run.outcome }}` expression now arrives as $RUN_OUTCOME, which
# the workflow passes as env on the invoking step.
#
# Inputs (env):
#   RUN_OUTCOME   the orchestrator step's outcome ("success" / "failure"),
#                 wired in daily.yml as RUN_OUTCOME: ${{ steps.run.outcome }}
# Reads:   state/production_runs/<today-UTC>/trending.json  (outcome file)
#          state/failure_count.txt
# Writes:  state/failure_count.txt
#
# Run from the repo root (daily.yml's working directory), as the inline
# step was. The inline step ran under Actions' default `bash -e`; a script
# gets a fresh shell, so restate it:
set -e

# THE COUNTER FEEDS AUTO-PAUSE, SO WHAT COUNTS AS "FAILURE" IS
# POLICY, not plumbing. The 2026-08-02 change made the run RED
# whenever uploaded < expected — which is right for VISIBILITY
# (a partial day must never look green), but it also fed every
# shortfall into this counter. That meant two days in which the
# SHOWRUNNER correctly held one video would auto-pause the whole
# channel — a machine that punishes the gate for working, and
# exactly the "more output via a lower bar" pressure the doctrine
# refuses. (The old code said this in its own comment: "a
# quarantine is an intentional skip, not a crash — it must NOT
# bump the auto-pause counter".)
#
# So: the RUN stays red on any shortfall (ChatGPT's visibility
# rule, kept), but the COUNTER bumps only on a ZERO-upload day —
# the outage shape it has always existed to catch. The judgment
# comes from the machine-readable production outcome the
# orchestrator now writes.
mkdir -p state
TODAY=$(date -u +%Y%m%d)
OUT="state/production_runs/$TODAY/trending.json"
UPLOADED=$(python3 -c "
import json,sys
try: print(int(json.load(open('$OUT')).get('uploaded') or 0))
except Exception: print(-1)")
if [ "$RUN_OUTCOME" = "success" ]; then
  echo "0" > state/failure_count.txt
  echo "Run OK — counter reset."
elif [ "$UPLOADED" -gt 0 ]; then
  echo "::warning::partial day ($UPLOADED uploaded) — run is RED for repair visibility, but a held/quarantined video is the gate working, not an outage. Counter NOT bumped."
else
  fc=$(cat state/failure_count.txt 2>/dev/null | tr -d '[:space:]' || echo 0)
  new=$((fc + 1))
  echo "$new" > state/failure_count.txt
  echo "::warning::Zero uploads — failure counter now $new (auto-pause at 2)."
fi
