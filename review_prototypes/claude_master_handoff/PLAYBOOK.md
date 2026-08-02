# Claude master playbook — Shorts Pipeline review lab

## 1. Mission

Draft PR #174 is a large **review-only implementation and design laboratory**. Its purpose is to give Claude tested algorithms, contracts, render ideas, safety systems, migration rehearsals, and adoption roadmaps without changing the live Shorts pipeline.

The correct next move is not “merge the PR.” The correct move is:

1. understand the available systems;
2. choose one explicit operational goal;
3. select the earliest unfinished phase for that goal;
4. remap the current production contract;
5. port one bounded slice on a separate Claude branch;
6. prove equivalence or improvement with publishing frozen;
7. stop, restore, or proceed based on explicit gates.

## 2. Absolute scope boundary

The review branch is not production. Prototype maturity must never be confused with deployed capability.

### Sacred rules

1. Publishing stays frozen until separately authorized.
2. The sovereign showrunner retains veto authority.
3. A BLOCK can never be averaged, routed, or repaired into SHIP by bridge code.
4. `WEIGHTS`, `AUTOFAIL_CHECKS`, `MIN_SCORE`, `decide_verdict`, and fail-closed publishing are not tuning knobs.
5. Posted logs, uploader idempotency, OAuth/token routing, expected-channel guards, workflow permissions, and production state are sacred.
6. Baseline and shadow comparisons use identical slug, source evidence, data, narration, and metric definitions.
7. Every production adoption phase is a separate commit with acceptance, stop, and rollback rules.
8. Unknown evidence remains unknown. Synthetic and heuristic evidence is not audience proof.
9. Channel doctrine and identity remain channel-owned.
10. The draft PR remains draft until a human explicitly changes it.

## 3. Current truth

### Explicitly recorded passing suites

- isolated completion closure: 25/25;
- viewer-facing render lab: 31/31;
- perceptual polish: 30/30;
- global continuity: 29/29;
- production-shaped integration bridge: 39/39;
- launch closure: 54/54;
- master handoff: 29/29.

That is **237 recorded passing tests across seven distinct handoff-critical suites**.

### Declared but not treated as verified here

The Professional Media OS manifest declares 25 tests but explicitly records that they were not executed in the connector environment. Capability Studio and subscription fallback also have isolated suites that Claude must run before adoption. Never convert “files exist” into “verified.”

### Still unclaimed

- production wiring: 0%;
- complete production MP4 using adopted integration: 0%;
- real channel performance proof: 0%.

The honest complete-system score remains 79.5%. The review/handoff scope is 100%.

## 4. First session: exact order

Run these before changing code:

```bash
git status --short --branch
cat review_prototypes/claude_master_handoff/PLAYBOOK.md
python -m review_prototypes.claude_master_handoff.cli summary
python -m review_prototypes.claude_master_handoff.cli validate --repo .
python -m unittest -v review_prototypes.claude_master_handoff.test_master_handoff
python -m unittest -v review_prototypes.integration_bridge.test_integration_bridge
python -m unittest -v review_prototypes.launch_closure.test_launch_closure
python -m review_prototypes.launch_closure.cli --out /tmp/shorts-launch-rehearsal
```

Stop if:

- the handoff validator finds a missing path or unsafe command;
- a frozen production symbol or SHA has drifted;
- a critical suite fails;
- the branch is no longer the expected review branch;
- publishing is enabled;
- the requested goal is ambiguous.

After preflight, state in writing:

- selected goal;
- selected phase;
- expected production files;
- authority ceiling;
- acceptance checks;
- stop conditions;
- rollback action.

## 5. Choose the correct lane

### Goal A — improve current videos visibly

Use:

- `visible_quality/render_lab` for effect mechanics;
- `visible_quality/polish_lab` for typography, sound, and archetype fit;
- `visible_quality/continuity_lab` for full-video motion, rhythm, and transitions;
- `integration_bridge` for production-shaped metadata and patch blueprints;
- `launch_closure` for MP4 rehearsal, reviewer replay, and restoration.

