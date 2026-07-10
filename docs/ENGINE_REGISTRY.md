# Engine Registry

*The capability layer for every channel. Code lives in `engines/`; this doc is
the human/brain-readable registry and the triage record. Companion audit:
`docs/STORAGE_AUDIT.md`.*

**The premise:** the pipeline compounds by accumulating *engines* (Blender = a
3D engine, Manim = a math-animation engine), not one-off tools. Every entry
here answers: what problem does it solve, can it run headless, can Claude
drive it via Python/CLI, and is it reusable across many videos.

**The rule that keeps this from becoming a museum of cool software:** every
engine has a lifecycle state — `active` / `experimental` / `deferred` /
`rejected` — and every `experimental` engine must carry a measurable use case,
a demo asset set, a quality benchmark, a runtime benchmark, and a **decision
date**. Miss the date without a verdict → demote to `deferred`. An engine
earns `active` only by making videos better, not by being impressive.

**Discovery for future Claude sessions** (offline, fast, safe to run):

```
python -m engines list          # every registered engine + availability
python -m engines info parallax # full metadata incl. pinned model + license
python -m engines doctor        # deterministic health checks (no network)
python -m engines install parallax   # the ONLY networked command
python -m engines demo kenburns --image X --out Y
```

**The contract** (modeled on `higgsfield.maybe_animate_still`, the pipeline's
existing dormant-enhancer pattern): `available()` is offline-deterministic
(deps importable + binaries on PATH + model present with valid checksum —
never a network call); best-effort entry points are `maybe_*` and return a
result or `None`, never raising into a caller; engines never write outside
`cache/` (gitignored). **No production renderer or workflow imports
`engines/` today — every capability is opt-in.**

---

## Active engines

### Already integrated (owned by workflows/renderers; registered for `doctor`)

| Engine | Problem solved | Consumers | Notes |
|---|---|---|---|
| **ffmpeg** | all encode/filter/mux | every renderer | apt, every workflow |
| **Blender** (Cycles) | full 3D engine | curiosity (`longform_render.py:436`) | **ships with OpenVDB volumetrics and OpenColorIO built in** — see triage below |
| **Manim** | math/data animation | curiosity (`longform_render.py:382`) | |
| **Kokoro** (ONNX) | neural TTS, CPU | all channels | model pinned via cache key `kokoro-onnx-v1.0` |
| **edge-tts** | TTS fallback | all channels | |
| **rembg** (u2net) | subject cutout | explainer `scene_media`, mascot gen | covers the SAM 2 use case today |
| **whisper** | speech→text captions | caption pipeline | |
| **Gemini vision** | frame QA (`vision_judge`) | trending QA (`run_trending_daily.py:290`) | covers the Florence-2/Moondream use case |
| **yt-dlp** | clip acquisition | third channel | |
| **matplotlib** | chart engine | explainer | |
| **themed_bottom** | procedural game engine (own physics/easing) | trending bottom-half | in-repo engine, self-contained |
| **Higgsfield** | AI still→motion (paid API) | dormant (`HIGGSFIELD_ENABLE=1`) | the architectural template for `maybe_*` |

### New in this change

| Field | `still_motion` | `parallax` |
|---|---|---|
| status | **active** | **active (gated — E2 verdict 2026-07-10)** |
| problem | Ken Burns push on stills — canonical implementation | 2.5D depth-parallax camera move from one still — new capability |
| headless / CLI / reusable | yes / yes / yes | yes / yes / yes |
| license / commercial | stdlib+ffmpeg / ✅ | **Apache-2.0 (Small checkpoint only** — V2 Base/Large are CC-BY-NC: never use on monetized channels) / ✅ |
| cpu_ok / runtime | ✅ / ~1-3 s per clip | ✅ / ~2-5 s depth (CPU) + ~0.05 s/frame remap |
| memory | trivial | ~500 MB peak (fp32 ONNX) |
| model | — | `depth_anything_v2_small.onnx` · repo `onnx-community/depth-anything-v2-small` · rev `4472b7362082ad9968fee890ca0f1e5aca36b93d` · SHA-256 `afb6a5c28f3b6bf1618c6e43f02073ef9dfdc70e937502d51603e57b0a1df10c` · 99,060,839 bytes · input 518×518 |
| health check | `python -m engines doctor still_motion` | `python -m engines doctor parallax` (presence + checksum, offline) |
| fallback | is the fallback | `still_motion.kenburns` (callers get `None` → fall through) |
| consumers | none yet (see E1) | **none — must stay none until E2 passes** |
| known failure modes | corrupt input → error (use `maybe_kenburns`) | torn/haloed edges at depth discontinuities; rubber-sheet on flat art/diagrams; nonsense depth on illustrations; text shimmer |
| sample | `python -m engines demo kenburns --image assets/mascot/anchor/laugh.png --out /tmp/kb.mp4` | `python -m engines demo parallax --image photo.jpg --out /tmp/px.mp4` |

