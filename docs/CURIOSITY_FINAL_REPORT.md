# Curiosity Recovery — Final Report (required format)

Date: 2026-07-25. All claims below link to commits, tests, runs, and artifacts
in this repository. Written for independent inspection.

---

## A. Repository State

- **Main SHA:** `6b03641` (untouched by this work)
- **Integration branch:** `feature/curiosity-pro-integration` @ `b0b4552` + this report commit — 16 focused commits on top of main, normal merge base
- **Recovery branch (archival):** `recovery/curiosity-pro-history` @ `a0bef66` — the complete disconnected pro history, preserved; never developed on
- **Open PRs:** [#172](https://github.com/caleblschulte0-ux/Shorts-pipeline/pull/172) `feature/curiosity-pro-integration` → `main` (full evidence table in the PR body)
- **Merged PRs:** none from this work (merging is an owner decision)
- Confirmed at the start: `git merge-base origin/main a0bef66` exits 1 — the pro history was genuinely unrelated. Recovery was selective per-file; **no `--allow-unrelated-histories` merge was used**. No mp4/large binary is committed on the integration branch (the old branch's committed 80 MB mp4 was explicitly rejected).

## B. Canonical Production Path

```
scripts/post_curiosity.py:main()
  → scripts/post_curiosity.py:_render_story()          # CURIOSITY_RENDERER=pro is the default
    → scripts/produce.py:produce()                     # THE canonical producer
      → scripts/no_dull_beats.py:run()                 # director loop: render → gates → repair → re-render (≤2 rounds)
        → data_learning/pro_render.py (build)          # planner → shots → package → fallback ledger → perf report
          → data_learning/planner.py:plan_story()
          → scripts/visual_judge.py                    # blind evidence package
      → scripts/facts_gate.py:evaluate()               # provenance gate (via produce._provenance_gap)
      → scripts/produce.py:evaluate()                  # 5 gates → PASS / QUARANTINE
  → post_curiosity quality gate (producer verdict + hook_director + interest_judge on the finished mp4)
  → CURIOSITY_PUBLISH_ENABLED gate → upload (or HOLD)
```

**Proof legacy is not the default:** `grep -n longform_render scripts/post_curiosity.py` → exactly one call site, inside the explicit `CURIOSITY_RENDERER=legacy` branch. A slug with no pro story **fails closed** (quarantine with the authoring instruction) — verified by `scripts/test_routing.py` with a tripwire module proving legacy is never imported on that path.

## C. Recovered Files

All recovered from `recovery/curiosity-pro-history` (= `a0bef66`) in commit `a4c8592` (76 files). Complete per-file table with classifications: **`docs/CURIOSITY_FILE_RECONCILIATION.md`**. Summary:

- Engine: `pro_render.py`, `planner.py`, `flat2d.py`, `scenes.py`, `expression.py`, `perf_instrument.py`, `media.py`, `media_video.py`, `stock.py`, `footage_hybrid.py`, `continuity.py`, `contrast_director.py`, `extra_director.py`, `continents.py`, `showrunner.py`
- Producer + gates: `produce.py`, `no_dull_beats.py`, `visual_judge.py`, `judge_verdict.py`, `hook_director.py`, `interest_judge.py`, `cool_judge.py`, `editorial_review.py`, `render_gates.py`, `quality_gate.py`, qa_* preview lane
- Stories: `pro_stories/` (7 stories incl. flagship `money-goes` with inline `facts[]`)
- Doctrine: `DIRECTOR.md`, `TASTE_JUDGE.md`, `VISUAL_STANDARD.md`, `PRO_DOCTRINE.md` + 7 more
- Tests + CI: expression suites, perf harness, `expression-tests.yml`
- Hand-reconciled: `post_curiosity.py` (kept main's atomic log writes), `curiosity.config.json` (verified superset), `CURIOSITY_BRAIN.md`, `curiosity.yml`, `.gitignore`/`requirements.txt` (kept main's newer versions + additions), 3 curio data files

## D. Rejected Workarounds

- **The blanket title-card conversion** (commits `b0d06c5`/`b0b2dc7` in the old history): rejected; the recovered `money-goes.beats.json` carries real media beats (restored in `0bd6061`).
- Committed render artifacts (80 MB+ mp4s, preview/, samples/) — artifacts ride CI artifact storage, not git.
- The orphaned V8 legacy-renderer cluster (`world_engine.py`, `world_builders.py`, `shots.py`, `check_builders.py`, `evidence.py`, `repair.py`, `render_director.py`, `sound_design.py`) — zero importers in the recovered tree.
- The pro-side `longform_render.py` evolution — legacy's job is stability; main's proven copy kept.
- The premature "production ready" claim documents (`CURIOSITY_PRO_PRODUCTION_READY.md`, `DELIVERY_REPORT.md`) — superseded by this evidence-based report; archived on the recovery branch only.
- Unrelated-workstream files (explainer/mascot, third-channel, scout) — main authoritative; explainer frozen per Phase 0 (`docs/EXPLAINER_MASCOT_SYSTEM.md`).

## E. Test Results

All commands run from the repo root; exit codes as stated.

| Layer | Command | Result |
|---|---|---|
| Static | `python -m compileall data_learning scripts` + all-JSON validity + 12-module import closure | exit 0 |
| Unit: routing law | `python3 scripts/test_routing.py` | 4/4, exit 0 (legacy-tripwire fail-closed proof) |
| Unit: verdict contract | `python3 scripts/test_judge_verdict.py` | 14/14, exit 0 |
| Unit: producer decisions | `python3 scripts/test_produce_evaluate.py` | 8/8, exit 0 (stale verdict, unacceptable fallback, missing sidecars, facts fail-closed…) |
| Unit: facts gate | `python3 scripts/test_facts_gate.py` | 12/12, exit 0 |
| Unit: perf instrumentation | `python3 scripts/test_perf_instrument.py` | pass, exit 0 |
| Unit: expression gates | `python3 scripts/verify_expression_gates.py` | pass, exit 0 |
| Scene | `python3 scripts/test_expressions.py` | 6/6 scenes, exit 0 |
| Scene (measured) | `python3 scripts/verify_expressions.py` | ALL VISIBLY DIFFERENT (1.7k–5.6k px peaks vs 600 threshold), exit 0 |
| Producer smoke | `python3 scripts/producer_smoke.py` | SMOKE PASS, exit 0 — all-card fixture rendered, director REJECTED it (rc=4, cards 100%), fail-closed held, package+perf+ledger present |
| Full canary | `python3 scripts/produce.py money-goes output/curiosity_money-goes.mp4` | exit 5 → **director CLEAN (rc=0)**, quarantined only pending the blind verdict (correct headless behavior); after judging: **PASS** |
| Render gates | `python3 scripts/render_gates.py output/curiosity_money-goes.mp4` | **4/4 PASS** |
| Facts gate (live) | `python3 scripts/facts_gate.py money-goes` | PASS, exit 0 — 7/7 claims, 16/16 numeric beats covered |
| Dry-run publish sim | `post_curiosity --dry-run --slugs money-goes` (existing green artifacts) | exit 0 — `publish_eligible: true, blocking_reasons: []`, HELD |
| CI (GitHub runners) | `curiosity-ci.yml` gates job | **success** on `87c805e`, `bf4ff13`, `923b9f7` (push + PR); final-SHA run noted in PR checks |

## F. Performance Results

From the final green render's `performance.json` (idle container, canonical path):

- **Full render duration:** 1906 s wall for 242 s of video (50 shots)
- **Median shot time:** 8.7 s (median local cost 1.99× planned duration)
- **Slowest shot:** #46 `scene_money`, 52.9 s (character animation — inherent, not a stall; per-kind outlier gate: 0 outliers)
- **Shot 1 vs shot 20:** 51.0 s vs 15.8 s (shot 1 is the 11.8 s paycheck cold-open — cost tracks planned duration, not position; within-kind first→last trends 0.90–1.25×)
- **RSS:** start 57 MB → end 60 MB, peak 121 MB — no climb
- **Remaining child processes:** 0 (per-shot subprocess accounting)
- **The historical "shot-48 problem" resolved with data** (`docs/CURIOSITY_PERFORMANCE_DIAGNOSIS.md`): no progressive degradation exists; the July-24 96–145 s image shots were session CPU contention (image-kind median now 1.4×, worst 3.7×, 0 outliers); the old gate compared across shot kinds and misread composition as slowdown — replaced with within-kind trend + per-kind outlier budget.

## G. Visual Evidence

- **Expression reel:** `tests/expression_tests/` — 6 scenes × 0/50/100% × on/off frames, clips, contact sheet, `results.json` (regenerated this session; gitignored artifacts, reproducible via `test_expressions.py`)
- **Contact sheet:** `output/curiosity_money-goes_pkg/contact_sheet.png`
- **Excerpt / viewing copies:** `output/curiosity_money-goes_pkg/clip_lowres.mp4`, `output/curiosity_money-goes_720p.mp4` (27 MB)
- **Full video:** `output/curiosity_money-goes.mp4` (241.5 s, 188 MB, 8 chapters, 40 sources in meta) — reproducible with one command; the CI full-canary job uploads the complete package as an artifact
- **Visual verdict:** `output/curiosity_money-goes_pkg/verdict.json` — blind fresh-agent taste judgment: **PASS**, personality 3/5, no reject labels, cards ~0.35, overall 6/10

## H. Quality Gates

- **facts gate:** PASS (7/7 claims valid, 16/16 numeric-beat coverage; blocks vague/stale/unsourced; `money-goes-weak` control BLOCKED)
- **fallback gate:** PASS — verdict `degraded`, 1 fallback honestly recorded (beat-6 photo cutaway → statement card when the keyless gateway found no photo); severity ladder equivalent/degraded/unacceptable enforced; unacceptable blocks
- **visual gate:** PASS — blind vision judge (image-capable agent, evidence-only, no code/intent), verdict schema-validated by `judge_verdict.py` (contradicting `pass` booleans refused), stale-verdict guard forces re-judgment of every new cut
- **performance gate:** PASS — within-kind trends flat, 0 outliers, memory stable, 0 process leaks
- **publish gate:** enforced — `produce.evaluate` 5 gates + post_curiosity two-layer gate + `CURIOSITY_PUBLISH_ENABLED=1` requirement; `--force` covers dedup/scheduling only; dry-run simulation: publish-eligible and correctly HELD

## I. Remaining Problems

**Blocking:** none for the recovery scope. Publishing stays frozen by design until the owner runs the explicit public canary (Phase 14 Canary 5 — an owner action by definition).

**Non-blocking (tracked):**
- Beat 6's photo cutaway degraded to a statement card (keyless media gateway found no "hands counting bills" photo) — recorded honestly; a stock API key (PEXELS/PIXABAY, already wired in CI env) would likely fill it.
- Blind judge craft notes on the final cut: the repeated dark-starfield chapter-card template (~7 cards share one look) and one off-register image (Japanese gas-station sign at ~116 s) in the transport chapter — media-relevance miss; taste still passes. Both are P1 creative items.
- Director FAMILY note: 3× real_media back-to-back at beat 17 (reported, under the gate threshold).
- Hook 7/10 (passes; was 8/10 before the paycheck-scene resize — worth a look in the next authoring pass).
- `kola-deepest-hole` has no pro beat story → fails closed on the pro path (author a story or run explicit legacy).
- `sitting-still-speed` and `hurricane-engine` remain quarantined as authored (card reel / stale spans) — re-authoring toward the palette is content work, not pipeline work.

**Future enhancements (assignment P1/P2):** semantic phases for all engines, honest media taxonomy labels, rendered-frame visual-family scoring, comparative media candidate ranking, transition direction, cross-video repetition tracking, and the Phase-15 learning loop (scaffold exists: `showrunner.py` + `quality_memory/`; deliberately not built until the system is stable, per the assignment).

## J. Confidence

- **Implementation correctness: 90%** — every routing/gate/facts/verdict behavior has a passing test or a live negative control (weak story blocked, all-card fixture rejected, stale verdict refused, legacy tripwire); the remaining 10% is code paths only CI exercises (upload path itself cannot be tested without publishing).
- **Visual quality: 70%** — director metrics clean and a blind judge passes it at 6/10 vs professional work, with named craft gaps (chapter-card template, one mismatched image). It is honest, watchable, and gate-clean; it is not yet a 9.
- **Performance stability: 90%** — two full instrumented renders on a clean machine show flat within-kind trends, stable memory, zero process leaks; the historical anomaly is explained with data and a gate is armed to catch recurrence. Long-horizon (many-render) behavior is inferred, not yet observed.
- **Unattended publishing safety: 85%** — five independent gates fail closed (proven by four different real quarantines this session, including a gate-crash path); nothing can upload without `CURIOSITY_PUBLISH_ENABLED=1`; `--force` cannot bypass quality. The missing 15% is exactly why Canary 5 (one explicit owner-approved public upload) exists before re-arming the cron.
