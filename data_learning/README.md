# data_learning — data-driven micro-learning add-on

A **niche-agnostic, data-driven** short-video generator that bolts *on top of*
the existing Shorts-pipeline **without modifying a single existing file**.

Where the base pipeline turns *trending news* into 9:16 explainers, this add-on
turns *free public datasets* (unemployment, inflation, rates, …) into the same
kind of short — a chart-backed "one claim, one chart, one takeaway" micro-lesson.

## How it piggybacks (zero changes to the base pipeline)

The only contract with the base pipeline is its **package JSON schema** —
the exact `{title, script, shots, punches, hashtags, music_vibe}` dict that
`make_explainer_stacked.build_from_package()` already consumes (the same thing
the daily trending routine writes by hand).

```
free public data  ─►  transform  ─►  pick strongest insight
                  ─►  render chart PNG (matplotlib, optional)
                  ─►  emit a base-pipeline package  ─►  QA validate
                  ─►  drop into review/  (or state/trending_packages/<date>/)
```

The base renderer is reused untouched in two ways:

1. **Schema** — emitted packages pass `build_from_package`'s exact field
   accesses (verified by `tests/`).
2. **Charts as shot images** — `build_from_package` already accepts a local
   image path for a shot (`_fetch_image` passes local paths through). We render
   a 1080×960 chart PNG (the top-half canvas) and attach it as the proof shot's
   `image_url`; the bottom half stays gameplay. No renderer change needed.

## Quick start

```bash
pip install -r data_learning/requirements.txt        # matplotlib (optional)

# Generate all videos from the niche config into a REVIEW folder (human gate):
python -m data_learning.generate

# One video, skip charts (pure stock B-roll fallback), strict QA:
python -m data_learning.generate --slug inflation-pain-points --no-chart --strict

# Run the tests:
python -m data_learning.tests.test_pipeline
```

Output packages land in `data_learning/review/<YYYYMMDD>/` by default — a
**human-approval gate** (the recommended operating model for an automated
channel). Inspect them, then either render locally or publish.

## Wiring into the daily upload pipeline (opt-in)

`--publish` writes packages straight into `state/trending_packages/<YYYYMMDD>/`,
which the **unchanged** `scripts/run_trending_daily.py` already renders + uploads:

```bash
python -m data_learning.generate --publish
# charts are gitignored; when publishing, commit them so CI can resolve the path:
git add -f data_learning/charts/<YYYYMMDD>/
git add state/trending_packages/<YYYYMMDD>/
```

> The chart path in a package is **repo-relative** (e.g.
> `data_learning/charts/20260603/inflation-pain-points.png`). The daily
> workflow runs from the repo root, so the path resolves at render time — but
> the PNG must be committed (it's gitignored by default). If a chart is missing,
> the renderer gracefully falls back to the shot's stock `query`.

## Retargeting to a new niche

Everything is config-driven in `niche.config.json`. A new niche = a new config:
no code changes. Each `videos[]` entry names:

| field          | meaning                                                      |
|----------------|-------------------------------------------------------------|
| `source`       | adapter id: `offline`, `fred`, `bls` (see `sources/`)       |
| `key`          | series id / dataset key for that adapter                    |
| `params`       | adapter params (`file`, `observations`, `series`, …)         |
| `topic`        | clean short name for the title + chart heading              |
| `insight_type` | `rank` \| `comparison` \| `trend` \| `outlier` \| `auto`    |
| `ascending`    | `true` when *lowest* is best (e.g. unemployment)            |
| `use_baseline` | include the dataset's baseline as a comparison anchor       |
| `hashtags`     | topical tags (base orchestrator merges its reach baseline)  |

Add a new adapter by subclassing `DataSource` in `sources/` and registering it
in `sources/__init__.py:REGISTRY`.

## Data sources

| adapter   | source                              | key/cost                          |
|-----------|-------------------------------------|-----------------------------------|
| `offline` | bundled JSON snapshots in `data/`   | none — zero network, runs in CI   |
| `fred`    | FRED (St. Louis Fed) macro series   | free key via `FRED_API_KEY`       |
| `bls`     | BLS Public Data API                 | open (v1); free key `BLS_API_KEY` |

The `offline` adapter is also a **cache format**: a live pull can be snapshot
to a `data/*.json` file (same shape) for reproducible re-renders. The bundled
samples use real, citable figures (BLS April-2026 state unemployment & CPI,
FRED FEDFUNDS) so the demo output is accurate, not placeholder.

## QA & guardrails (`qa.py`)

`validate()` returns `[]` only when the package is safe to ship. It enforces:

- every shot/punch phrase is a **verbatim substring** of the script
  (the base renderer's alignment requirement);
- every spoken **metric traces to the fact table** (catches hallucinated
  numbers; year labels and rounding are handled);
- a **source footer** exists for on-screen citation;
- honest title length, script length, and caption density;
- optional **source allowlist** (pin approved publishers per niche).

## Module map

```
data_learning/
  generate.py            CLI entrypoint (data → package → QA → write)
  niche.config.json      the niche definition (swap this to retarget)
  sources/               adapters: base, offline, fred, bls  (+ REGISTRY)
  transforms.py          whitelisted, auditable numeric transforms
  insights.py            pick the strongest insight (rank/comparison/trend/outlier)
  charts.py              matplotlib chart → 1080×960 PNG, house style (optional)
  packager.py            insight → base-pipeline package (verbatim-safe)
  qa.py                  pre-publish validator
  data/                  bundled dataset snapshots (offline source)
  tests/                 contract + QA tests
```

## Design notes

- **Numbers never come from a model.** Values come from source data and a fixed
  whitelist of transforms (`transforms.py`); only phrasing varies. That's both
  the accuracy guarantee and the "not a template/inauthentic" variation the
  platforms reward.
- **Per-video variation** is deterministic per slug (rotating hooks/takeaways),
  so output is reproducible but not identical across videos.
- **Graceful degradation**: no matplotlib → no chart → stock B-roll fallback;
  no API key → use `offline` snapshots. The pipeline always produces a video.
```
