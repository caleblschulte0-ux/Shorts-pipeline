# Capability Studio — review-only prototype

This package is an isolated reference implementation for future creative, media,
audio, editing, QA, research, replay, evidence, plugin, and free-first production
capabilities.

## Safety boundary

- no production imports;
- no workflow, uploader, OAuth, renderer, secret, or production-state access;
- no network execution by default;
- all remote integrations return inspectable request plans;
- all local integrations return inspectable command plans;
- optional local workers execute only when invoked explicitly;
- writes occur only when the caller supplies a path;
- nothing here is wired to a live channel.

## Existing capability set

- audience-demand mining and competitor reverse engineering;
- creative candidate tournaments and global idea routing;
- intentional B-roll planning and multi-provider media search;
- browser/PDF evidence capture and rights lineage;
- directed voice, local transcription, sound design, deterministic editing, enhancement, QA, replay, and capability truth.

## Free-first expansion

The large free expansion adds:

- GDELT, Wikidata, Wikipedia, Common Crawl, SEC EDGAR, Our World in Data, FRED, Census, and NOAA request planners;
- yt-dlp metadata/subtitle/thumbnail plans and rights-gated authorized clip ingest;
- OCRmyPDF and PDF page-rendering plans;
- dependency-free animated 1080x1920 SVG charts and comparison cards;
- Manim, Blender, ImageMagick, LibreOffice, Graphviz, Mermaid, and CairoSVG command plans;
- PySceneDetect scene boundary and clip-splitting plans;
- OpenTimelineIO-compatible timeline documents plus FFmpeg and optional MoviePy rendering plans;
- local CLIP scoring, Pillow perceptual hashing, SAM 2 integration contracts, and MediaPipe tracking;
- Demucs stem separation, Rubber Band time stretching, Audacity macro plans, and FFmpeg mastering;
- a free-first pipeline blueprint mapping these tools into discover, verify, script, source media, build visuals, narrate, edit, enhance, QA, and package stages;
- explicit free fallbacks and a zero-required-secret contract for the new stack.

## Pipeline fit

`FreeFirstPipelinePlanner` maps the new capabilities into stable integration slots:

```text
topic_discovery
research_packet
media_manifest
scene_plan
narration
timeline
rough_cut
quality_gate
run_lineage
```

The package does not import the production pipeline. Claude can later map one slot
at a time behind disabled feature flags and shadow execution.

## API-key policy

The new free stack requires **no new API key** to generate a blueprint or use its
local tools and keyless sources.

Useful existing keys:

- `YOUTUBE_API_KEY`
- `PEXELS_API_KEY`

Optional free public-data keys:

- `FRED_API_KEY`
- `NOAA_TOKEN`
- `CENSUS_API_KEY` — required only when the Census adapter is enabled

Paid providers remain registered only as optional adapters. They are not part of
the free-first default path.

## Isolated checks

```bash
python -m unittest \
  review_prototypes.capability_studio.test_capability_studio \
  review_prototypes.capability_studio.test_free_capabilities

python -m review_prototypes.capability_studio.cli demo
python -m review_prototypes.capability_studio.free_cli keys
python -m review_prototypes.capability_studio.free_cli doctor
python -m review_prototypes.capability_studio.free_cli plan \
  --topic "Why printer ink is expensive" \
  --channel "consumer facts"
```

## Adoption rule

Do not import this package from production. Port one adapter or contract at a time
through a separate reviewed change, execute real dependency tests, validate rights
and source lineage, and verify finished-video behavior before granting authority.
