# Operating doctrine — how changes to this channel are made and proven

Distilled from the PR #174 review-lab playbook (the parts worth keeping) and
the practices already enforced in-tree. This is doctrine, not aspiration:
sessions working on this repo follow it.

## Sacred safeguards (never trade these for a passing result)

1. **Publishing stays frozen** until separately authorized
   (`PUBLISH_ENABLED=1` / `--publish`; see docs/EDITORIAL_RESET.md).
2. **The showrunner's BLOCK is sovereign.** It can never be averaged, routed,
   retried, or "repaired" into SHIP by code. Code only ever ADDS blocks.
3. `WEIGHTS`, auto-fail checks, `MIN_SCORE`, `decide_verdict`, and fail-closed
   behavior are **not tuning knobs**. Never weaken the judge to cross a bar.
4. Posted logs, uploader idempotency, token routing, expected-channel guards,
   workflow permissions, and production state are **sacred**.
5. Baseline/shadow comparisons must use identical slug, data, narration, and
   metric definitions — otherwise refuse the comparison.
6. One bounded phase per commit, each with acceptance checks, stop conditions,
   and a rollback path.
7. Channel identity and editorial doctrine remain channel-owned.

## Evidence hierarchy (strongest → weakest)

1. Mature real-channel outcomes (views/reactions with compatible metrics)
2. Complete production-format video, reviewed by the unchanged showrunner
3. Matched baseline-vs-shadow full-video comparison
4. Deterministic integration rehearsal (scene-level metrics, benchmark suite)
5. Isolated unit/property tests
6. Synthetic fixture demonstrations
7. Design documents / heuristic scores

**Levels 4–7 are never audience proof.** A "test suite passes" claim states its
level. Structural benchmarks certify programmed intent; only the visual
benchmark + showrunner certify what a viewer sees; only the channel certifies
what an audience feels.

## Acceptance record (required for every quality-affecting phase)

Report each phase with exactly:

- **Completed** — only fully implemented AND validated items
- **Partially completed** — coded but not fully wired, rendered, or proven
- **Not completed** — still missing
- **Tests run** — exact commands and results
- **Full renders run** — stories, run IDs, artifact locations
- **Before / after** — scores, failures, temporal metrics
- **Regressions** — anything that got worse
- **Next phase** — the next bounded target

"Complete" requires the phase's acceptance criteria to have actually passed.
A high average never cancels a hard failure.

## Failure responses

- **Contract drift** (target file changed since a plan was made): stop, remap,
  re-plan. Never apply a stale blueprint.
- **Judge blocked / no verdict**: the artifact holds. The baseline stays
  canonical. Do not re-roll until it happens to pass — repair the scene.
- **A repair loses**: the incumbent stays promoted (transactional rollback in
  `scripts/repair_loop.py`); the losing attempt is preserved for diagnosis.
- **Publishing escape**: stop everything, disable, reconcile upload state.

## Reference shelf

PR #174 (`agent/claude-roadmap-review`) is a review-only idea library — kept
draft and unmerged permanently. Vetted-useful lanes if their need arises:
subscription-fallback posting (approved queue + idempotent reservations) and
premise-lint heuristics. Known-bad: its parallel renderer/mascot, synthetic
"MP4 proof", and the professional-media-os layer (contains never-executed
code). Nothing from it gets wired without passing this doctrine's evidence
bars in the real pipeline.