Execution path:

```text
orientation
  -> critical preflight
  -> record-only metadata contracts
  -> shadow bridge
  -> preview-only renderer
  -> sovereign complete-video review
  -> bounded keep-best repair
  -> frozen/private holdout
```

This is the default next lane when the goal is simply “make the channel better.”

### Goal B — improve premises, evidence, and story selection

Use:

- `content_system/source_registry.py`;
- `content_system/premise_engine.py`;
- `content_system/story_compiler.py`;
- `content_system/content_queue.py`;
- `retention_system`;
- `channel_operations`.

Do not import these directly into production. First map the live authoring and queue contracts. Begin with record-only premise/evidence diagnostics. Preserve source truth and fail closed on unsupported claims.

### Goal C — make posting independent from live Claude/API availability

Use `review_prototypes/subscription_fallback/`.

The intended architecture is:

- an approved ready-to-post queue exists before provider failure;
- provider health affects generation, not upload correctness;
- deterministic degradation never promotes unapproved content;
- upload idempotency prevents duplicate posts;
- replay/resume reconciles existing upload reservations before starting another upload;
- publishing does not depend on same-day AI generation.

Run:

```bash
python -m unittest review_prototypes.subscription_fallback.test_subscription_fallback
cat review_prototypes/subscription_fallback/ADOPTION_MANIFEST.json
```

Adopt only one bounded slice at a time. Do not modify posted logs or uploader authority in the first phase.

### Goal D — add free research, media, audio, graphics, browser, or video capability

Use `review_prototypes/capability_studio/` and the related future docs.

Run all three suites first:

```bash
python -m unittest review_prototypes.capability_studio.test_capability_studio
python -m unittest review_prototypes.capability_studio.test_free_capabilities
python -m unittest review_prototypes.capability_studio.test_toolchain_adoption
```

Then inspect:

- `ADOPTION_MANIFEST.json`;
- `CLAUDE_ADOPTION_MANIFEST.json`;
- `toolchain_catalog.py`;
- `toolchain_executor.py`;
- `diagnostics.py`;
- provider and free-capability modules.

Adopt one capability at a time. Require suitability, licensing, deterministic fallback, resource ceilings, and a kill switch. Do not adopt a tool merely because it is free.

### Goal E — build institutional learning and professional content intelligence

Use `review_prototypes/professional_media_os/`.

Its classes are reference contracts, not a calibrated production brain. Adoption order:

1. stable identifiers and immutable record contracts;
2. record-only content genomes and evidence references;
3. physically separate shadow capture;
4. append-only observation/decision history;
5. exact artifact, metric, and decision lineage;
6. representative historical benchmark corpus;
7. shadow candidate laboratory;
8. evaluator calibration with false rejection separated from false approval;
9. rough-cut selection only;
10. bounded canary;
11. versioned pattern adoption;
12. operator and portfolio authority only after mature evidence.

Run:

```bash
python -m unittest \
  review_prototypes.professional_media_os.test_professional_media_os \
  review_prototypes.professional_media_os.test_lineage \
  review_prototypes.professional_media_os.test_patterns_version
python -m review_prototypes.professional_media_os.cli demo
cat review_prototypes/professional_media_os/ADOPTION_MANIFEST.json
```

The prototype file ledger is single-writer and must not be copied blindly into a concurrent production runtime.

## 6. System map

### Safety and transactional foundation

- `attempt_store.py` — immutable attempt storage and atomic promotion.
- `quality_contracts.py` — quality/evidence contracts.
- `implementation/` — isolated runtime, adapters, manifests, and repository semantics.
- `next_level/` — semantic planner, judge ensemble, state machine, and benchmark orchestration.

### Content and learning

- `content_system/` — evidence, premises, claims, story compilation, and queue diversity.
- `channel_analytics/` — observations, guarded experiments, and performance patterns.
- `retention_system/` — hook, pacing, repetition, and payoff controls.
- `channel_operations/` — readiness, portfolio, scheduling, and experiment enforcement.

### Viewer-facing quality

