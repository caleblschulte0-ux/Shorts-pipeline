# Curiosity File Reconciliation — pro-history → main-based integration branch

**Date:** 2026-07-25
**Source (archival):** `recovery/curiosity-pro-history` = `a0bef66`
**Target:** `feature/curiosity-pro-integration` (branched from `origin/main` = `6b03641`)
**Method:** selective `git checkout a0bef66 -- <path>` per file. **No unrelated-history
merge was used** — `git merge-base origin/main a0bef66` exits 1 (the histories are
genuinely disconnected), so every file below was recovered individually and classified.

Diff basis: `git diff --name-status origin/main a0bef66` → 125 added / 61 modified /
399 deleted (main-only). Full listing archived in the session scratchpad; the
decisions are recorded here.

---

## 1. Recovered verbatim (NEW on main — pro-only files)

### Engine (`data_learning/`)
| Path | Why | Tests |
|---|---|---|
| `pro_render.py` | The pro assembler (planner-driven shots, publishing package, fallback ledger, perf hooks) | producer smoke, full canary |
| `planner.py` | Whole-video visual planner (beat → shot contract) | exercised by smoke/canary |
| `flat2d.py` | Designed-2D motion-graphics engine | scene tests |
| `scenes.py` | Character/scene vignettes wired with structured expressions | `scripts/test_expressions.py` |
| `expression.py` | Structured emotion → whole-body pose deltas (clamped, deterministic) | `scripts/verify_expression_gates.py`, `test_expressions.py` |
| `perf_instrument.py` | Per-stage/per-shot timing, memory, subprocess accounting | `scripts/test_perf_instrument.py` |
| `media.py`, `media_video.py`, `stock.py` | Media gateway (image/video search, licensing, appeal gates) | exercised by canary; perf attribution |
| `footage_hybrid.py` | Footage windows, Ken Burns image beats, dissolve joins | exercised by canary |
| `continuity.py` | Continuity trace for the judge package | producer smoke |
| `contrast_director.py`, `extra_director.py` | Medium-variety + "be extra" passes inside pro_render | exercised by canary |
| `continents.py` | Landmass silhouettes used by pro_render | import check |
| `showrunner.py` | Learning-loop scaffold (Phase 15, future) | `scripts/quality_gate.py` imports it |

### Stories + data
| Path | Why |
|---|---|
| `pro_stories/*.beats.json` (7 stories + fixtures) | The pro beat packages incl. flagship `money-goes` with inline `facts[]` |
| `data/curio_sky_reference.json`, `data/curio_speed_ladder.json` | Data files pro stories reference |
| `quality_memory/` (README, rules.json, ledger.jsonl) | Evidence-gated learning ledger |
| `footage_journeys.example.json` | Media-journey config example |

### Doctrine (`data_learning/`)
`DIRECTOR.md`, `TASTE_JUDGE.md`, `VISUAL_STANDARD.md`, `PRO_DOCTRINE.md`,
`COOL_JUDGE.md`, `HOOK_DIRECTOR.md`, `MOTION_FIRST.md`, `NO_DULL_BEATS.md`,
`PERSPECTIVE_DIRECTOR.md`, `EXPRESSION_EVOLUTION.md`, `PRO_VALIDATION.md`
— the single visual authority the director loop and judges enforce.

### Scripts (`scripts/`)
| Path | Consumer |
|---|---|
| `produce.py` | THE canonical producer (post_curiosity → produce) |
| `no_dull_beats.py` | Director loop (novelty/hook/pacing/variety/dull/cool + repair) — called by produce |
| `judge_verdict.py` | Validates + serializes the blind taste verdict (fail-closed contract) |
| `visual_judge.py` | Blind evidence package builder — called by pro_render |
| `hook_director.py`, `interest_judge.py`, `cool_judge.py` | Invoked by no_dull_beats + the publish gate |
| `editorial_review.py` | Vision-review harness over the beatmap |
| `qa_frames.py`, `qa_motion.py`, `qa_semantics.py`, `qa_escalation.py` | Legacy-preview QA lane in curiosity.yml |
| `quality_gate.py` | Show-bar gate (uses showrunner) |
| `render_gates.py` | Automated post-render verdict (technical/fallback/perf/package) |
| `perf_experiments.py`, `perf_test_render.py`, `profile_scenes.py` | Performance diagnosis harness (Phase 6) |
| `test_expressions.py`, `test_expressions_render.py`, `verify_expressions.py`, `verify_expression_gates.py`, `test_perf_instrument.py` | Test suites |
| `footage_preview.py` | Interactive media QA tool |

