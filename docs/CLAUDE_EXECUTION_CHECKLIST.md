# Claude Execution Checklist — Curiosity Continuation

Documentation-only handoff. No runtime behavior is changed by this file.

Base reviewed: PR #172, head `f6419ad574e140bcdd0a052f89b89304b3503e44`.

Use `docs/CLAUDE_CONTINUATION_PLAYBOOK.md` for the full requirements.

## Work order

- [ ] Reconcile PR #172 with current `main` and rerun every check on the exact merge SHA.
- [ ] Prove scheduled runs, `--force`, defaults, and auto-merge cannot enable publishing.
- [ ] Add a cryptographic package manifest and bind every report/verdict to the exact video and story hashes.
- [ ] Add tamper negative controls: changed video, story, facts, thumbnail, captions, or copied verdict must quarantine.
- [ ] Replace opt-in provenance with mandatory factual modes.
- [ ] Expand claim coverage beyond numeric regexes to superlatives, comparisons, dates, causal, geographic, historical, scientific, and attributed claims.
- [ ] Automate technical and editorial visual review from a blind evidence package.
- [ ] Bind judge verdicts to manifest/video hashes and record judge version.
- [ ] Add second-judge handling for borderline scores and quarantine disagreement.
- [ ] Add draft, review, and production render profiles.
- [ ] Add deterministic shot caching and selective rerender for one-beat repairs.
- [ ] Fix `money-goes`: Japanese gas-station media, degraded bills fallback, repeated chapter cards, real-media cluster, weaker hook, and personality.
- [ ] Raise `money-goes` to at least 7.5/10 overall and 4/5 personality without lowering thresholds.
- [ ] Add comparative media candidate ranking with geography, signage, era, currency, licensing, duplication, and relevance checks.
- [ ] Upgrade repair logic to use defect-specific evidence and before/after proof.
- [ ] Add a story-status manifest; scheduler may select only `production_candidate`.
- [ ] Complete or re-author `kola-deepest-hole`, `sitting-still-speed`, and `hurricane-engine`.
- [ ] Prove at least three distinct stories pass facts, render, manifest, visual review, fallbacks, performance, and package gates.
- [ ] Add cross-video repetition tracking over at least ten videos.
- [ ] Run one owner-approved, hash-verified public canary, then disable publishing again.
- [ ] Complete three scheduled HOLD simulations before any autonomous publishing.
- [ ] Add automatic freeze conditions for artifact mismatch, wrong channel, invalid verdict, facts failure, media outage, performance violation, repeated quarantine, or upload verification failure.
- [ ] Build the shot-level learning loop only after multi-story stability is demonstrated.

## Required evidence for every implementation PR

- [ ] Problem and root cause.
- [ ] Exact files changed.
- [ ] Tests and exit codes.
- [ ] GitHub workflow run on the exact head SHA.
- [ ] Negative controls.
- [ ] Rendered artifacts where applicable.
- [ ] Before/after visual evidence where applicable.
- [ ] Rollback plan.
- [ ] Remaining risks.
- [ ] Definition of done.

## Never do

- [ ] Never enable scheduled publishing during development.
- [ ] Never weaken a gate to make a story pass.
- [ ] Never silently fall back to legacy.
- [ ] Never use generic cards as a blanket media-failure solution.
- [ ] Never trust mtime as final artifact identity.
- [ ] Never commit large rendered videos to Git.
- [ ] Never call one passing story proof of catalog readiness.
- [ ] Never create another giant mixed implementation PR.
- [ ] Never claim completion without exact artifacts and workflow evidence.

## Final acceptance

- [ ] Exact merge SHAs green.
- [ ] Publishing disabled by default.
- [ ] Hash-bound manifests and verdicts.
- [ ] Mandatory factual modes and semantic claim coverage.
- [ ] Autonomous blind technical/editorial review.
- [ ] Draft/review/production profiles and shot cache.
- [ ] Flagship at least 7.5/10 and personality at least 4/5.
- [ ] Three distinct production candidates pass end to end.
- [ ] One verified public canary succeeds and publishing is refrozen.
- [ ] Three scheduled HOLD simulations succeed.
- [ ] Learning system uses real multi-video evidence without changing doctrine from one result.