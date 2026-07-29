# PR #173 Adoption Record

**Date:** 2026-07-28 (initial adoptions) · 2026-07-29 (FULL adoption)
**Source:** PR #173 (`agent/curiosity-continuation-handoff`) — the dormant
autonomous reference surface (77 modules, 425 contracts) built off to the side
by the owner + ChatGPT, deliberately isolated from production.
**Rule followed:** never import the package wholesale as bespoke logic; adapt
each idea into the REAL pipeline shapes as a focused commit with tests and
negative controls. Story identity never selects behavior.

**Owner ruling 2026-07-29:** adopt EVERYTHING, including the pieces the first
pass boxed as premature ("I love redundancy"). This record now reflects the
full adoption; the earlier "stays in the box" section is preserved at the
bottom as history, with what changed.

## Dormant suite status

Executed and repaired on the PR #173 branch itself (commit `3f490d3`):
`python -m unittest discover experiments/curiosity_nextgen/tests` →
**Ran 425 tests, OK**. Six authored-never-run drifts reconciled without
weakening any contract. The whole verified surface was then merged into
production (`experiments/curiosity_nextgen/`, commit `e61182e`+`89bac09`) and
its full 425-contract suite runs in CI (Layer 2c) on every push.

## Wave 1 adoptions (2026-07-28)

| Reference idea | Production adaptation | Proof |
|---|---|---|
| `artifact_manifest.py` — content-addressed package identity | `scripts/artifact_identity.py`: every successful render hashes video/story/facts/captions/thumbnail/meta/fallbacks into `pkg/manifest.json` (self-hashed); verdicts carry the sha256 of the exact mp4 they judged; `produce.evaluate` refuses mismatched OR unbound verdicts | `test_artifact_identity.py` 8/8 negative controls |
| `execution_ledger.py` — durable ledger, idempotency | `scripts/run_ledger.py`: hash-chained append-only `state/curiosity_run_ledger.jsonl`; manifest-proven render RESUME (never mtimes); `--fresh` overrides | `test_run_ledger.py` 5/5 |
| `media_ranker.py` context + `repetition_ledger.py` + `circuit_breaker.py` | `data_learning/media_context.py`: geography/language/exclude-terms filtering, cross-video reuse penalties, per-provider breaker; wired into `best_image`/`motion_first`/`find` | `test_media_context.py` 6/6 |
| `approval_token.py` + lifecycle kill switch | `scripts/approve_publish.py`: owner approval BOUND to the manifest hash; kill-switch file halts all uploads above every flag | `test_publish_guards.py` 6/6 |
| Truth-label vocabulary (authored/executed/integrated/launched) | Used in all status reporting | — |

## Wave 2 — FULL adoption (2026-07-29)

