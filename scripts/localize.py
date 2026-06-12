#!/usr/bin/env python3
"""Translate a video's title + description into the channel's target languages
so we can attach YouTube `localizations` at upload time. Localized metadata is
the single biggest *automatable* discovery lever on YouTube: the same Short
surfaces in search/recommendations for viewers in each language.

Design notes:
  * Best-effort. Translation must NEVER block an upload — any failure for a
    language just drops that locale and we keep going (English always ships).
  * Cached on disk (state/translation_cache.json) keyed by (lang, source text),
    so re-runs are instant, deterministic, and don't re-hammer the endpoint.
    The workflow's state-persist step commits the cache back to the repo.
  * The CC-BY music attribution line is a legal notice — it is appended in
    English to every localized description, never translated.

Translation backend is deep-translator's GoogleTranslator (no API key). If the
package or network is unavailable, localize_meta() simply returns {} and the
uploader ships English only.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "state" / "translation_cache.json"

# Top 8 short-form languages by global reach. Keys are YouTube/BCP-47 codes.
LANGS: dict[str, str] = {
    "es": "spanish",
    "hi": "hindi",
    "pt": "portuguese",
    "id": "indonesian",
    "ar": "arabic",
    "fr": "french",
    "de": "german",
}
DEFAULT_LANG = "en"

# Kept in English on every localized description (license requirement).
ATTRIBUTION = ("Music by Kevin MacLeod (incompetech.com), licensed under "
               "Creative Commons: By Attribution 4.0 "
               "(creativecommons.org/licenses/by/4.0/)")


def _load_cache() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text())
        except Exception:  # noqa: BLE001 — a corrupt cache should never break a post
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n")


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


if __name__ == "__main__":  # tiny smoke test / manual use
    import sys
    ttl = sys.argv[1] if len(sys.argv) > 1 else "The deadliest animals on Earth"
    bod = sys.argv[2] if len(sys.argv) > 2 else "Mosquitoes kill more people than sharks. Here's the data."
    print(json.dumps(localize_meta(ttl, bod), ensure_ascii=False, indent=2))