- `visible_quality/director.py` — visual event direction.
- `visible_quality/render_lab/` — deterministic effects and SVG previews.
- `visible_quality/polish_lab/` — captions, sound, archetypes, tension, and transitions.
- `visible_quality/continuity_lab/` — global motion, occupancy, rhythm, and audio alignment.

### Proof, observability, and safe release

- `sandbox_adapters/` — forced publishing freeze and contained execution.
- `full_video_proof/` — complete-video acceptance and immutable evidence.
- `observability/` — hash-chained event log, incidents, and summaries.
- `release_safety/` — quarantine, canonical promotion, tamper refusal, and restoration.
- `completion_lab/` — deterministic end-to-end closure and fault injection.

### Production migration

- `integration_bridge/` — current production-shaped Story adapter, non-mutating application, manifest bridge, contract probe, and verdict routing.
- `launch_closure/` — matched MP4 rehearsal, two-pass reviewer checks, restoration drills, seven patch targets, and five core migration phases.

### Expansion and independence

- `capability_studio/` — provider and free-tool capability references.
- `subscription_fallback/` — approved queue, degradation, provider routing, and upload idempotency.
- `professional_media_os/` — institutional memory, lineage, candidate lab, patterns, governance, operator, and portfolio.

### Evidence and status

- `system_scorecard/` — evidence-weighted status snapshots.
- `claude_master_handoff/` — canonical map, validator, risk register, and execution playbook.

## 7. Production patch map for the current-video-quality lane

The launch manifest defines seven ordered targets.

### Target 1 — `data_learning/story.py`

Purpose: accept optional compiled quality metadata without changing source truth.

Symbols: `Segment`, `Story`, `build`.

Acceptance:

- existing story tests pass;
- old configs and serialized forms remain valid;
- metadata is optional;
- same input produces the same default production output.

Rollback: remove optional metadata fields.

### Target 2 — `data_learning/viz_director.py`

Purpose: consume a compiled kind only when it is renderable and preview-enabled.

Symbols: `assign`, `renderable`, `KINDS`.

Acceptance:

- fallback and novelty guarantees remain intact;
- preview flag off equals current behavior;
- unsupported kinds fail safely.

Rollback: disable preview flag and restore current assignment.

### Target 3 — `data_learning/charts.py`

Purpose: honor verified `perf_override` while preserving terminal fallbacks and attachment evidence.

Symbols: `render_story_build`, `_perf_action`, `FALLBACK`.

Acceptance:

- contact/attachment sidecar remains valid;
- cadence tests pass;
- fallback still depicts data;
- no worse performance silently replaces the incumbent.

Rollback: ignore override and use current performance routing.

### Target 4 — `data_learning/studio_render.py`

Purpose: read compiled scene, audio, and transition metadata only in preview mode.

Symbols: `render`, `_build_soundtrack`, `_plan_events`.

Acceptance:

- matched complete baseline/shadow MP4s render;
- publishing remains frozen;
- preview flag off is behaviorally identical;
- shadow artifact is complete and objectively better.

Rollback: unset preview flag.

### Target 5 — `scripts/showrunner_review.py`

Purpose: attach diagnostics only.

Symbols: `review_video`, `decide_verdict`, `AUTOFAIL_CHECKS`.

Acceptance:

- scoring and verdict rules are byte/behavior equivalent;
- two consecutive full-video reviews agree;
- no auto-fail appears.

Rollback: drop diagnostic context.

### Target 6 — `scripts/scene_repair.py`

Purpose: include bridge-generated structural candidates in blind review.

Symbols: `propose`, `score_candidate`, `VARIANTS`.

Acceptance:

- incumbent remains unless challenger wins by the existing margin;
- candidate differences are structural, not parameter jitter.

Rollback: use the current variants table only.

### Target 7 — `scripts/repair_loop.py`

Purpose: record bridge evidence while preserving bounded, monotone keep-best repair.

Symbols: `repair`, `pick_remedy`, `better`.

Acceptance:

