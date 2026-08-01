# Curiosity Channel Recovery Manifest

**Created:** 2026-07-25
**Purpose:** authoritative record of the fragmented state, the recovery plan, and
the target architecture. Companion doc: `CURIOSITY_FILE_RECONCILIATION.md`
(per-file decisions).

---

## The confirmed fragmentation

| # | System | Where | Status |
|---|---|---|---|
| 1 | Live curiosity long-form pipeline | `scripts/post_curiosity.py` on `main` | ❌ calls `longform_render.render(...)` directly (legacy) |
| 2 | Legacy long-form renderer | `data_learning/longform_render.py` on `main` | Live publisher; becomes explicit emergency fallback |
| 3 | Disconnected pro-render history | `recovery/curiosity-pro-history` (= `a0bef66`) | **No merge base with main** — `git merge-base origin/main a0bef66` exits 1. Recovered file-by-file |
| 4 | Vertical explainer/data-channel renderer | `data_learning/studio_render.py` + `mascot_director` on `main` | **Frozen** during recovery (Phase 0) — untouched |
| 5 | Mascot action system | explainer subsystem on `main` | Preserved as-is; concepts (arcs, whole-body poses, structured emotion) live in curiosity via `expression.py` — see `docs/EXPLAINER_MASCOT_SYSTEM.md` |
| 6 | Quality-control / editorial-reset systems | director+judge scripts in pro history | Recovered as the enforcement layer of the canonical producer |
| 7 | Large mixed draft PR / branch | `claude/youtube-curiosity-channel-s8mm94` | Superseded — no further growth; its useful content is the pro history archived at `a0bef66` |

## Current live curiosity entry point (main, before recovery)

```
scripts/post_curiosity.py:main()
  → longform_render.render(slug, out, config_path=...)   # legacy, ungated
```

## Branches

| Branch | Base | Purpose |
|---|---|---|
| `recovery/curiosity-pro-history` | `a0bef66` (disconnected tip) | **Archival.** Complete pro history incl. expression + perf work. Never develop here |
| `feature/curiosity-pro-integration` | `origin/main` (`6b03641`) | The recovery branch — normal merge base with main; selective file recovery + routing + gates |

## Key commits in the archived pro history

```
a0bef66  (tip) — full pro system + expression + perf instrumentation + validation
9032a73  validation: PRO_VALIDATION.md — enforced studio proven on real renders
7edacd0  produce.py: single canonical story→film path
7bb0700  pro_render: honest fallbacks + publishing package + structured verdict
4484a5c  post_curiosity: publish through the PRO producer; non-bypassable gate
2f9f98e  expression system: structured emotion in all six character scenes
9f52187  perf instrumentation: per-stage timing, per-shot metrics, memory
0bd6061  money-goes media beats restored (rejects the flat-card workaround)
```

## Known degraded-media workaround (REJECTED)

Commits `b0d06c5`/`b0b2dc7` ("convert all footage beats to designed_2d with
flat_statement placeholders") stripped external media to dodge retrieval
failures. **Rejected**: `0bd6061` restored the media beats; the recovered
`money-goes.beats.json` carries real media queries. A visual describing a photo
while showing a text card is a quality failure, not a fallback.

## Known performance symptoms (Phase 6 input)

From the full `money-goes` render (2026-07-24, `performance.json`):
- Total wall: 2904.5 s for 240 s of video; 50 shots.
- Shot 48 (Ken Burns image beat): **132.4 s for 5.4 s of video (24.4× cost)**.
- First-3 vs last-3 shot cost ratio: **3.00×** (gate threshold 1.5×) → perf gate HOLD.
- Controlled experiments (A/B/E, archived branch): local render loop is **flat**
  (0.95× first→last); memory stable (+24 MB). The rise is attributed to the
  **media/asset-resolution path**, not the render loop. Phase 6 must confirm from
  the per-shot `asset_resolution` timings and fix the media path (retry caps,
  timeouts, caching) — not the renderer.

## CI status at recovery start

- `main`: no curiosity-specific CI beyond the workflow's own render modes.
- Pro history: `expression-tests.yml` (unit gates + measured visual proof + perf
  sanity) — recovered.
- Phase 12 adds the layered curiosity CI (static / unit / scene / producer smoke /
  perf / canary-dispatch).

## Publishing safety (Phase 0 freeze)

- Publishing requires **`CURIOSITY_PUBLISH_ENABLED=1`** (new hard flag; default
  hold: render → review → package → stop).
- Legacy renderer requires **`CURIOSITY_RENDERER=legacy`** (default `pro`); the
  default path never silently falls back to legacy.
- The weekly cron stays disarmed until the canary sequence passes.

## Target architecture

```
story package (pro_stories/<slug>.beats.json [+ facts])
  → planner (semantic beat → shot contracts)
  → canonical producer (scripts/produce.py)
      → pro renderer (data_learning/pro_render.py)
      → performance report        (<out>_pkg/performance.json)
      → honest fallback ledger    (<out>_pkg/fallbacks.json)
      → director loop + repair    (scripts/no_dull_beats.py, ≤2 repair passes)
      → blind visual judge        (visual_judge package → judge_verdict.py → verdict.json)
      → facts gate                (scripts/facts_gate.py → .facts-report.json)
      → publishing package        (.meta.json / .srt / .jpg / produce_report.json)
  → explicit publish gate (post_curiosity: CURIOSITY_PUBLISH_ENABLED + quality gate,
    --force = dedup/scheduling only)
  → YouTube (disabled until canary sequence passes)
```