**Honesty notes:**
- `still_motion` is the *canonical future implementation*, *not* a completed
  consolidation — the three renderer copies (`make_explainer_stacked.py:1574`,
  `data_learning/longform_render.py:526`, `data_learning/studio_render.py:1029`)
  still exist and are still what production uses. Migration is **Ticket E1**.
- `parallax` is **experimental pending the visual benchmark** (Ticket E2). A
  depth map + remap does not automatically make good 2.5D — run
  `python -m engines.benchmarks.parallax_bench`, review the 8-category clips
  against the checklist, and only then decide. If it only works on a minority
  of categories it needs an automatic suitability gate, not broad use.
  The ONNX conversion is community-maintained (`onnx-community`), not the
  upstream project's primary artifact — hence the pinned revision + checksum.
- **OpenCV** enters the repo here as a shared dependency (`opencv-python-headless`),
  initially consumed only by parallax; stabilization/motion-QA uses are E-ticket
  material. It is *not* added to any workflow requirements.

---

## Triage of the suggested engine list

### Good later (tickets, in priority order)

| Engine | Verdict | Ticket |
|---|---|---|
| **NASA SPICE** (`spiceypy`) | Genuinely good fit: physically accurate planet/moon/spacecraft geometry for curiosity's space content. pip-installable, CPU, headless. Needs kernel files (~100s MB, actions/cache). | E3 |
| **pybullet** | One pip install covers the whole Box2D/Bullet/ODE trio: real 3D physics (falling/stacking/collision) rendered headless for explainer "what if" beats. | E4 |
| **GDAL + OpenStreetMap** | Real terrain/buildings/rivers/city renders from free data. Heavier install (apt gdal-bin + Python bindings), big payoff for geography content. Covers the honest 80% of the Cesium ambition with zero ToS risk. | E5 |
| **SoX** | Procedural audio polish beyond ffmpeg filters. Cheap apt install, modest payoff. | E6 |

### Deferred — not rejected, revisit on a concrete trigger

| Engine | Why not now | Revisit when |
|---|---|---|
| **OpenUSD** | Its real value is non-destructive scene composition — references, variants, layered world assets — not rendering. Today there is exactly one Blender scene template (`blender_hero.py`) and no 3D asset library to compose. | Multi-asset 3D world composition becomes painful (a growing library of reusable scenes/props across channels). |
| **OpenTimelineIO** | Editorial timeline *interchange* format. The pipeline composes edits programmatically and nothing round-trips with an NLE or human editor. | A human editor or external NLE enters the loop, or A/B re-edits of published videos become a workflow. |
| **SAM 2** | rembg already produces the cutouts the pipeline needs; SAM 2 is heavy on CPU runners. | rembg mask quality measurably blocks a shot type (log examples first). |

### Rejected for this pipeline (with reasons — say if something is dumb: several of these were)

| Engine | Reason |
|---|---|
| **OpenVDB (standalone)** | Already own it: Blender ships with OpenVDB volumetrics. "Integrate OpenVDB" = author smoke/clouds/fog in the existing Blender path. A standalone C++ build would duplicate a capability we have. |
| **OpenColorIO (standalone)** | Same — built into Blender. The 2D/photo pipeline gets consistent grading far cheaper with a shared ffmpeg LUT (`lut3d=`) if ever needed. |
| **Assimp** | Solves multi-format 3D asset interchange. We have no 3D asset zoo — the repo's only 3D content is procedurally authored in Blender. A solution without a problem. |
| **Cesium** | A streaming JS globe runtime tied to Cesium ion accounts/ToS; not CI-friendly, not a headless Python engine. The realistic subset (terrain/city flyovers) is E5 with free OSM/GDAL data. |
| **VTK / ParaView** | Professional scientific viz for volumetric/CFD data we do not have. At Shorts scale, Manim + matplotlib cover the need. Revisit only for a channel built on real simulation datasets. |
| **Particle Life** | A toy/screensaver. `themed_bottom.py` already IS the in-repo procedural particle/physics playground, tuned for retention. |
| **VapourSynth** | Its killer features (RIFE interpolation, ML denoise/upscale) want a GPU we don't have; the CPU-viable remainder (sharpen, tweaks) is plain ffmpeg filters. |
| **RoughJS** | A Node dependency for a hand-drawn aesthetic that `matplotlib` xkcd-mode approximates without adding a JS runtime to CI. |
| **Florence-2 / Moondream** | Frame QA already exists via Gemini vision (`gemini_images.vision_judge`) — better quality than a small local model on CPU, effectively free at current volume, and fail-open by design. A local fallback only becomes interesting if Gemini quota/cost bites. |

---

## Tickets

- **E1 — Ken Burns migration.** ◐ IN PROGRESS (2026-07-10): the trending
  renderer (`make_explainer_stacked.py`, `is_image` branch) now routes
  through `engines.still_motion` behind the opt-in env flag
  `ENGINES_STILL_MOTION=1` (default OFF — zero production change). Next:
  regression renders via the preview workflow with the flag on, then flip
  the default, then migrate `longform_render.py` + `studio_render.py` and
  delete the duplicate implementations. Only after this may the registry
  say "consolidated".
