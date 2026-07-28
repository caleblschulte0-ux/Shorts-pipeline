# Ready-to-paste prompt for Claude

You are taking over draft PR #174 in `caleblschulte0-ux/Shorts-pipeline`.

Your job is **not** to merge the PR or wire every prototype into production. Your job is to understand the review-only systems, select one explicit adoption goal, and execute only the next bounded phase on a separate Claude branch with publishing frozen.

## Read first

1. `review_prototypes/claude_master_handoff/PLAYBOOK.md`
2. `review_prototypes/claude_master_handoff/fixtures/master_handoff_manifest.json`
3. `review_prototypes/launch_closure/fixtures/CLAUDE_LAUNCH.md`
4. `review_prototypes/launch_closure/fixtures/claude_launch_manifest.json`
5. `review_prototypes/professional_media_os/ADOPTION_MANIFEST.json`
6. `docs/future/CLAUDE_PROFESSIONAL_MEDIA_OS_ADOPTION.md`

## Run before changing code

```bash
git status --short --branch
python -m review_prototypes.claude_master_handoff.cli summary
python -m review_prototypes.claude_master_handoff.cli validate --repo .
python -m unittest -v review_prototypes.claude_master_handoff.test_master_handoff
python -m unittest -v review_prototypes.integration_bridge.test_integration_bridge
python -m unittest -v review_prototypes.launch_closure.test_launch_closure
python -m review_prototypes.launch_closure.cli --out /tmp/shorts-launch-rehearsal
```

Run the selected lane's own tests too. In particular, the Professional Media OS, Capability Studio, and subscription fallback suites must be executed before any code from those packages is adopted; their presence in the PR is not production proof.

## Non-negotiable rules

- Keep PR #174 draft and unmerged.
- Do not change `main`.
- Do not touch publishing workflows, uploader authority, OAuth/token selection, expected-channel guards, posted logs, or production secrets.
- Do not weaken the showrunner. Never change `WEIGHTS`, `AUTOFAIL_CHECKS`, `MIN_SCORE`, `decide_verdict`, or fail-closed publish behavior to make a video pass.
- A showrunner BLOCK remains BLOCK.
- Use the same slug, evidence, source data, narration, and metric definitions for baseline/shadow comparisons.
- Every phase is one commit with explicit acceptance and rollback.
- Stop immediately on contract drift, missing evidence, regression, reviewer disagreement, or any accidental publishing enablement.
- Unknown is not zero. Synthetic or heuristic results are not audience proof.
- Channel identity remains channel-owned.

## Choose exactly one goal

- Improve current video quality now: follow the launch-closure production migration lane.
- Make posting independent from live Claude/API availability: use the subscription fallback lane.
- Add free research/media/audio/video capabilities: use Capability Studio, one provider at a time.
- Build institutional learning and content intelligence: adopt Professional Media OS records and lineage first; do not grant ranking authority.
- Improve premise/source quality: adapt the content system only after mapping its target production contract.

State the selected goal, selected phase, files you expect to touch, acceptance checks, stop conditions, and rollback before writing code.

## Default next action

Unless a human specifies another goal, begin with the **current-video-quality lane**:

1. Rerun contract and launch preflight.
2. Map the current live symbols again.
3. Implement optional metadata contracts only.
4. Prove production artifact identity with the feature disabled.
5. Produce matched complete baseline/shadow MP4s with publishing frozen.
6. Require two consecutive sovereign showrunner SHIP verdicts with no auto-fails.
7. Adopt structural repair candidates only through the existing bounded keep-best system.
8. Run a frozen/private holdout and prove exact restoration.

Do not proceed to a later authority stage just because the prototype already contains classes for it.
