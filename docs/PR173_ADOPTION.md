# PR #173 Adoption Record

**Date:** 2026-07-28
**Source:** PR #173 (`agent/curiosity-continuation-handoff`) — the dormant
autonomous reference surface (77 modules, 425 contracts) built off to the side
by the owner + ChatGPT, deliberately isolated from production.
**Rule followed:** never import the package wholesale; adapt each good idea
into the REAL pipeline shapes as a focused commit with tests and negative
controls. Story identity never selects behavior.

## Dormant suite status

Executed and repaired on the PR #173 branch itself (commit `3f490d3`):
`python -m unittest discover experiments/curiosity_nextgen/tests` →
**Ran 425 tests, OK**. Six authored-never-run drifts reconciled without
weakening any contract (each documented in that commit message). The
reference surface is now VERIFIED, not just authored.

## Adopted into production (feature/curiosity-pro-integration)

| Reference idea | Production adaptation | Proof |
|---|---|---|
| `artifact_manifest.py` — content-addressed package identity (their PR A) | `scripts/artifact_identity.py`: every successful render hashes video/story/facts/captions/thumbnail/meta/fallbacks into `pkg/manifest.json` (self-hashed); `verify_manifest()` recomputes and names what changed. Verdicts now carry the sha256 of the exact mp4 they judged; `produce.evaluate` refuses mismatched OR unbound verdicts (old mtime rule kept as belt-and-braces) | `test_artifact_identity.py` 8/8 negative controls: video swap after judgment, copied verdict, unbound verdict, story edit, caption swap, hand-edited manifest — all detected |
| `execution_ledger.py` — durable ledger, idempotency (their PR D) | `scripts/run_ledger.py`: hash-chained append-only `state/curiosity_run_ledger.jsonl` of every producer phase; `--verify` names the first edited link. **Resume:** produce skips the hour-long re-render when the manifest re-verifies exactly (never mtimes) and a director rc is recorded; `--fresh` overrides. Cure for the two container-death re-renders of 2026-07-25 | `test_run_ledger.py` 5/5: tamper detection at exact seq; renderer-tripwire proof that identical packages resume and any change (or `--fresh`) re-renders |
| `media_ranker.py` context fields + `repetition_ledger.py` + `circuit_breaker.py` | `data_learning/media_context.py`: opt-in story `media_context` {geography, language, exclude_terms} filters candidates by metadata (foreign-script titles, wrong-country geo tells, excluded terms); cross-video reuse ledger penalizes assets other videos already shipped (0.7/0.45 — penalty, not ban); per-provider breaker opens after 3 consecutive failures. Wired into `best_image`/`motion_first`/`find`; flagship declares geography=US | `test_media_context.py` 6/6 incl. the literal Japanese-gas-station-sign case the blind judge found at ~116s |
| `approval_token.py` + lifecycle kill switch | `scripts/approve_publish.py`: owner approval BOUND to the package-manifest hash — a re-render/artifact swap/manifest edit makes it inert; quarantined films are unapprovable. Kill switch: `state/curiosity_kill_switch` existing halts ALL uploads, outranking every flag and `--force`. Publish order: gates → publish-enabled → kill switch → approval → upload | `test_publish_guards.py` 6/6 incl. approval-reuse-on-different-cut refused |
| Truth-label vocabulary (authored / executed / integrated / launched) | Adopted in this document and in how status is reported going forward | — |

All four adoption commits ride the standard CI (new Layer 2b) and are pushed.

## Deliberately NOT adopted (stays in the box, with reasons)

- **Autonomous batch controller / autonomous program / simulator / batch
  acceptance / idea funnel / portfolio optimizer / story intake** — premature
  before ONE public canary succeeds and ≥3 stories pass taste. The channel's
  binding constraint is content quality, not orchestration scale. Verified in
  the box, ready when the catalog exists.
- **`judge_orchestrator` / `semantic_claims` / `claim_registry`** — production
  already has working equivalents (`judge_verdict.py`, `facts_gate.py`,
  the blind-judge protocol) proven on real renders. Adopting the twins would
  create two competing implementations of the same gates. Future work should
  EXTEND the production gates with the reference's ideas (semantic non-numeric
  claims is the good one), not swap them.
- **`provider_pool` (full routing: quota/latency/cost/judge-independence)** —
  we have ~3 keyless providers; the breaker captures the current value. Worth
  revisiting when paid providers (Pexels/Pixabay/Apify keys) are live.
- **`security_scanner`, `migration_planner`, `schema_registry`,
  `policy_snapshot`, `audit_chain`, `observability`, `drift` machinery** — no
  current consumer in a single-worker pipeline; would be dead code in
  production. The run ledger + manifest self-hash cover today's tamper-evidence
  need.
- **`controlled_learning_loop`** — the reference's own rule: only after stable
  shadow operation. Nothing to learn from yet.
- **Creative-layer modules (hooks/pacing/choreography/captions/etc.)** — the
  production director loop + taste judge already enforce these dimensions on
  RENDERED PIXELS, which is stronger than metadata-level checks. The
  reference's per-dimension vocabularies are good authoring checklists; no
  code adopted.

## Follow-ups this unlocks

1. First real render on this branch writes the first manifest → resume + the
   approval flow become live for Canary 5 (`approve_publish.py money-goes`
   after the owner watches the cut; `CURIOSITY_PUBLISH_ENABLED=1` still
   required; kill-switch file as the abort lever).
2. When stock API keys land, revisit provider_pool-style routing.
3. Extend facts_gate with semantic (non-numeric) claim coverage from the
   reference's `semantic_claims.py` vocabulary.