| Reference cluster | Production adaptation | Proof |
|---|---|---|
| `portfolio_optimizer` + `idea_funnel` + `autonomous_batch_controller` + `batch_acceptance` + `autonomous_decision_engine` | `scripts/batch_produce.py`: `--plan` admits from the REAL catalog on mechanical readiness only; `--ideas` scores raw ideas through the funnel; `--run` drives the canonical producer story-by-story under count+wall-clock budgets with per-story decisions; `--status` maps real on-disk evidence (produce reports, verdicts, manifests, facts reports) into batch acceptance, reporting today's reachable floor AND the strict 50-story launch policy side by side. Publishing untouched | `test_batch_produce.py` 5/5 |
| `cognitive_load` + `retention_risk` | `scripts/story_advisor.py`: authoring-time advisory over real beats — per-beat load (speech density, concept/number stacking), retention risk (early-exit windows, static holds, repeated families), unanswered-hook heuristic. Mechanical proxies only, documented; never blocks (pixels outrank metadata) | `test_story_advisor.py` 4/4; discriminates on the real catalog (money-goes best early-exit risk, sitting-still worst) |
| `security_scanner` | `scripts/publish_security.py` wired into `post_curiosity` before ANY upload: the exact outbound payload (title/description/tags/localizations/captions/whole meta sidecar) is scanned; secrets/bearer tokens/private keys/credential fields/internal-instruction fields BLOCK, scanner errors also block (nothing ships unscanned), `--force` cannot bypass. Report → `output/curiosity_<slug>.security.json` | `test_publish_security.py` 6/6 |
| `semantic_claims` + `claim_registry` | EXTENDED `scripts/facts_gate.py` (no competing twin): sentence-level detection of historical/superlative/comparative/causal/scientific/attributed claims across every beat, audited against the same registry (claims may declare `claim_type`; inline `facts[]` covers its beat). Advisory by default; `require_semantic_provenance: true` makes uncovered semantic claims hard blocks, failing closed on audit crash | `test_facts_gate.py` 16/16; flagship 9/9 signals covered |
| `provider_pool` | `data_learning/provider_routing.py`: the real providers become live `ProviderRecord`s (health = key present + circuit closed; error rate from breaker counts), ranked by the reference fitness function with family-independent fallbacks. `media.find()` consults `maybe_route()` for image-provider order; abstains (None) on any error so it can only steer away from dead providers, never break acquisition | `test_provider_routing.py` 6/6 |
| `observability` + `pipeline_status` | `scripts/pipeline_health.py`: verifies the run-ledger hash chain, maps rows into runs with pass/quarantine/failure rates + refusal reasons; honest capability table where evidence level discounts readiness (the publish path stays capped at `tested` until a real gated upload exists) → `output/pipeline_status.json` | `test_pipeline_health.py` 5/5 incl. tamper surfacing |
| `autonomous_simulator` + `fault_injection` semantics | `scripts/simulate_pipeline.py` (CI Layer 2e): deterministic 50-story drill over the real stage sequence under a fault campaign — transient retries complete, repairables consume the repair budget, one factual fault REWINDS to research, persistent factual faults quarantine, missing evidence HOLDS and invalidates the batch, fatal quarantines, bit-for-bit deterministic. `publish` excluded from the drill on purpose | exit-code gated in CI; report → `output/simulation_report.json` |
| `controlled_learning_loop` | `scripts/learning_proposals.py`: the only sanctioned analytics→policy path. Guardrailed proposals (impressions/story floors, real watch+completion lift, no negative-feedback regression, bounded parameter deltas), sha256-bound to their evidence, canary-gated (`--canary --passed-batches N --rollback-ready`), ledgered, and NEVER self-applying — applying stays a human commit | `test_learning_proposals.py` 6/6 |

CI now runs: Layer 2b (wave-1 suites), 2c (all 425 nextgen contracts),
2d (all wave-2 adapter suites), 2e (the 50-story drill).

## Not adapted as separate code (with reasons — nothing remains unadopted)

- **`judge_orchestrator` / `judge_contract` / `judge_evidence`** — production's
  `judge_verdict.py` + blind-judge protocol is the SAME design already proven
  on real renders; a second implementation would compete with it. The library
  modules are merged, tested in CI, and available.
- **Creative-layer modules (hooks/pacing/choreography/captions/visual
  grammar/etc.)** — the render-time director + taste judge enforce these on
  RENDERED PIXELS, which outranks metadata checks. Their authoring-time value
  is delivered through `story_advisor.py`; the rest of the vocabulary is
  merged and importable as checklists.
- **`migration_planner`, `schema_registry`, `replay_engine`, `shot_cache`,
  `freeze_controller`, etc.** — merged, contract-tested in CI every push, and
  callable; no production call site exists yet because nothing in the current
  single-worker pipeline consumes them. First consumer can wire them without
  re-verification.

## Standing invariants (unchanged by full adoption)

- Publishing stays disabled by default (`CURIOSITY_PUBLISH_ENABLED=1` +
  manifest-bound approval + kill switch + security scan; `--force` is
  dedup/scheduling only).
- Every layer fails closed; advisory layers may warn but never crash a gate.
- Story slugs are opaque — no behavior selects on identity.
- No rendered media in git; reports/ledgers are small JSON.

## Historical note — the 2026-07-28 "stays in the box" list

Wave 1 deliberately deferred the batch/autonomy, security, provider-routing,
observability, simulator, and learning clusters as premature for a channel
whose binding constraint was content quality. The owner overruled on
2026-07-29 ("adopt anything good, I love redundancy — don't come back until
it's all added"), and wave 2 adapted every one of them against real pipeline
data with tests, keeping all standing invariants.
