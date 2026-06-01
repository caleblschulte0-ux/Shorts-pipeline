"""Shared core for the video pipeline.

Reusable, behavior-preserving stages extracted from make_short.py:
    sourcing  — yt-dlp / local fetch
    gameplay  — loop pick + trim
    tts       — edge-tts voiceover
    audio     — duck + mix
    captions  — whisper transcribe + ASS authoring
    render    — compose() (main app, verbatim) + render_layered() (new)

The main app (make_short.py) imports these so there is a single source of
truth. Its output is byte-identical to before this extraction — see
tools/verify_identical.py.
"""
from __future__ import annotations

from .audio import mix_audio
from .captions import (
    Word,
    group_words,
    transcribe,
    write_ass,
    _ass_escape,
    _ass_time,
)
from .constants import (
    GAMEPLAY_DIR,
    H,
    HALF_H,
    OUTPUT_DIR,
    ROOT,
    TTS_VOICE,
    VIDEO_EXTS,
    W,
)
from .gameplay import list_gameplay, pick_gameplay
from .render import (
    burn_captions,
    compose,
    mux_audio_track,
    render_background,
    render_layered,
)
from .shell import ffprobe_duration, run
from .sourcing import download_source, is_url
from .tts import synthesize_voiceover
from .visualgen import (
    Building,
    SceneSpec,
    generate_abstract_clip,
    generate_scene_clip,
    make_seamless_loop,
    overlay_logo,
)

__all__ = [
    "mix_audio",
    "Word",
    "group_words",
    "transcribe",
    "write_ass",
    "_ass_escape",
    "_ass_time",
    "GAMEPLAY_DIR",
    "H",
    "HALF_H",
    "OUTPUT_DIR",
    "ROOT",
    "TTS_VOICE",
    "VIDEO_EXTS",
    "W",
    "list_gameplay",
    "pick_gameplay",
    "burn_captions",
    "compose",
    "mux_audio_track",
    "render_background",
    "render_layered",
    "ffprobe_duration",
    "run",
    "download_source",
    "is_url",
    "synthesize_voiceover",
    "generate_abstract_clip",
    "generate_scene_clip",
    "make_seamless_loop",
    "overlay_logo",
    "SceneSpec",
    "Building",
]
