# Claude/Claudio roadmap — adopt the complete free production toolchain

> **Review-only handoff.** The implementation lives under
> `review_prototypes/capability_studio/`. It does not modify production, workflows,
> uploads, publishing, OAuth, or live renderer authority.

## Objective

Turn the free capability catalog into real, correctly routed production capabilities
without making every scene use every tool and without creating a fragile pile of
shell commands. The default render must continue to work when optional tools are
missing. Paid providers remain optional and disabled by default.

## Current facts Claude must verify again

1. Gemini already has production helpers and expects `GEMINI_API_KEY`; do not create
   a second key name.
2. FFmpeg is already core production infrastructure.
3. The chart path inspected in the handoff uses Matplotlib. Manim is a new specialized
   renderer, not a replacement for every chart.
4. Blender may already exist in some paths. Reuse working code instead of creating a
   second incompatible Blender contract.
5. Re-run the production contract probe before touching any live file. SHA drift is a
   migration blocker.

## What this addition provides

### Code

- `toolchain_catalog.py`: one truthful catalog for every free tool, install group,
  stage, best use, cost/resource class, fallback, and warning.
- `scene_router.py`: semantic routing from scene intent to a primary tool chain and
  safe fallbacks.
- `integration_compiler.py`: compiles routes into inspectable `CommandPlan` objects.
- `toolchain_executor.py`: plan-only by default, workspace-scoped, no shell, executable
  allowlist, secret allowlist, timeouts, and per-command logs.
- `toolchain_cli.py`: catalog, doctor, keys, routing, and plan inspection.
- `test_toolchain_adoption.py`: coverage, rights gates, fallbacks, compiler mapping,
  and executor isolation.

### Installation references

- `toolchain/Dockerfile.review`
- `toolchain/install_ubuntu_review.sh`
- `toolchain/requirements-core.txt`
- `toolchain/requirements-vision-audio.txt`
- `toolchain/package.json`
- `toolchain/workflow_snippet.review.yml`

None of those files are wired into `.github/workflows`.

## Complete tool list and proper use

| Tool | Use it for | Do not use it for |
|---|---|---|
| yt-dlp | Metadata, subtitles, thumbnails, and clips with explicit reuse rights | Treating a downloadable video as licensed |
| SVG motion | Fast charts, counters, arrows, comparisons, maps, icon motion | Complex equations or 3D scenes |
| CairoSVG | Deterministic SVG-frame rasterization | Final video encoding |
| ImageMagick | Crops, composites, masks, sharpening, thumbnail normalization | Long timeline editing |
| Pillow | Native Python cards, overlays, hashes, lightweight thumbnails | Heavy video work |
| Manim | Equations, axes, transformations, math/finance explanations | Generic B-roll or simple cards |
| Blender | 3D, spatial demonstrations, procedural products/rooms/maps | Ordinary charts or every story |
| Graphviz | Networks, hierarchies, decision trees, dependencies | Decorative animation |
| Mermaid | Flowcharts, timelines, sequence diagrams | Dense custom layouts requiring exact art direction |
| LibreOffice headless | Source-faithful spreadsheets, decks, and office-document conversion | Inventing charts when structured data is available directly |
| OCRmyPDF/Tesseract/Poppler | Searchable PDFs and page evidence frames | Claim verification without source lineage |
| PySceneDetect | Shot boundaries, clip indexing, B-roll extraction | Semantic understanding by itself |
| OpenTimelineIO | Portable deterministic timeline records and editor interchange | Canonical final rendering |
| MoviePy | Convenient Python previews and unusual composites | Replacing FFmpeg as the final canonical renderer |
| FFmpeg/ffprobe | Normalize, concat, xfade, caption, mix, encode, inspect | Choosing creative concepts |
| CLIP | Semantic relevance ranking and thumbnail/frame preselection | Final editorial judgment by itself |
| SAM 2 | High-quality object masks and tracked cutouts | Automatic activation without pinned code, checkpoint, and license |
| MediaPipe/OpenCV | Pose/face/hand tracking, auto-reframe guidance, technical QA | Identity recognition or creative scoring |
| Demucs | Stem separation and vocal removal on authorized audio | Rights circumvention |
| Rubber Band | Quality time stretching and pitch correction | Large pacing changes that make speech unnatural |
| Audacity macros | Optional repeatable cleanup compatible with manual review | Core unattended path until its CLI is validated on the runner |
| GDELT | News-event discovery and trend candidates | Sole factual authority |
| Common Crawl | Historical page discovery | Assuming indexed text is current or authoritative |
| Wikidata/Wikipedia | Entity orientation and source discovery | Sole support for consequential claims |
| OWID/FRED/Census/NOAA | Structured public data and chart-ready evidence | Using mismatched units, vintages, or geography |

