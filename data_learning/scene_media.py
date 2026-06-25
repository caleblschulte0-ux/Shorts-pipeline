"""Cinematic scene imagery for the data-explainer channel (best-effort).

Every scene (the hook, and each segment) gets a bold, attention-grabbing image
behind the animated data. Order of preference:

  1. AI generation via Gemini (free-tier, vertical 9:16) — bold cinematic look.
  2. A license-safe stock photo (Wikipedia/Commons via topic_media).
  3. None — the renderer falls back to a designed gradient.

All failures (no key, quota, network) degrade to the next option and ultimately
to None, so a scene always renders. Images cache under state/scene_images/.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from data_learning import hook_media           # noqa: E402 — stock fetch + query helpers

CACHE_DIR = REPO / "state" / "scene_images"


def _prompt(subject: str, context: str = "") -> str:
    """Bold-cinematic art direction. Gemini appends its own
    'vertical 9:16, no text' suffix, so we focus on look + subject."""
    ctx = f" Context: {context.strip()}." if context.strip() else ""
    return (
        f"A bold, cinematic poster-style image representing {subject}.{ctx} "
        "Dramatic moody lighting, vibrant high-contrast color grade, shallow "
        "depth of field, epic and eye-catching, editorial magazine quality, "
        "strong central subject, vertical composition. No text or numbers."
    )


_DIAG_DONE = False


def _diag_once():
    """Log, once per run, what image models this Gemini key actually exposes —
    so we can tell 'not enabled' from 'quota' from 'reachable'."""
    global _DIAG_DONE
    if _DIAG_DONE:
        return
    _DIAG_DONE = True
    try:
        import gemini_images
        print(f"[scene][diag] gemini enabled={gemini_images.enabled()}", flush=True)
        avail = gemini_images._available_models()
        img = sorted(m for m in avail if "image" in m.lower() or "imagen" in m.lower())
        print(f"[scene][diag] image-capable models visible ({len(img)}): {img}",
              flush=True)
        free = [m for m in gemini_images.FREE_IMAGE_MODELS if (not avail or m in avail)]
        print(f"[scene][diag] usable FREE image models: {free}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[scene][diag] probe error: {e}", flush=True)


def _gen_pollinations(subject: str, dest: Path, context: str = "") -> Path | None:
    """Generate a bold-cinematic image via Pollinations.ai — FREE, no API key,
    just an HTTP GET. Deterministic per prompt (seeded) so re-renders are stable.
    Best-effort: any failure returns None and the caller falls back."""
    import hashlib
    import ssl
    import urllib.parse
    import urllib.request
    try:
        prompt = _prompt(subject, context)
        seed = int(hashlib.sha1(prompt.encode()).hexdigest()[:8], 16)
        url = ("https://image.pollinations.ai/prompt/"
               + urllib.parse.quote(prompt)
               + f"?width=1080&height=1920&nologo=true&model=flux&seed={seed}")
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={"User-Agent": "shorts-pipeline/1.0"})
        with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
            data = r.read()
        if len(data) < 4096:
            return None
        dest.write_bytes(data)
        from PIL import Image
        with Image.open(dest) as im:
            if min(im.size) < 400:
                dest.unlink(missing_ok=True)
                return None
        print(f"[scene] pollinations image OK -> {dest.name}", flush=True)
        return dest
    except Exception as e:  # noqa: BLE001 — never block a render
        print(f"[scene] pollinations skipped: {e}", flush=True)
        return None


def _gen_ai(subject: str, dest: Path, context: str = "") -> Path | None:
    try:
        import gemini_images
        _diag_once()
        if not gemini_images.enabled():
            return None
        p = gemini_images.generate_image(_prompt(subject, context), dest)
        if p and Path(p).exists() and Path(p).stat().st_size > 2048:
            print(f"[scene] AI image OK -> {Path(p).name}", flush=True)
            return Path(p)
        print("[scene] AI image returned nothing — falling back to stock", flush=True)
    except Exception as e:  # noqa: BLE001 — never block a render
        print(f"[scene] AI image skipped: {e}", flush=True)
    return None


def scene_image(subject: str, slug: str, tag: str, *, context: str = "",
                allow_stock: bool = True, cache_dir: Path = CACHE_DIR) -> Path | None:
    """Return a cached cinematic image for `subject` (AI → stock → None).
    `tag` distinguishes scenes within a story (e.g. 'hook', 'seg01')."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in f"{slug}__{tag}")
    dest = cache_dir / f"{safe}.png"
    if dest.exists() and dest.stat().st_size > 2048:
        return dest
    if (subject or "").strip():
        # Free AI first (Pollinations), then paid Gemini if ever enabled.
        poll = _gen_pollinations(subject, dest, context)
        if poll:
            return poll
        ai = _gen_ai(subject, dest, context)
        if ai:
            return ai
    if allow_stock:
        try:
            import topic_media
            import entity_media
            cands, seen = [], set()
            for q in [subject] + [w for w in (subject or "").split() if len(w) > 3]:
                q = q.strip()
                if q and q.lower() not in seen:
                    seen.add(q.lower())
                    cands.append(q)
            for q in cands[:4]:
                urls = topic_media.search(q, context) or []
                for url in urls[:4]:
                    try:
                        if entity_media.url_is_image(url):
                            p = hook_media._download(url, cache_dir)
                            if p:
                                return p
                    except Exception:  # noqa: BLE001
                        continue
        except Exception:  # noqa: BLE001
            pass
    return None


def fetch_hook_image(story, *, cache_dir: Path = CACHE_DIR) -> Path | None:
    """AI-first cinematic hook image for a story; stock then designed fallback."""
    if getattr(story, "hook_image", None) is False:
        return None
    cands = hook_media._candidates(story)
    subject = (getattr(story, "hook_query", "") or " ".join(cands[:2])
               or getattr(story, "title", "")).strip()
    return scene_image(subject, getattr(story, "slug", "story"), "hook",
                       context=getattr(story, "hook", "") or "", cache_dir=cache_dir)
