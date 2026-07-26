# Isolated Channel Build Sprint 3

This sprint implements the remaining major safety and proof gaps as executable review-only code. No production module imports these packages.

## `sandbox_adapters/`

- enforces a sandbox root for every input, output, and working directory;
- uses an explicit executable allow-list;
- executes argument arrays directly with `shell=False`;
- forces `PUBLISH_ENABLED=0` in every child process;
- records renderer and judge requests plus execution evidence;
- fails when required render or verdict artifacts are missing.

## `full_video_proof/`

- models complete-video story evidence and immutable suite-run proof;
- requires video/verdict hashes and proof that the vision judge watched the video;
- locks suite, judge, and renderer versions across consecutive runs;
- implements phase 1, phase 2, and phase 3 acceptance thresholds;
- blocks a batch when even one benchmark story collapses;
- stores proof append-only with tamper detection.

## `observability/`

- writes append-only, hash-chained JSONL events;
- detects edits, broken sequence numbers, and broken chain links;
- classifies incidents by severity and retryability;
- stores failed work in an idempotent dead-letter queue;
- builds reproducible run summaries from evidence rather than console prose.

## `release_safety/`

- validates release identity, source proof, readiness evidence, and hard-failure status;
- records immutable release manifests;
- verifies manifests before canonical promotion;
- quarantines suspect releases;
- rolls back only to a verified earlier release;
- fails closed when no safe rollback target exists.

## `sprint3_lab/`

- composes full-video proof, audit logging, and release promotion;
- proves a strong release candidate is still blocked when the suite proof fails;
- proves a passing two-run phase gate can promote a verified release in isolation.

## Verification

Run from repository root:

```bash
python -m unittest discover -s review_prototypes -p 'test_*.py' -v
```

Safety remains unchanged:

- existing production files modified: 0
- workflows modified: 0
- publishing calls added: 0
- production imports added: 0