## Semantic routing policy

Claude should add one scene-intent field to the planning contract, then map it through
`FreeSceneRouter`. The intended routing is:

```text
simple chart/comparison       -> SVG + CairoSVG + FFmpeg
formula/equation              -> Manim -> SVG fallback
process/timeline              -> Mermaid -> Graphviz -> SVG fallback
network/hierarchy             -> Graphviz -> Mermaid fallback
3D/spatial                    -> Blender -> SVG/stock fallback
office document               -> LibreOffice -> Poppler/OCR -> FFmpeg
authorized web clip           -> rights gate -> yt-dlp -> PySceneDetect -> FFmpeg
photo composite               -> ImageMagick/Pillow -> FFmpeg
subject cutout                -> SAM 2 -> rembg fallback
presenter tracking            -> MediaPipe/OpenCV -> FFmpeg
audio cleanup                 -> Demucs/Rubber Band -> FFmpeg fallback
final timeline                -> OpenTimelineIO record -> FFmpeg render
```

Never route by tool availability alone. Route by what the scene must communicate,
then choose the highest-quality available chain inside the runner budget.

## Production integration points

Reinspect and map these files before patching:

1. `data_learning/story.py` — add optional scene intent and tool-policy metadata;
2. `data_learning/charts.py` — keep Matplotlib and existing renderers; register SVG,
   Manim, Graphviz/Mermaid, office-document, and Blender adapters as additional kinds;
3. `data_learning/scene_timeline.py` — preserve one clock and declare renderer output
   timing rather than allowing tools to invent independent timing;
4. `data_learning/studio_render.py` — materialize each selected renderer into isolated
   scene artifact directories, normalize with FFmpeg, and preserve manifests;
5. `scripts/showrunner_review.py` — add tool-specific technical checks but keep the
   sovereign finished-video verdict independent of the renderer;
6. `scripts/scene_repair.py` — allow a failed scene to switch renderer families when
   the failure is structural, not just reroll the same tool;
7. `scripts/repair_loop.py` — preserve transactional winner promotion and rollback;
8. `scripts/post_stories.py` — no new publishing authority; feature flags and fail-closed
   gates only after shadow proof.

## Feature flags

Use explicit flags, all defaulting to false at first:

```text
FREE_TOOLCHAIN_ENABLED
SVG_RENDERER_ENABLED
MANIM_RENDERER_ENABLED
BLENDER_RENDERER_ENABLED
DIAGRAM_RENDERERS_ENABLED
OFFICE_EVIDENCE_RENDERER_ENABLED
LOCAL_VISION_ENABLED
LOCAL_AUDIO_ENHANCEMENT_ENABLED
OTIO_TIMELINE_ENABLED
```

Do not create flags per provider when a semantic capability flag is sufficient.

## Adoption phases

### Phase 0 — inventory and freeze

- Re-run production SHA/AST probe.
- Locate every existing FFmpeg, Blender, Gemini, chart, timeline, and image-composite
  path.
- Record duplicates and select one owner per capability.
- Run existing production tests unchanged.

**Gate:** zero production behavior changes.

### Phase 1 — reproducible runner

