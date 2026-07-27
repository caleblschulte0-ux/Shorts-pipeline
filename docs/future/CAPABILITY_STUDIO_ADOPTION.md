# Capability Studio adoption guide

> Review-only. This document and its package do not affect production.

## What is implemented

The isolated package defines contracts and reference logic for the capability work
requested after the Professional Media OS prototype:

1. audience-demand mining;
2. competitor structure analysis;
3. creative candidate tournaments;
4. browser and document evidence capture;
5. directed voice and pronunciation;
6. custom generative video and visual reference locking;
7. intentional B-roll and multi-provider media search;
8. programmatic editing through FFmpeg, Auto-Editor, Remotion, and Creatomate;
9. local transcription, subtitle planning, upscaling, interpolation, background removal, lip sync, sound design, and color grading;
10. thumbnail ranking, format-aware final QA, capability truth records, evidence contracts, replay bundles, asset recall, and shared technical learning.

## Secret names reserved by the prototype

Existing or likely already configured:

- `YOUTUBE_API_KEY`
- `YOUTUBE_TOKEN_JSON`
- `PEXELS_API_KEY`

New optional providers:

- `ELEVENLABS_API_KEY`
- `RUNWAYML_API_SECRET`
- `CREATOMATE_API_KEY`
- `CARTESIA_API_KEY`
- `PLAYHT_API_KEY`
- `PLAYHT_USER_ID`
- `SYNC_API_KEY`
- `OPENAI_API_KEY`

No secret is read by the prototype. These names are contracts for later adoption.

## Local tools

The package emits command plans for FFmpeg/ffprobe, Faster-Whisper, Auto-Editor,
Playwright, Tesseract, Real-ESRGAN, RIFE, rembg, Remotion, Blender, and Manim.

## Required migration discipline

- run the isolated test module;
- inspect every generated HTTP request and shell command;
- never expose provider keys to browser/client code;
- add cost ceilings to metered providers;
- keep Runway and other generated-video providers behind per-video shot budgets;
- preserve source and rights lineage for every asset;
- run candidate systems in shadow mode before allowing automatic selection;
- keep QA fail-closed for publishing once calibrated;
- preserve channel-specific creative doctrine while sharing technical capabilities.
