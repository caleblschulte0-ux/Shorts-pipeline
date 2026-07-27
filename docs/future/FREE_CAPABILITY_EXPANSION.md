# Free Capability Expansion — Claude adoption guide

> Review-only. All code lives under `review_prototypes/capability_studio/` and changes no production behavior.

## What was added

This expansion turns the Capability Studio into a free-first production design rather
than a paid-provider-centered design.

### Research and evidence

- GDELT article discovery
- Wikidata SPARQL
- Wikipedia summaries for discovery context
- Common Crawl index/CDX planning
- SEC EDGAR company facts
- Our World in Data CSV retrieval
- FRED observations
- Census ACS5 queries
- NOAA CDO queries
- OCRmyPDF and PDF page rendering

### Media and scene preparation

- yt-dlp metadata, subtitle, and thumbnail ingest
- explicitly rights-gated clip ingest
- PySceneDetect cut detection and splitting
- source and page-lineage notes on all evidence plans

### Graphics and visual generation

- dependency-free animated SVG charts and comparison cards
- Manim
- Blender
- ImageMagick
- LibreOffice headless rendering
- Graphviz
- Mermaid
- CairoSVG

### Vision and QA

- local CLIP scoring
- Pillow perceptual hashing
- SAM 2 integration contract
- MediaPipe face, hand, and pose tracking
- deterministic local visual ranking and hard gates

### Audio

- Demucs source separation
- Rubber Band time stretching and pitch control
- optional Audacity macros
- FFmpeg mixing and mastering

### Editing and pipeline fit

- OpenTimelineIO-compatible documents
- deterministic gap and clip placement
- FFmpeg concat plans
- optional MoviePy rendering
- a complete free-first blueprint from discovery through replay packaging

## Free-first rule

The default blueprint has:

- required new secrets: **0**
- estimated metered provider cost: **$0.00**
- paid provider fallbacks: **disabled**
- production wiring: **false**
- network execution in the review package: **false**

Existing YouTube and Pexels keys remain useful. FRED, NOAA, and Census keys are
optional free data-access enhancements.

## Production adoption order

1. Run both isolated test modules.
2. Run `free_cli doctor` on the intended runner.
3. Select one pipeline slot and one local tool.
4. Add a disabled production adapter in a separate PR.
5. Record plans and outputs in shadow mode.
6. Validate source rights, artifact equivalence, runtime, and failure handling.
7. Grant bounded authority only after the shadow evidence is satisfactory.
8. Keep every paid provider outside the default path unless the operator explicitly enables a budget.

## Important limitations

- Command plans are integration contracts, not proof that every third-party tool is installed.
- SAM 2 is deliberately release-pinned before execution; the worker refuses to guess across incompatible releases.
- Audacity command-line behavior varies by platform and must be validated locally.
- yt-dlp support is not permission to download or reuse media; production must require an explicit rights record.
- Keyless data sources still require caching, provenance, rate-limit handling, and source-specific terms review.