- Build the review Dockerfile.
- Pin exact Python, apt, npm, model, and checkpoint versions.
- Generate an SBOM or at minimum a version manifest.
- Cache large models and prohibit unverified downloads during a render.
- Split `core` and `heavy` runner profiles if startup time becomes excessive.

**Gate:** `toolchain_cli doctor` is deterministic on two fresh builds.

### Phase 2 — contracts and plan-only compilation

- Port `ToolSpec`, `SceneIntent`, `RouteDecision`, and `CommandPlan` contracts.
- Compile plans but execute none.
- Persist the proposed chain in the run manifest.
- Confirm every route has at least one free fallback.

**Gate:** existing MP4 hashes remain unchanged because no new command executes.

### Phase 3 — shadow artifact generation

Enable one family at a time:

1. SVG/CairoSVG/ImageMagick/Pillow;
2. Graphviz/Mermaid;
3. LibreOffice/OCR/Poppler;
4. PySceneDetect/OpenTimelineIO/MoviePy preview;
5. Manim;
6. Blender;
7. MediaPipe/CLIP;
8. SAM 2 only after exact pinning;
9. Demucs/Rubber Band/Audacity only on authorized audio.

Render new artifacts beside production artifacts. Never substitute them yet.

**Gate per family:** valid media, correct dimensions/fps/duration, source lineage,
resource/time ceiling, and no workspace escape.

### Phase 4 — blind comparison

- Put incumbent and new scene candidates through identical technical prefilters.
- Blind-rank claim clarity, narration fit, readability, motion, novelty, and payoff.
- Preserve losers and scores.
- Measure false approval and false rejection separately.

**Gate:** new family beats or matches the incumbent on a representative corpus and
has a reliable fallback.

### Phase 5 — bounded canary

- Enable one semantic scene class on one channel.
- Cap heavy scenes per video: recommended one Manim or Blender scene, not both by
  default.
- Keep automatic rollback.
- Publishing remains blocked on missing outputs, rights records, or failed final QA.

### Phase 6 — minimum production authority

Grant only the specific validated routes. Tool installation does not itself grant
selection or publishing authority.

## Data-source adoption

The user has added FRED, Census, and NOAA secrets. Claude should:

- detect their presence without printing values;
- call them only from the research stage;
- record query parameters, series/table identifiers, units, geography, release date,
  access time, and raw-response hash;
- convert results into the shared evidence contract;
- reject charts that mix incompatible units or vintages;
- retain keyless fallbacks where possible.

## Secrets

No new secret is required for the local tools. Recognized optional names:

```text
GEMINI_API_KEY
YOUTUBE_API_KEY
PEXELS_API_KEY
FRED_API_KEY
NOAA_TOKEN
CENSUS_API_KEY
```

Never print values. Do not add ElevenLabs, Runway, or Creatomate to the default path.

## Required isolated checks

```bash
python -m unittest \
  review_prototypes.capability_studio.test_capability_studio \
  review_prototypes.capability_studio.test_free_capabilities \
  review_prototypes.capability_studio.test_toolchain_adoption

python -m review_prototypes.capability_studio.toolchain_cli catalog
python -m review_prototypes.capability_studio.toolchain_cli doctor
python -m review_prototypes.capability_studio.toolchain_cli keys
python -m review_prototypes.capability_studio.toolchain_cli route \
  --kind simple_chart --duration 6
```

## Non-negotiable acceptance criteria

- no production imports from `review_prototypes`;
- no `.github/workflows` change in this PR;
- zero mandatory new API keys;
- no paid provider in the default route;
- rights gate before yt-dlp video/audio downloads;
- workspace-scoped execution with no `shell=True`;
- exact versions/checkpoint hashes before heavy-model adoption;
- deterministic timeline and one scene clock;
- finished-video QA remains renderer-independent;
- fallback produces a complete video when an optional tool is absent;
- transactional keep-best and rollback remain intact;
- adoption is capability-by-capability, never a blind merge of the whole lab.
