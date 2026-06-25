"""Hook image for a data-explainer story (best-effort).

Opens the video on a *picture of the subject* instead of a blank background.
Reuses the repo's license-aware, no-API-key image search (Wikipedia / Wikimedia
Commons / news og:image via ``topic_media``) plus a small cached downloader.

Returns a local image Path, or None when nothing relevant is found — abstract
topics (e.g. "personal saving rate") legitimately have no clean photo, and the
renderer falls back to a polished *designed* hook. Every failure path returns
None so a hiccup can never break a render.
"""
from __future__ import annotations

import hashlib
import re
import ssl
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

CACHE_DIR = REPO / "state" / "hook_images"

# Filler dropped when turning a title into an image query — keep the concrete
# nouns ("wedding", "wildfire", "cocoa") that actually find a photo.
_STOP = set("""
the a an and or of to in on for is are was were be been it its your you we our us
how why what when where who much more than that this these those now never ever
just only most least americans american usa year years from up down by at as with
into about now costs cost more less new record amount their than is've don't
""".split())

# Generic/meta hashtags that aren't a visual subject — never use as a query.
_TAG_SKIP = set("""
data fyp fyp viral shorts short money costofliving inflation prices price economy
usa us america american world global news today trending explained explainer chart
charts statistics stats facts didyouknow education learn budget budgeting finance
""".split())


def _candidates(story) -> list[str]:
    """Ordered image-search queries: explicit override, then the story's
    concrete hashtags (the best subject keywords), then title nouns."""
    out: list[str] = []
    explicit = (getattr(story, "hook_query", "") or "").strip()
    if explicit:
        out.append(explicit)
    for tag in (getattr(story, "hashtags", None) or []):
        t = re.sub(r"[^a-z]", "", str(tag).lower())
        if t and t not in _TAG_SKIP and len(t) >= 3 and t not in out:
            out.append(t)
        if len(out) >= 4:
            break
    title = getattr(story, "title", "") or ""
    keep = [w for w in re.findall(r"[A-Za-z][A-Za-z'\-]+", title)
            if w.lower() not in _STOP]
    if keep:
        out.append(keep[0])
    return out[:5]


def _download(url: str, cache_dir: Path) -> Path | None:
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        ext = ".jpg"
        for e in (".jpg", ".jpeg", ".png", ".webp"):
            if e in url.lower():
                ext = ".png" if e == ".png" else ".jpg"
                break
        dest = cache_dir / (hashlib.sha1(url.encode()).hexdigest()[:16] + ext)
        if dest.exists() and dest.stat().st_size > 2048:
            return dest
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={"User-Agent": "shorts-pipeline/1.0"})
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            data = r.read()
        if len(data) < 2048:                       # too tiny to be a real image
            return None
        dest.write_bytes(data)
        # Reject low-res images that would upscale blurry behind a 1080-wide hook.
        try:
            from PIL import Image
            with Image.open(dest) as im:
                if min(im.size) < 500:
                    dest.unlink(missing_ok=True)
                    return None
        except Exception:  # noqa: BLE001 — if PIL can't read it, it's unusable
            dest.unlink(missing_ok=True)
            return None
        return dest
    except Exception:  # noqa: BLE001 — never let a download break a render
        return None


def fetch_hook_image(story, *, cache_dir: Path = CACHE_DIR) -> Path | None:
    """Return a cached local image Path relevant to the story, or None."""
    if getattr(story, "hook_image", None) is False:   # explicit per-story opt-out
        return None
    try:
        import topic_media          # noqa: WPS433
        import entity_media         # noqa: WPS433
    except Exception:  # noqa: BLE001
        return None
    context = getattr(story, "hook", "") or ""
    for query in _candidates(story):
        try:
            urls = topic_media.search(query, context) or []
        except Exception:  # noqa: BLE001
            continue
        for url in urls[:5]:
            try:
                if not entity_media.url_is_image(url):
                    continue
            except Exception:  # noqa: BLE001
                continue
            p = _download(url, cache_dir)
            if p:
                return p
    return None
