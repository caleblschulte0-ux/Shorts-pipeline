# Claude capability-expansion handoff

> **Canonical capability entrypoint for draft PR #174.** This file is review-only. It grants no production, workflow, uploader, secret, model-download, network-execution, or publishing authority.

## Mission

The operator wants Claude to keep expanding what the Shorts pipeline can do. The capability work is spread across the original Capability Studio, the free-toolchain adoption package, the subscription-independent fallback package, and Advanced Capability Expansion Wave 2.

Do not search the branch randomly. Start here, follow the reading order, run the declared tests, choose one bounded capability family, and only then prepare a production-adoption plan.

## Read in this order

1. `review_prototypes/claude_master_handoff/PLAYBOOK.md`
2. `review_prototypes/claude_master_handoff/CAPABILITY_EXPANSION_HANDOFF.md`
3. `review_prototypes/claude_master_handoff/fixtures/capability_expansion_handoff.json`
4. `docs/future/ADVANCED_CAPABILITY_EXPANSION.md`
5. `review_prototypes/ADVANCED_CAPABILITIES_MANIFEST.json`
6. `review_prototypes/advanced_capabilities.py`
7. `review_prototypes/advanced_requirements.txt`
8. `review_prototypes/test_advanced_capabilities.py`
9. `docs/future/CLAUDE_FREE_TOOLCHAIN_ADOPTION_ROADMAP.md`
10. `review_prototypes/capability_studio/CLAUDE_ADOPTION_MANIFEST.json`
11. `review_prototypes/capability_studio/toolchain_catalog.py`
12. `review_prototypes/capability_studio/scene_router.py`
13. `review_prototypes/capability_studio/integration_compiler.py`
14. `review_prototypes/capability_studio/toolchain_executor.py`
15. `docs/future/CLAUDE_INDEPENDENCE_ROADMAP.md`
16. `review_prototypes/subscription_fallback/ADOPTION_MANIFEST.json`

## What lives where

### Capability Studio: original free production toolbox

Use `review_prototypes/capability_studio/` for:

- FFmpeg and ffprobe;
- SVG motion, CairoSVG, Pillow, ImageMagick;
- Manim, Blender, Graphviz, Mermaid and LibreOffice headless;
- OCRmyPDF, Tesseract and Poppler;
- PySceneDetect, OpenTimelineIO and MoviePy;
- CLIP, SAM 2, MediaPipe, OpenCV and rembg;
- Demucs, Rubber Band and optional Audacity macros;
- yt-dlp with explicit rights gates;
- GDELT, Common Crawl, Wikidata, Wikipedia, OWID, FRED, Census and NOAA;
- semantic scene routing, command compilation, tool detection and workspace-scoped plan execution.

The important ownership files are:

```text
review_prototypes/capability_studio/toolchain_catalog.py
review_prototypes/capability_studio/scene_router.py
review_prototypes/capability_studio/integration_compiler.py
review_prototypes/capability_studio/toolchain_executor.py
```

### Advanced Capability Expansion Wave 2

Use `review_prototypes/advanced_capabilities.py` for the additional 38 review-only capabilities:

- Ollama and llama.cpp local structured generation;
- sentence-transformers, FAISS, sqlite-vec and SQLite FTS5 memory;
- RSS/Atom, sitemaps, Trafilatura/readability, JSON-LD, Playwright and WARC evidence;
- PaddleOCR;
- DuckDB, Polars, data compatibility gates, Vega-Lite and Plotly/Kaleido;
- Lottie and Remotion;
- Nominatim, Overpass, GeoPandas, MapLibre and SVG map fallback;
- WhisperX, stable-ts, Silero VAD, RNNoise and librosa rhythm grids;
- karaoke captions, optical-flow scoring, smart 9:16 reframing and black/freeze-frame QA;
- SigLIP, DINOv2 and Grounding DINO;
- Argos Translate and NLLB;
- MusicGen and AudioGen plans with procedural FFmpeg SFX fallback.

The authoritative summary is `docs/future/ADVANCED_CAPABILITY_EXPANSION.md`; the machine status is `review_prototypes/ADVANCED_CAPABILITIES_MANIFEST.json`.

### Subscription-independent operation

Use `review_prototypes/subscription_fallback/` when a capability depends on Claude, Gemini, a local model or a same-day provider. It owns:

- provider-health routing and circuit breakers;
- Claude -> Gemini -> local model/template degradation;
- approved-package buffering;
- atomic claims and upload idempotency;
- explicit FULL/ACCEPTABLE/DEGRADED/BUFFERED/BLOCKED states.

Capability adoption must not make scheduled posting depend on same-day generation.

## Required preflight

Run before proposing or editing a production adapter:

```bash
git status --short --branch
python -m review_prototypes.claude_master_handoff.cli summary
python -m review_prototypes.claude_master_handoff.cli validate --repo .
python -m unittest -v review_prototypes.claude_master_handoff.test_master_handoff
python -m unittest -v review_prototypes.test_advanced_capabilities
python -m unittest -v \
  review_prototypes.capability_studio.test_capability_studio \
  review_prototypes.capability_studio.test_free_capabilities \
  review_prototypes.capability_studio.test_toolchain_adoption
python -m unittest -v review_prototypes.subscription_fallback.test_subscription_fallback
python -m review_prototypes.capability_studio.toolchain_cli catalog
python -m review_prototypes.capability_studio.toolchain_cli doctor
python -m review_prototypes.capability_studio.toolchain_cli keys
```

Do not claim a suite passed unless it was executed in the current checkout. A declared test count is not current execution evidence.

## Decide which capability lane applies

```text
Need a free renderer, media tool or public-data adapter
  -> Capability Studio catalog/router/compiler/executor

Need local AI, semantic memory, advanced extraction, maps, captions,
advanced visual ranking, localization or generated audio
  -> Advanced Capability Expansion Wave 2

Need the feature to survive Claude/Gemini/provider outage
  -> Subscription fallback package

Need institutional learning across videos and channels
  -> Professional Media OS, records and lineage first
```

## Recommended adoption order

1. **Data foundation:** DuckDB, Polars, unit/geography/vintage/frequency gates and Vega-Lite.
2. **Research intake:** RSS/Atom, sitemaps, article extraction, JSON-LD and browser/WARC evidence.
3. **Caption and technical QA:** Silero VAD, karaoke captions, stable-ts/WhisperX fallback, black/freeze-frame checks.
4. **Motion graphics:** Lottie and Remotion shadow renders, retaining FFmpeg as canonical final assembly.
5. **Maps:** Nominatim/Overpass -> GeoPandas/MapLibre -> SVG fallback.
6. **Semantic memory:** sentence-transformers -> FAISS/sqlite-vec -> SQLite FTS5 fallback.
7. **Local generation:** Ollama -> llama.cpp -> deterministic writer; output must pass the same evidence contracts.
8. **Visual intelligence:** smart reframe, SigLIP, DINOv2 and Grounding DINO with CLIP/OpenCV fallback.
9. **Heavy generative media:** MusicGen/AudioGen and other GPU paths only after exact version, checkpoint, license, runtime and resource proof.

## Required phase declaration

Before writing production code, Claude must state:

```text
Selected capability family:
Specific capability:
User-visible problem it solves:
Current production contract owner:
Expected production files/symbols:
Feature flag and default:
Authority ceiling:
Primary implementation:
Deterministic fallback:
Rights/license rule:
Runtime and resource ceiling:
Tests and matched artifacts:
Stop conditions:
Rollback action:
```

## Capability acceptance gate

A capability is not adopted merely because its package imports or its command runs. It must prove all of the following:

- the selected scene/story actually benefits from it;
- source, model and output licensing are recorded;
- no secret value is logged;
- all outputs remain inside the run workspace;
- exact versions and model/checkpoint hashes are pinned where relevant;
- runtime, memory, storage and GPU ceilings are enforced;
- a lighter deterministic fallback produces a complete valid video;
- the incumbent remains available behind rollback;
- baseline and shadow use identical source evidence, narration and metric definitions;
- complete-video QA stays renderer-independent;
- a showrunner BLOCK remains BLOCK;
- publishing remains frozen during shadow proof.

## Stop immediately when

- a current production contract differs from the handoff assumptions;
- a dependency or model license is unclear;
- the capability requires an unbounded download or unpinned checkpoint;
- the only fallback is another paid or unreliable provider;
- resource use exceeds the declared ceiling;
- output escapes the workspace;
- the feature weakens factual, rights, duplicate, QA or upload gates;
- the feature changes publishing or workflow authority without explicit approval.

## First bounded task for Claude

When the operator asks to add capabilities, Claude should not wire the whole list. Claude should:

1. run the preflight and all capability suites;
2. inventory what production already has so duplicate implementations are not created;
3. select one capability family using the recommended order;
4. create a record-only or plan-only adapter first;
5. generate shadow artifacts beside the incumbent;
6. preserve all candidates and compare them blindly;
7. retain only a proven winner behind a default-off feature flag;
8. report exact commands, exit codes, changed files, artifact paths, verdicts and rollback.

## Status truth

- PR: #174
- branch: `agent/claude-roadmap-review`
- scope: review-only
- production imports granted by this handoff: 0
- workflow changes granted by this handoff: 0
- publishing authority granted by this handoff: none
- mandatory new API keys: none
- advanced capability count declared by Wave 2: 38
- local/network/GPU execution default: disabled or plan-only until separately validated