- **E2 — Parallax verdict.** ✅ DECIDED 2026-07-10 (ahead of the 07-24
  deadline). Benchmark ran across all 8 categories (3s clips, 1080x1350,
  CPU ~3-4s each). Verdict per category: portrait/animal/landscape/city/
  space/overlap-foreground — PASS (real depth motion, no tearing or halos
  at strength=18); text — degenerates to a rigid shift (harmless, but
  pointless vs Ken Burns); illustration — depth is hallucinated on flat
  art. Finding: the depth model reports CONFIDENT depth even on flat
  inputs, so depth statistics cannot gate — the INPUT is screened instead.
  Shipped `_suitable()` gate: flat-art detector (fraction of exactly-flat
  8x8 blocks — vector fills 0.68 vs photos ≤0.43) + text detector
  (color-uniformity AND stroke-density both high), plus a `content=` caller
  hint ("photo" bypasses, "art"/"text"/"chart" refuses). **Status →
  active (gated).** Thresholds calibrated on the v1 bench set — recalibrate
  when the bench grows. Caveats recorded honestly: review was frame-based
  (temporal wobble not fully judged), so the first channel adoption must go
  through a preview render before flipping any default.
- **E3 — spiceypy engine** (`engines/ephemeris.py`): planet/moon/spacecraft
  positions for curiosity; kernels in `cache/`, actions/cache in the curiosity
  workflow only.
- **E4 — pybullet engine** (`engines/physics.py`): headless sim → frame
  sequence → ffmpeg, same `maybe_*` contract.
- **E5 — geo engine** (`engines/geo.py`): OSM extract + GDAL DEM → styled
  map/terrain renders (Natural Earth data — see E14).
- **E6 — SoX audio chain** (`engines/audio_polish.py`).

### Backlog (recorded 2026-07-10 — approved for the queue, one at a time)

*Tier 1 — capabilities hiding inside engines we already own (zero new installs):*

- **E7 — Blender volumetrics + compositor templates.** Smoke, fog, god-rays,
  atmosphere for curiosity hero shots. The engine is installed; only scene
  templates (`data_learning/blender_*.py`) are missing. This IS the OpenVDB
  "integration".
- **E8 — Kinetic typography engine** (`engines/kinetic_text.py`). The ASS/libass
  caption path already supports karaoke tags, per-word pops, color sweeps —
  an unused motion-graphics engine inside ffmpeg. Ship reusable templates.
- **E9 — Depth-map reuse pack.** Parallax's depth model also enables fake
  depth-of-field blur, fog-by-distance, and dolly-zoom on any photo — one
  model, four effects. **Gated on E2 passing**; extends `engines/parallax.py`.
- **E10 — Channel LUT pack** (`engines/grade.py`). One `lut3d` per channel for
  a consistent color identity. The realistic version of the OpenColorIO idea.

*Tier 2 — new engines that pass all four tests:*

- **E11 — MediaPipe composition/QA** (`engines/composition.py`, Apache-2.0,
  CPU, pip). Face/pose/object landmarks → auto-crop stills so subjects don't
  sit under the caption block, smarter thumbnail crops, subject-presence QA.
  Best pound-for-pound candidate in the backlog.
- **E12 — PySceneDetect highlight cuts** (`engines/scene_cuts.py`, CPU, pip).
  Automatic cut detection for the third channel: find the actual highlight
  moment in a captured clip instead of trusting spec timestamps.
- **E13 — Lottie vector motion graphics** (`engines/vector_motion.py`,
  python-lottie). Crisp animated icons/arrows/counters — the gap between
  matplotlib charts and full Blender.

*Tier 3 — data engines (story fuel is an engine too):*

- **E14 — Datasets engine** (`engines/datasets.py`). Thin fetch+cache wrappers
  with license metadata baked in: Our World in Data (CC-BY CSVs — endless
  "top 10 X by Y" chart stories), Wikidata SPARQL (superlatives/rankings on
  demand), Natural Earth (feeds E5), NASA open APIs. Cache under `cache/`,
  same provisioning pattern as models.

*Round-two rejects (asked and answered — recorded so they don't come back):*
local diffusion image-gen (CPU-hopeless on runners; Gemini/Pollinations
already cover it), Real-ESRGAN / RIFE upscale-interpolation (GPU-bound),
voice cloning (rights/likeness minefield on monetized channels).

## Adding a new engine (checklist)

1. It must let the channels tell stories they literally could not tell before
   (or kill a real cost). "Cool" is not a criterion.
2. CPU-viable on ubuntu-latest, headless, driveable from Python/CLI.
3. License permits commercial use (channels are monetized) — record it here.
4. Module in `engines/<name>.py` honoring the contract; `REGISTRY` entry with
   pinned models (URL + revision + SHA-256 + size); provisioning via
   `python -m engines install <name>`; entry in this doc with lifecycle state,
   failure modes, fallback, sample command, and — if `experimental` — a
   benchmark and a decision date.