### Workflows
`.github/workflows/expression-tests.yml` — expression regression CI (unit gates,
measured visual proof, perf sanity).

---

## 2. Reconciled by hand (files that differ in BOTH histories)

| Path | Chosen | Rejected behavior | Why |
|---|---|---|---|
| `scripts/post_curiosity.py` | Pro version (produce routing, two-layer non-bypassable gate, `--force`=dedup-only) **with main's `_save_log` restored** | Pro's plain `write_text` log save | The pro snapshot predates main's `fsutil.atomic_write_json`; taking it verbatim would have regressed crash-safe log writes |
| `data_learning/curiosity.config.json` | Pro version | — | Verified superset: `kola-deepest-hole` byte-identical to main, `sitting-still-speed` evolved (adds `world`), plus `money-goes` + `hurricane-engine` registrations |
| `data_learning/CURIOSITY_BRAIN.md` | Pro version | Main's stale §5/§7 | Pro carries the reconciled single-authority doctrine (≤5s cadence, five co-equal engines, card minority cap, pro renderer/legacy fallback) |
| `.github/workflows/curiosity.yml` | Pro version (has `pro` mode + producer path) | Main's translation-cache step | Verified: neither `post_curiosity.py` nor `longform_render.py` reads `cache/translation/` — that step belongs to the shorts/localize machinery, vestigial here. Further routing surgery lands in the Phase-3 commit |
| `data_learning/data/curio_{cmb_speed,everyday_speeds,orbit_vs_bullet}.json` | Pro versions | — | Match the pro `sitting-still-speed` beats |
| `.gitignore` | **Main's version** + pro's two additions (`media/`, `tests/expression_tests/`) | Pro's version wholesale | Main's is newer (cache/, `*.runtime.json`, `samples/*.mp4` rules postdate the pro fork) |
| `requirements.txt` | **Main's version unchanged** | Pro's version (missing opencv/matplotlib pins) | Main is a superset; `edge-tts`, `pillow`, `numpy` already present. `psutil` used by perf_instrument is import-guarded (falls back to /proc) |
| `data_learning/longform_render.py` | **Main's version unchanged** | Pro's V5–V8 evolution (hero splices, world engine, stamps) | Legacy is demoted to explicit emergency fallback; its job is stability. Main's copy is the one proven live. The evolved version stays archived on the recovery branch |

## 3. Deliberately NOT recovered (rejected)

| Set | Reason |
|---|---|
| `output/*.mp4`, `output/*_pkg/*`, `preview/*`, `samples/*` | Generated render artifacts. **Committing an 80 MB mp4 into git (as the pro branch did) is rejected**; artifacts belong in CI artifact storage / release assets |
| `data_learning/world_engine.py`, `world_builders.py`, `shots.py`, `scripts/check_builders.py` | Orphaned V8 legacy-renderer evolution — only consumer was the rejected pro `longform_render.py`. Verified: zero importers in the recovered tree |
| `data_learning/evidence.py`, `repair.py`, `render_director.py`, `sound_design.py` | Same orphan cluster; grep confirms no importer. `no_dull_beats` carries its own repair logic; `pro_render` its own audio mastering |
| `make_explainer.py`, `make_motiongraphic.py`, `make_short.py`, `make_trending.py`, `tiktok_demo.py`, `tiktok_demo_oneclick.ps1`, `scripts/run_daily.py`, `scripts/diag_gemini.py` | Files main deleted/superseded in other workstreams — main is authoritative for non-curiosity systems |
| `.github/workflows/{claude-smoke,gemini-diag,test_funnel}.yml` | Unrelated diagnostics |
| `state/analytics_curiosity/2026*.json`, `state/translation_cache.json` | State snapshots — main's live `state/` is authoritative |
| `CURIOSITY_PRO_PRODUCTION_READY.md`, `DELIVERY_REPORT.md` | Premature "production ready" claim documents written before this recovery; superseded. They remain on the archival branch only |
| All other `M`-status files (explainer `mascot.py`/`studio_render.py`/`scene_media.py`, third-channel, scout, analytics, uploaders, brains) | **Main's versions kept untouched** — explainer/mascot work is frozen per Phase 0; unrelated workstreams are not curiosity's to change |

## 4. Verification run at recovery time

```
python3 -m py_compile <39 recovered .py files>          → exit 0
import-closure check (12 pro-path modules on this branch) → all OK
```
