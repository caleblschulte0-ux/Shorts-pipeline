"""Shared localization layer (bottom of funnel) — single source of truth.

Translates a video's title + description into the channel's target languages so
the SAME Short surfaces in search/recommendations for viewers worldwide. Used by
``scripts/post_stories.py`` (explicit) AND auto-invoked by
``uploaders.YouTubeUploader.upload()`` when a caller passes no localizations — so
BOTH channels localize automatically with no per-call-site changes.

Backend is deep-translator's GoogleTranslator (no API key). Results are cached on
disk (state/translation_cache.json) so re-runs are instant and the workflow
commits the cache back. Best-effort: any failure for a language drops that locale
and English always ships — translation never blocks an upload.

NOTE: the public YouTube Data API can localize titles/descriptions and declare
the audio language, but cannot attach alternate AUDIO tracks (dubs) — those are
a YouTube Studio step. This module covers everything the API exposes.

History: this consolidates two previously-colliding modules (a root and a
scripts/ copy, both named ``localize``) into one, which is what caused an import
failure that silently disabled localization. Keep it as the only ``localize``.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Translation cache (audit Ticket 3): split per channel and moved OUT of
# git into cache/ (gitignored, persisted between CI runs via actions/cache).
# The old committed state/translation_cache.json was rewritten wholesale by
# three channels concurrently — the single worst git-churn file in the repo
# and a permanent push-race hazard. Losing this cache costs only some
# re-translation; it is not state.
_LEGACY_CACHE = ROOT / "state" / "translation_cache.json"


def _cache_path() -> Path:
    chan = os.environ.get("TRANSLATION_CACHE_CHANNEL") \
        or os.environ.get("YOUTUBE_EXPECTED_CHANNEL") or "shared"
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", chan).strip("_").lower() or "shared"
    return ROOT / "cache" / "translation" / f"{slug}.json"


CACHE = _cache_path()

# Top short-form languages by global reach. Keys are YouTube/BCP-47 codes;
# values are GoogleTranslator language names.
LANGS: dict[str, str] = {
    "es": "spanish",
    "hi": "hindi",
    "pt": "portuguese",
    "id": "indonesian",
    "ar": "arabic",
    "fr": "french",
    "de": "german",
}

# Extended set for channels that want max worldwide reach (opt-in via the
# langs= parameter — the default LANGS behavior is unchanged). Used by the
# clipper (channel "third"), whose content is visual-first and travels.
ALL_LANGS: dict[str, str] = {
    **LANGS,
    "ja": "japanese",
    "ko": "korean",
    "ru": "russian",
    "tr": "turkish",
    "vi": "vietnamese",
    "th": "thai",
    "pl": "polish",
    "it": "italian",
    "nl": "dutch",
    "ms": "malay",
    "ur": "urdu",
    "bn": "bengali",
    "ta": "tamil",
    "fil": "filipino",
    "sw": "swahili",
    "fa": "persian",
    "uk": "ukrainian",
    "el": "greek",
    "cs": "czech",
    "ro": "romanian",
    "hu": "hungarian",
    "sv": "swedish",
}
DEFAULT_LANG = "en"

# Kept in English on every localized description (license requirement).
ATTRIBUTION = ("Music by Kevin MacLeod (incompetech.com), licensed under "
               "Creative Commons: By Attribution 4.0 "
               "(creativecommons.org/licenses/by/4.0/)")


def _load_cache() -> dict:
    for path in (CACHE, _LEGACY_CACHE):  # legacy file seeds the first run
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:  # noqa: BLE001 — corrupt cache must never break a post
                continue
    return {}


def _save_cache(cache: dict) -> None:
    from fsutil import atomic_write_json
    atomic_write_json(CACHE, cache, ensure_ascii=False, sort_keys=True)


def _translate(text: str, lang_name: str, cache: dict) -> str | None:
    """Return translated text (cached), or None on any failure."""
    if not text.strip():
        return text
    key = f"{lang_name} {text}"
    if key in cache:
        return cache[key]
    try:
        from deep_translator import GoogleTranslator
        out = GoogleTranslator(source="auto", target=lang_name).translate(text)
    except Exception as e:  # noqa: BLE001
        print(f"[localize] {lang_name} skipped: {e}", flush=True)
        return None
    if out:
        cache[key] = out
    return out


def localize_meta(title: str, body: str, suffix: str = "",
                  langs: dict[str, str] | None = None) -> dict[str, dict]:
    """Return {lang_code: {"title": ..., "description": ...}} for each target
    language. Only `title` and the prose `body` are translated; `suffix`
    (hashtags + the CC-BY attribution) is appended verbatim in English so tags
    stay clickable and the license notice stays intact. Missing/failed
    languages are simply omitted."""
    langs = langs or LANGS
    cache = _load_cache()
    out: dict[str, dict] = {}
    # YouTube hard-limits localizations to title<=100 / description<=5000.
    for code, name in langs.items():
        t = _translate(title, name, cache)
        b = _translate(body, name, cache)
        if not t and not b:
            continue
        desc = (b or body).strip() + suffix
        out[code] = {"title": (t or title)[:100], "description": desc[:5000]}
    _save_cache(cache)
    if out:
        print(f"[localize] localized into: {', '.join(out)}", flush=True)
    return out


def translate_metadata(title: str, description: str,
                       langs: dict[str, str] | None = None) -> dict[str, dict]:
    """Compatibility wrapper for the uploader's auto-localize path: translates a
    title + a full description (no separate hashtag/attribution suffix)."""
    return localize_meta(title, description, "", langs)


if __name__ == "__main__":  # tiny smoke test / manual use
    import sys
    ttl = sys.argv[1] if len(sys.argv) > 1 else "The deadliest animals on Earth"
    bod = sys.argv[2] if len(sys.argv) > 2 else "Mosquitoes kill more people than sharks. Here's the data."
    print(json.dumps(localize_meta(ttl, bod), ensure_ascii=False, indent=2))
