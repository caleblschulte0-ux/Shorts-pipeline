# Advanced capability expansion — wave 2

> Review-only handoff. This commit changes no production code, workflows, uploader, secrets, or publishing authority.

## What was added

### Local intelligence and memory

- Ollama and llama.cpp for subscription-independent structured generation.
- sentence-transformers for local embeddings.
- FAISS/sqlite-vec semantic recall with SQLite FTS5 fallback.

Local model output must validate against the same evidence and content contracts as Claude or Gemini.

### Better research and evidence

- RSS and Atom feeds.
- sitemap discovery.
- Trafilatura/readability article extraction.
- JSON-LD metadata extraction.
- responsive Playwright screenshots and DOM capture.
- WARC evidence preservation.
- PaddleOCR for difficult tables and screenshots.

### Data and visualization

- DuckDB analytical SQL.
- Polars transforms.
- unit, geography, vintage, and frequency compatibility gates.
- Vega-Lite and Plotly/Kaleido graphics.
- Lottie and Remotion motion graphics.

### Maps

- Nominatim geocoding.
- OpenStreetMap Overpass queries.
- GeoPandas transformation.
- MapLibre animation.
- SVG map fallback.

### Captions, audio, and video

- WhisperX and stable-ts alignment.
- Silero VAD.
- RNNoise cleanup.
- librosa rhythm grids.
- karaoke word-highlight captions.
- optical-flow motion scoring.
- smart subject-aware reframing.
- black/freeze-frame detection.
- keyless procedural FFmpeg SFX.

### Visual intelligence

- SigLIP semantic ranking.
- DINOv2 visual memory.
- Grounding DINO text-guided object localization.

### Localization and original audio

- Argos Translate and NLLB local translation.
- MusicGen and AudioGen plans, disabled until model/output licensing and runner limits are validated.

## Routing examples

```text
cloud model unavailable       -> Ollama -> llama.cpp -> deterministic writer
large public dataset          -> DuckDB -> Polars -> data gates -> Vega-Lite
location story                -> Nominatim -> Overpass -> GeoPandas/MapLibre -> SVG fallback
caption upgrade               -> WhisperX -> Silero VAD -> karaoke ASS -> stable-ts fallback
horizontal source video       -> MediaPipe/OpenCV -> optical flow -> smart 9:16 reframe
visual search                 -> SigLIP + DINOv2 -> CLIP/phash fallback
localized publishing          -> NLLB -> Argos -> English-only fallback
custom SFX                    -> AudioGen -> procedural FFmpeg fallback
```

## Adoption order

1. DuckDB, Polars, data gates, and Vega-Lite.
2. RSS, sitemaps, extraction, and browser/WARC evidence.
3. karaoke captions, Silero VAD, and freeze/black-frame QA.
4. Lottie and Remotion shadow renders.
5. maps.
6. semantic memory.
7. Ollama/llama.cpp local generation.
8. smart reframe and advanced visual ranking.
9. GPU models and generative audio only after license, checkpoint, cost, and runtime proof.

## Required gates

- everything remains plan-only before shadow execution;
- no new mandatory API key;
- exact dependency/model versions and hashes;
- license records for models and generated asset classes;
- resource and runtime ceilings;
- output confined to the run workspace;
- lighter fallback for every advanced route;
- renderer-independent final-video QA;
- no publishing authority granted merely because a tool is installed.

## Checks

```bash
python -m unittest review_prototypes.test_advanced_capabilities
```
