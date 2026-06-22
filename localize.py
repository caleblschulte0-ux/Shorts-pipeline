"""Shared localization layer (bottom of funnel).

Translates a video's title + description into a wide language set so the SAME
Short surfaces in search and recommendations for viewers worldwide — no extra
uploads, and all views/engagement stay on one video. Used automatically by
``YouTubeUploader.upload()`` for every post on every channel.

What this covers vs. not:
  * COVERED (YouTube Data API): localized titles/descriptions, defaultLanguage,
    defaultAudioLanguage. These drive cross-language discovery and label the
    audio so the video is ready for dubbing.
  * NOT COVERED: alternate AUDIO tracks (dubs). The public Data API cannot
    attach them — they're added in YouTube Studio. This layer makes a video
    fully ready for that manual step (correct audio language declared).

Best-effort by design: a missing LLM key, a network error, or unparseable
model output all degrade to "English only" so a successful upload is never
lost to a localization hiccup.
"""
from __future__ import annotations

import json
import os

# BCP-47 code -> English name. First wave: highest-reach YouTube languages.
TARGET_LANGS = {
    "es": "Spanish", "hi": "Hindi", "pt": "Portuguese", "id": "Indonesian",
    "ar": "Arabic", "fr": "French", "de": "German", "ja": "Japanese",
    "ru": "Russian", "ko": "Korean", "it": "Italian", "tr": "Turkish",
}

_SYS = (
    "You are a professional localizer for short-form video metadata. Translate "
    "naturally for native speakers (not word-for-word), preserve meaning and "
    "tone, and keep numbers, units, currency symbols, #hashtags and URLs "
    "verbatim. Output STRICT JSON only — no prose, no code fences."
)


def _have_llm_key() -> bool:
    return bool(os.environ.get("GROQ_API_KEY")
                or os.environ.get("GEMINI_API_KEY")
                or os.environ.get("ANTHROPIC_API_KEY"))


def translate_metadata(title: str, description: str,
                       langs: dict | None = None) -> dict:
    """Return ``{code: {"title": ..., "description": ...}}`` for each target
    language. Empty dict on any failure so the caller ships English-only."""
    langs = langs or TARGET_LANGS
    if not _have_llm_key():
        print("[localize] no LLM key set — shipping English only", flush=True)
        return {}

    codes = ", ".join(f"{c} ({n})" for c, n in langs.items())
    user = (
        "Translate this YouTube Short's title and description into EACH of "
        f"these languages: {codes}.\n\n"
        f"TITLE:\n{title}\n\nDESCRIPTION:\n{description}\n\n"
        "Return JSON shaped exactly as:\n"
        '{"es": {"title": "...", "description": "..."}, "hi": {"title": '
        '"...", "description": "..."}}\n'
        "Use the given language codes as keys. Keep each title under 100 "
        "characters."
    )
    try:
        from script_generator import _call_llm, _strip_fence
        raw = _call_llm(_SYS, user)
        data = json.loads(_strip_fence(raw))
    except Exception as e:  # noqa: BLE001
        print(f"[localize] translation failed ({e}) — shipping English only",
              flush=True)
        return {}

    out = {}
    for code in langs:
        v = data.get(code) if isinstance(data, dict) else None
        if isinstance(v, dict) and v.get("title") and v.get("description"):
            out[code] = {"title": str(v["title"])[:100],
                         "description": str(v["description"])[:5000]}
    print(f"[localize] translated into {len(out)}/{len(langs)} languages: "
          f"{','.join(out) or '(none)'}", flush=True)
    return out
