# shared/ — reusable pipeline core

Behavior-preserving stages extracted from `make_short.py` so the main app and
the new `livestream` / `localize` modules share one source of truth.

| Module | Stage | Notes |
|---|---|---|
| `sourcing.py` | source fetch | yt-dlp download / local copy |
| `gameplay.py` | gameplay loop | pick + trim; `gameplay_dir` is a param |
| `tts.py` | voiceover | edge-tts; `voice` is a param (localize passes in-language voices) |
| `audio.py` | audio mix | duck source under voiceover |
| `captions.py` | captions | whisper transcribe + ASS authoring; style is parameterized |
| `render.py` | render | see below |
| `constants.py` | shared constants | `W/H/HALF_H`, voice, paths — verbatim from make_short.py |

## Two renderers in `render.py`

- **`compose()`** — the MAIN APP's renderer, lifted **verbatim**. One ffmpeg
  pass: stack → burn captions → mux audio. The daily money-maker uses this and
  its output is **byte-identical** to before the extraction.
- **`render_layered()`** — NEW, additive. Same stacked Short but built as
  **separate layers** in distinct passes (`render_background` →
  `burn_captions` → `mux_audio_track`). Used by the new modules; **not** used
  by the main app and **not** byte-identical to `compose()`. Splitting the
  layers is what lets `localize` keep a finished video's background + timing
  and re-run only captions + audio.

## Proof of non-breaking extraction

`tools/verify_identical.py` renders a real Short through the pre-refactor
`make_short.py` (fetched from git `HEAD`) and through `shared/` on byte-identical
pinned inputs, then byte-compares the MP4s. Run it after touching anything in
this folder:

```bash
python3 tools/verify_identical.py   # exit 0 = byte-identical
```

It does not exercise edge-tts or whisper themselves (network/model only, and
those were moved verbatim) — it proves the render-math stages are unchanged.
