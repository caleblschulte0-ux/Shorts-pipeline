# Claude Launch Path — Production Integration

This is the starting point for Claude after reviewing draft PR #174.

## Current state

- Review/test scope: **100%**
- Migration rehearsal gates: **14/14 passed**
- Isolated launch-closure tests: **54/54 passed**
- Production contracts frozen: **8/8**
- Archetypes rehearsed: **5/5**
- Temporary production-format MP4s generated during rehearsal: **15**
- Consecutive reviewer replays: **10/10 shipped for shadow artifacts**
- Rollback drills: **5/5 verified**
- Production files modified by this PR: **0**
- Publishing enabled: **no**

## Start here

```bash
python -m unittest -v review_prototypes.integration_bridge.test_integration_bridge
python -m unittest -v review_prototypes.launch_closure.test_launch_closure
python -m review_prototypes.launch_closure.cli --out /tmp/shorts-launch-rehearsal
```

Stop immediately if any command fails or if the frozen production contract probe reports drift.

## Execution order

1. **Preflight only.** Confirm the eight production contracts and both isolated suites.
2. **Patch targets 1–3 only.** Add optional metadata acceptance to `story.py`, preview-gated routing to `viz_director.py`, and verified performance overrides to `charts.py`.
3. **Matched dry run.** Render the same slug with the same sources and narration as baseline and shadow. Publishing must remain frozen.
4. **Renderer integration.** Add preview-only consumption in `studio_render.py`. Do not change default behavior.
5. **Reviewer diagnostics only.** Add context to `showrunner_review.py`; do not change `WEIGHTS`, `AUTOFAIL_CHECKS`, `MIN_SCORE`, `decide_verdict`, or any fail-closed behavior.
6. **Complete-video acceptance.** The full shadow MP4 must receive two consecutive SHIP verdicts with no auto-fails.
7. **Repair adoption.** Feed bridge candidates through the existing blind, bounded, keep-best repair path. A worse cut never replaces the incumbent.
8. **Controlled holdout.** Use frozen/private operation before any public release.

## Non-negotiable rollback rule

Every phase is its own commit. Revert that phase immediately if its acceptance gate fails. Never repair a failed gate by weakening the showrunner or enabling publishing.

## Exact files

The machine-readable patch order, symbols, commands, acceptance checks, and rollback steps are in `claude_launch_manifest.json`.

## What 100% means here

The isolated implementation, migration rehearsal, and Claude handoff are complete. It does **not** claim that production wiring, a real production MP4, or public-channel performance have already happened.
