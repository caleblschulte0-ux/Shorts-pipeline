# Curiosity render performance — measured diagnosis (Phase 6)

**Data source:** `performance.json` from the full `money-goes` production render
of 2026-07-24 (2904.5 s wall for 240.0 s of video, 50 shots, per-shot stage
attribution from `data_learning/perf_instrument.py`), plus controlled
re-measurement on 2026-07-25 (idle 4-core container).

This replaces the earlier guesswork ("resource issue", "media path is the
bottleneck") with what the instruments actually recorded.

---

## 1. What the July-24 report shows

### Stage totals

| Stage | Time |
|---|---|
| shot_visual (50 shots) | 1859.8 s |
| final_mux_and_grade | 508.4 s |
| video_assembly | 233.1 s |
| downscale_720p | 151.8 s |
| image_search (20 calls) | 53.9 s |
| narration_synthesis | 15.7 s |

### Attribution across the 50 shots

| Bucket | Time |
|---|---|
| asset_resolution (media waits) | **53.9 s** |
| frame_render (local CPU) | **1859.8 s** |
| memory | 57 MB → 71 MB (flat) |
| fd count | constant 4 |
| unreaped child processes | 0 recorded |

### The 8 slowest shots — all the same KIND

| Shot | Kind | Planned | Total | Cost |
|---|---|---|---|---|
| 9 | image | 4.7 s | 144.4 s | 30.5× |
| 13 | image | 3.3 s | 137.8 s | 42.2× |
| 48 | image | 5.4 s | 132.4 s | 24.4× |
| 25 | image | 4.2 s | 130.6 s | 31.0× |
| 44 | image | 4.2 s | 104.2 s | 24.7× |
| 14 | image | 3.3 s | 103.7 s | 31.7× |
| 30 | image | 4.2 s | 96.6 s | 22.8× |
| 12 | image | 3.3 s | 81.3 s | 24.9× |

## 2. Findings (measured, not hypothesized)

**F1 — There is NO progressive slowdown.** Within-kind first→last cost trends:
`flat_title` 0.96×, `image` **0.67×** (late image shots were *faster* than early
ones), `scene_money` 1.24×. Memory is flat (+14 MB over 48 minutes), the fd
count never moves, and no child process was left unreaped. The render loop does
not degrade.

**F2 — The old perf gate misdiagnosed composition as degradation.** The
previous heuristic compared the first 3 vs last 3 shots of the *timeline*
across different shot kinds. The expensive Ken-Burns `image` shots happen to
sit in the back half, so the gate read "3.00× rising trend". Fixed in
`scripts/render_gates.py`: trend is now computed **within each shot kind**,
plus an absolute outlier check (any shot >3× its own kind's median).

**F3 — The slow shots are NOT the media path.** Every slow shot has
`asset_resolution_s = 0.0` — the still was already on disk. All 20 image
searches together cost 53.9 s. The cost sits in the Ken-Burns **frame render**
(ffmpeg zoompan).

**F4 — The production numbers do not reproduce on an idle machine.**
Controlled re-measurement of `footage_hybrid.image_beat` on the same container
class, idle, with locally generated stills:

| Source size | Time for a 5.4 s shot | Cost |
|---|---|---|
| 2000×1333 | 8.8 s | 1.6× |
| 4000×2667 (3 reps) | 8.5 / 6.8 / 6.7 s | 1.2–1.6× |
| 8000×5333 | 7.8 s | 1.4× |

Source-image size is **not** the driver, and 6.7–8.8 s ≠ 96–145 s. The July-24
session ran multiple concurrent background renders and monitors in the same
4-core container; the 15–18× inflation on these CPU-bound shots is consistent
with CPU contention, and with F1 (shots rendered *between* the contended
windows were fast). The fresh full canary on the integration branch — run on an
idle container — re-measures this under clean conditions; its
`performance.json` is the deciding artifact.

## 3. Fixes applied

1. **`footage_hybrid.image_beat`**: removed the `-loop 1` input pattern. The
   looped input re-ran the 4K `scale`+`crop` chain for every duplicate input
   frame and buffered them into `zoompan`; the still is now decoded ONCE and
   `zoompan d=frames` + `-frames:v` generate exactly the needed output frames.
   Output verified identical (162 frames / 5.40 s / 1920×1080); ~10 % faster on
   idle hardware and removes the pathological buffering pattern.
2. **`render_gates.gate_performance`**: within-kind trend + per-kind outlier
   budget (see F2). Applied to the July-24 report it correctly reports *no
   rising trend anywhere* and flags the 12 contended image shots as
   unexplained outliers → HOLD, pending the clean re-render.

## 4. Controlled experiments (archived + current)

- **A/B/E loop experiments** (archived branch, commit `bb5a544`): the same
  local scene 10×, 10 different scenes, assembly-only — render loop flat at
  0.95× first→last, memory stable. Runs in CI as
  `scripts/perf_experiments.py` (layer 5 of `curiosity-ci.yml`).
- **Instrumentation harness**: `scripts/test_perf_instrument.py` (unit),
  `scripts/perf_test_render.py`, `scripts/profile_scenes.py` (diagnosis
  tools).

## 5. Verdict against the assignment's targets

| Target | Status |
|---|---|
| representative local shot median ≤ 25 s | ✅ image median 3.3× ≈ 13 s; card/scene shots far under |
| no unexplained shot > 1.5× median | ⚠ gate now enforces per-kind; July-24 outliers attributed to session contention — fresh canary decides |
| child processes after cleanup = 0 | ✅ measured 0 |
| no sustained memory climb | ✅ 57→71 MB over 50 shots |
| 20-shot stability trend | ✅ within-kind trends 0.67–1.24× |

The remaining ⚠ is closed by the fresh canary's `performance.json` (Canary 3),
which runs on an idle container with the fixed `image_beat` and the honest
gate.
