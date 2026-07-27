# Capability Studio — review-only prototype

This package is an isolated reference implementation for future creative, media,
audio, editing, QA, research, replay, evidence, and plugin capabilities.

## Safety boundary

- standard-library Python only;
- no production imports;
- no workflow, uploader, OAuth, renderer, secret, or production-state access;
- no network execution by default (`DisabledTransport` fails closed);
- browser capture entrypoint is deliberately inert;
- all providers return inspectable request plans rather than sending requests;
- all local integrations return inspectable command plans rather than executing tools;
- writes occur only when the caller supplies a path;
- nothing here is wired to a live channel.

## Included capabilities

- audience-demand mining from comments;
- competitor video reverse engineering;
- hook/title/opening/ending candidate studio and tournaments;
- global idea routing and semantic duplicate checks;
- intentional B-roll planning;
- Pexels, Openverse, Wikimedia, and Internet Archive search plans;
- rights normalization, media quality scoring, and duplicate detection;
- browser/PDF evidence-capture plans;
- directed TTS routing for ElevenLabs, Cartesia, PlayHT, and local Kokoro;
- local Faster-Whisper transcription and subtitle plans;
- sound-effects and audio-mix plans;
- FFmpeg, Auto-Editor, Remotion, and Creatomate edit plans;
- Real-ESRGAN upscaling, RIFE interpolation, rembg removal, color grading, and loudness normalization;
- Runway custom video and reference-locking plans;
- Sync lip-sync plans;
- thumbnail tournaments and format-aware final-video gates;
- capability truth records, evidence contracts, replay bundles, asset recall, and shared technical learning.

## Isolated checks

```bash
python -m unittest review_prototypes.capability_studio.test_capability_studio
python -m review_prototypes.capability_studio.cli demo
python -m review_prototypes.capability_studio.cli keys
python -m review_prototypes.capability_studio.cli doctor --output /tmp/capability_report.json
```

## Adoption rule

Do not import this package from production. Port one adapter or contract at a time
through a separate reviewed change, execute real tests, and verify finished-video
behavior before granting authority.