- worse challengers never replace better cuts;
- repair budget remains bounded;
- a BLOCK remains BLOCK.

Rollback: ignore bridge evidence and keep the existing loop.

## 8. Acceptance protocol

For every phase:

1. freeze the target contract before editing;
2. write the phase objective and authority ceiling;
3. create one commit;
4. run existing production tests plus selected prototype tests;
5. produce matched evidence;
6. run the full output through the sovereign reviewer when video behavior changes;
7. compare against explicit acceptance checks;
8. either retain the commit or revert it completely;
9. append a decision record; do not rewrite history.

A phase passes only when every required check passes. A high average score cannot cancel a hard failure.

## 9. Evidence hierarchy

From strongest to weakest:

1. mature real-channel outcomes with compatible metric definitions;
2. complete production-format artifact reviewed twice;
3. matched baseline/shadow artifact comparison;
4. isolated deterministic integration rehearsal;
5. isolated unit/property/fault tests;
6. synthetic fixture demonstration;
7. design document or heuristic score.

Never describe levels 4–7 as audience proof.

## 10. Failure and rollback rules

### Contract drift

Stop. Remap the symbols and update the blueprint before coding. Do not apply an old patch against a changed contract.

### Showrunner disagreement or missing verdict

Hold the artifact. Retain the baseline. Do not rerun until it happens to pass.

### Shadow artifact loses

Keep the incumbent. Preserve the failed candidate and reason for calibration.

### Publishing escape

Stop immediately. Disable the feature, reconcile upload/posted state, and do not start another upload until the prior reservation is understood.

### Metric incompatibility

Refuse the comparison. Persist metric definition versions and recompute using eligible samples.

### Pattern or evaluator overreach

Reduce authority to shadow/reference, append a reversal, and preserve negative knowledge.

### Subscription/provider failure

Use the approved queue and deterministic degradation. Do not generate or promote unapproved emergency content merely to maintain cadence.

## 11. Troubleshooting by symptom

### “Too many systems; I do not know where to start”

Choose one goal from Section 5. Run only its earliest incomplete phase.

### “The prototypes say 100%, so can I wire them all?”

No. The 100% is review/handoff completion. Production authority remains unclaimed.

### “A reviewer blocked the video but the isolated score is high”

The reviewer wins. Fix the artifact or keep the baseline.

### “The Professional Media OS can rank candidates already”

Only synthetically. Begin with records and lineage. Ranking remains shadow-only until calibrated.

### “Claude/API quota is gone; should posting stop?”

Not necessarily. Use an approved prebuilt queue and subscription fallback. Never bypass approval or idempotency.

### “A free tool can generate something impressive”

Run suitability, license, resource, deterministic fallback, and output-quality checks before adoption.

### “The old production file changed since the blueprint”

Contract drift invalidates the blueprint. Re-probe and remap.

## 12. Required decision record for each Claude phase

Record:

- goal;
- phase ID;
- branch and commit;
- target files and symbols;
- contract snapshot;
- feature flag and default;
- authority ceiling;
- tests run;
- baseline artifact identity;
- shadow artifact identity;
- reviewer verdicts;
- acceptance result;
- rollback command;
- unresolved risks;
- next permitted phase.

## 13. Definition of done

### Review/handoff done

- all canonical files exist;
- validator passes;
- every system is cataloged;
- every adoption lane has commands, acceptance, stop, and rollback;
- verified and unverified evidence are separated;
- Claude has a ready-to-paste first-session prompt.

### Production phase done

- one bounded phase is adopted;
- default behavior remains unchanged outside the flag;
- acceptance evidence is complete;
- rollback has been exercised;
- no sacred authority changed.

### Full system done

The system is not fully adopted until it can reconstruct:

- all candidate alternatives;
- why one was selected;
- evidence and rights supporting the promise;
- evaluator, policy, and metric versions;
- complete artifact lineage;
- stage-by-stage mature outcomes;
- experiment context;
- decisions and learned patterns;
- exact restoration path.

Until then, keep unfinished layers record-only, shadow-only, or preview-only.
